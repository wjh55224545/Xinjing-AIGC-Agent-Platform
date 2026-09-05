"""
基础情绪参数 — E1/E2/E3 三个独立基础参数。

这三个参数是VibraImage参数体系的基石，从三个正交维度分析头部微振动:
- E1 Aggression: 频率直方图统计 → 振动频率的强度和离散度
- E2 Stress: 空间不对称性 → 左右半脸运动的不一致性
- E3 Tension: 频谱功率比 → 高频振动能量的占比

所有其他情绪参数(E4-E12)都由这三个基础参数派生或依赖频率直方图。
三者之间在数学上无相关性 (VCE.pdf p76)。

公式来源:
- E1: 方程(3), VCE.pdf p60
- E2: 方程(4), VCE.pdf p71
- E3: 方程(5), VCE.pdf p75
"""

import numpy as np
from typing import Tuple
from ..core.histogram import HistogramStats
from ..core.spatial_analyzer import PerLineStats


def compute_aggression(
    hist_stats: HistogramStats,
    f_in: float = 10.0,
) -> float:
    """
    计算E1 — Aggression (攻击性)。

    方程(3), VCE.pdf p60:
        E1 = F_max × σ_freq / (2 × F_in) × 100%

    物理含义 (p60-61):
        - F_max: 频率直方图峰值 → 最高频的振动模式
        - σ_freq: 频率分布离散度 → 振动模式的不均匀性
        - 高频+高离散 = 高攻击性
        - Lorenz认为攻击性与反射运动频率成正比; VibraImage在此基础上
          增加了频率离散度的影响 — 运动员(活跃但非攻击)离散度低，
          攻击状态者离散度高

    Parameters
    ----------
    hist_stats : HistogramStats
        频率直方图统计量。
    f_in : float
        VibraImage 处理频率 F_in [Hz] (方程(3) 分母)。

    Returns
    -------
    aggression : float
        攻击性参数 [0-100]%。

    Notes
    -----
    方程(3) 的 `/2` 与 `F_in` 分母已在 VCE.pdf 原文中确认 (cid 文本出现
    `2F_in`)，但 F_in 的数值口径在抽取文本中无法唯一还原 (候选: 帧率 30Hz
    或有效频段上界 10Hz)。实测 (9 条真实视频): F_in=10Hz 使 aggression 落在
    常模 41.99±3SD 内，F_in=30Hz 则偏低至 ~11。故取 10Hz (= FREQ_BAND[1])。
    该取值口径为标定驱动，F_in 确切数值待源文献 Minkin 2014 确认，不擅自拍板。
    """
    if hist_stats.total_pixels == 0 or f_in <= 0:
        return 0.0

    F_max = max(hist_stats.F_max, 0.01)  # 避免除零
    sigma = hist_stats.sigma

    # E1 = F_max × σ / (2 × F_in) × 100%
    aggression = (F_max * sigma) / (2.0 * f_in) * 100.0

    return float(np.clip(aggression, 0.0, 100.0))


def compute_stress(per_line: PerLineStats) -> float:
    """
    计算E2 — Stress (压力)。

    方程(4), VCE.pdf p71:
        E2 = [Σ(|A_Li−A_Ri|/A_max_i + |F_Li−F_Ri|/F_max_i) / (2n)] × 100%

    物理含义 (p71-72):
        - A_Li, A_Ri: 第i行左右侧振动振幅总量
        - F_Li, F_Ri: 第i行左右侧最大振动频率
        - A_max_i = max(A_Li, A_Ri)，F_max_i = max(F_Li, F_Ri)
        - 左右半脸运动不对称 = 高压力
        - 人体放松时运动均匀对称; 压力状态下出现间歇性不对称运动
        - 同时使用振幅和频率两个维度提高对不同压力表现形式的灵敏度

    Parameters
    ----------
    per_line : PerLineStats
        逐行左右分析结果。

    Returns
    -------
    stress : float
        压力参数 [0-100]%。
    """
    if per_line.n_lines == 0:
        return 50.0  # 无有效数据 → 中性值

    n = float(per_line.n_lines)

    # VCE 方程(4)使用逐行 A_max_i / F_max_i，而不是全局最大值。
    # 同时，p71原文明确说明“大幅度/频率左右差异 → Stress 增高”，
    # 因此 E2 应直接等于不对称度百分比，不是 1 - asymmetry。
    A_max_i = np.maximum(np.maximum(per_line.A_L, per_line.A_R), 1e-6)
    F_max_i = np.maximum(np.maximum(per_line.F_L, per_line.F_R), 1e-6)

    amp_term = np.sum(np.abs(per_line.A_L - per_line.A_R) / A_max_i)
    freq_term = np.sum(np.abs(per_line.F_L - per_line.F_R) / F_max_i)

    stress = (amp_term + freq_term) / (2.0 * n) * 100.0

    return float(np.clip(stress, 0.0, 100.0))


def compute_tension(
    power_spectrum: np.ndarray,
    high_freq_threshold: float = 5.0,
    freq_band: Tuple[float, float] = (0.1, 10.0),
) -> float:
    """
    计算 E3 — Tension/Anxiety (紧张/焦虑)。

    方程 (5), VCE.pdf p75:
        E3 = [Σ_{f=f_threshold}^{f_max} P(f_i)] / [Σ_{f=0.1}^{f_max} P(f_i)] × 100%

    物理含义 (p75-76):
        - P(f_i): 振动频谱功率
        - 高频振动密度高 = 紧张/焦虑
        - 与 EEG 检测焦虑的β波分析方法类似
        - 三个负性情绪参数从三个正交维度:
          Aggression → 统计特征 (均值 + 标准差)
          Stress → 空间特征 (对称性)
          Tension → 频率特征 (高频比例)

    Parameters
    ----------
    power_spectrum : np.ndarray, shape (n_bins,)
        聚合频谱功率分布。
    high_freq_threshold : float
        高频分界点 [Hz]。默认 3.0Hz（标定记录选择，见 run_validation 的 CALIB_RECORD）。
    freq_band : tuple
        有效频段 (f_min, f_max)。

    Returns
    -------
    tension : float
        紧张参数 [0-100]%。
    """
    total_power = np.sum(power_spectrum)
    if total_power <= 0:
        return 0.0

    n_bins = len(power_spectrum)
    bin_width = (freq_band[1] - freq_band[0]) / n_bins
    high_start_bin = int((high_freq_threshold - freq_band[0]) / bin_width)
    high_start_bin = max(0, min(n_bins - 1, high_start_bin))

    high_power = np.sum(power_spectrum[high_start_bin:])
    tension = (high_power / total_power) * 100.0

    return float(np.clip(tension, 0.0, 100.0))

def compute_primary_emotions(
    hist_stats: HistogramStats,
    per_line: PerLineStats,
    power_spectrum: np.ndarray,
    f_in: float = 10.0,
    high_freq_threshold: float = 5.0,
    freq_band: Tuple[float, float] = (0.1, 10.0),
) -> Tuple[float, float, float]:
    """
    一次性计算所有三个基础情绪参数。

    Returns
    -------
    (aggression, stress, tension) : Tuple[float, float, float]
    """
    e1 = compute_aggression(hist_stats, f_in)
    e2 = compute_stress(per_line)
    e3 = compute_tension(power_spectrum, high_freq_threshold, freq_band)
    return e1, e2, e3
