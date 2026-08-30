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
    frame_rate: float = 30.0,
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
    frame_rate : float
        输入帧率 [fps] (F_in in the formula)。

    Returns
    -------
    aggression : float
        攻击性参数 [0-100]%。
    """
    if hist_stats.total_pixels == 0 or frame_rate <= 0:
        return 0.0

    F_max = max(hist_stats.F_max, 0.01)  # 避免除零
    sigma = hist_stats.sigma

    # E1 = F_max × σ / (2 × F_in) × 100%
    aggression = (F_max * sigma) / (2.0 * frame_rate) * 100.0

    return float(np.clip(aggression, 0.0, 100.0))


def compute_stress(per_line: PerLineStats) -> float:
    """
    计算E2 — Stress (压力)。

    方程(4), VCE.pdf p71:
        E2 = [1 − (Σ|A_Li−A_Ri|/(2n·A_max) + Σ|F_Li−F_Ri|/(2n·F_max))] × 100%

    物理含义 (p71-72):
        - A_Li, A_Ri: 第i行左右侧振动振幅总量
        - F_Li, F_Ri: 第i行左右侧最大振动频率
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
    A_max = max(per_line.A_max, 1e-6)
    F_max = max(per_line.F_max, 1e-6)

    # 振幅不对称项: Σ|A_Li − A_Ri| / (2n × A_max)
    amp_asym_sum = np.sum(np.abs(per_line.A_L - per_line.A_R))
    amp_term = amp_asym_sum / (2.0 * n * A_max)

    # 频率不对称项: Σ|F_Li − F_Ri| / (2n × F_max)
    freq_asym_sum = np.sum(np.abs(per_line.F_L - per_line.F_R))
    freq_term = freq_asym_sum / (2.0 * n * F_max)

    # E2 = [1 - (amp_term + freq_term)] × 100%
    asymmetry = amp_term + freq_term
    stress = (1.0 - asymmetry) * 100.0

    return float(np.clip(stress, 0.0, 100.0))


def compute_tension(
    power_spectrum: np.ndarray,
    high_freq_threshold: float = 3.0,
    freq_band: Tuple[float, float] = (0.1, 10.0),
) -> float:
    """
    计算E3 — Tension/Anxiety (紧张/焦虑)。

    方程(5), VCE.pdf p75:
        E3 = [Σ_{f=f_threshold}^{f_max} P(f_i)] / [Σ_{f=0.1}^{f_max} P(f_i)] × 100%

    物理含义 (p75-76):
        - P(f_i): 振动频谱功率
        - 高频振动密度高 = 紧张/焦虑
        - 与EEG检测焦虑的β波分析方法类似
        - 三个负性情绪参数从三个正交维度:
          Aggression → 统计特征(均值+标准差)
          Stress → 空间特征(对称性)
          Tension → 频率特征(高频比例)

    Parameters
    ----------
    power_spectrum : np.ndarray, shape (n_bins,)
        聚合频谱功率分布。
    high_freq_threshold : float
        高频分界点 [Hz]。默认3.0Hz。
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
    frame_rate: float = 30.0,
    high_freq_threshold: float = 3.0,
    freq_band: Tuple[float, float] = (0.1, 10.0),
) -> Tuple[float, float, float]:
    """
    一次性计算所有三个基础情绪参数。

    Returns
    -------
    (aggression, stress, tension) : Tuple[float, float, float]
    """
    e1 = compute_aggression(hist_stats, frame_rate)
    e2 = compute_stress(per_line)
    e3 = compute_tension(power_spectrum, high_freq_threshold, freq_band)
    return e1, e2, e3
