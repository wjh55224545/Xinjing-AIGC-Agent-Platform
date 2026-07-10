"""
派生情绪参数 — E4-E10, E12。

这些参数由E1/E2/E3和频率直方图统计量计算得出。
每个参数的计算公式来自VCE.pdf第4章。

注意: E11(Depression)虽然编号上是第11个，但直接用频率直方图计算，
不依赖E1-E3，故意放在本模块中。
"""

import numpy as np
from typing import Dict, List, Optional


# ============================================================================
# E4 — Suspect (可疑度)
# ============================================================================

def compute_suspect(e1: float, e2: float, e3: float) -> float:
    """
    计算E4 — Suspect (可疑度/危险性)。

    VCE.pdf p80:
        E4 = E1/3 + E2/3 + E3/3

    三个负性情绪等权组合，用于安检/反恐等场景的单一指标决策。

    极值关闭算法 (p82):
        "additional to equation 6) that sets this value for Suspect level
        at abnormally high values based on Aggression-Stress pair
        and high Aggression level"
        当E1和E2同时很高时，E4被钳位到80%。

    Parameters
    ----------
    e1, e2, e3 : float
        E1 (Aggression), E2 (Stress), E3 (Tension) [0-100]%。

    Returns
    -------
    suspect : float
        可疑度参数 [0-100]%。
    """
    suspect = (e1 + e2 + e3) / 3.0

    # 极值关闭算法: E1 > 70 且 E2 > 60 → 钳位到80%
    if e1 > 70.0 and e2 > 60.0:
        suspect = max(suspect, 80.0)

    return float(np.clip(suspect, 0.0, 100.0))


# ============================================================================
# E5 — Balance (平衡)
# ============================================================================

def compute_balance(variability_sum: float) -> float:
    """
    计算E5 — Balance (平衡/心理平衡)。

    方程(7), VCE.pdf p83:
        E5 = (100 − 2 × Va)%
        Va = Σ SD_i / M_i  (各情绪参数的变异系数之和)

    物理含义 (p83-84):
        - 情绪参数的时间稳定性 = 心理平衡
        - 最小变异性 = 最大平衡
        - Mira y Lopez (1957): "心理不平衡和肌动不平衡是同一个个体过程的两面"

    Parameters
    ----------
    variability_sum : float
        各情绪参数变异系数之和 Va。

    Returns
    -------
    balance : float
        平衡参数 [0-100]%。
    """
    balance = 100.0 - 2.0 * variability_sum * 100.0
    return float(np.clip(balance, 0.0, 100.0))


# ============================================================================
# E6 — Charm (魅力/魅力值)
# ============================================================================

def compute_charm(
    per_line_W_L: np.ndarray,
    per_line_W_R: np.ndarray,
    per_line_C_L: np.ndarray,
    per_line_C_R: np.ndarray,
    n_lines: int,
) -> float:
    """
    计算E6 — Charm/Charisma (魅力)。

    方程(8), VCE.pdf p87:
        E6 = [1 − Σ max(|W_Li−W_Ri|, |C_Li−C_Ri|) / (N × 255)] × 100%

    其中 (根据p87-88说明):
        W_Li, W_Ri = 第i行左右侧振幅分量均值
        C_Li, C_Ri = 第i行左右侧频率分量最大值
        N = 有效行数
        分母255 = 振幅归一化因子 (8-bit灰度范围)

    物理含义 (p87):
        - 与Stress原理相同但处理振幅分量、符号相反
        - 最大运动对称性(频率+振幅) = 高魅力
        - Stress用频率分量, Charm用振幅分量

    Parameters
    ----------
    per_line_W_L, per_line_W_R : np.ndarray
        每行左右侧振幅分量均值。
    per_line_C_L, per_line_C_R : np.ndarray
        每行左右侧频率分量最大值。
    n_lines : int
        有效行数。

    Returns
    -------
    charm : float
        魅力参数 [0-100]%。
    """
    if n_lines == 0:
        return 50.0

    N = float(n_lines)
    # 每行的L/R差异: max(|W_L-W_R|, |C_L-C_R|)
    line_diffs = np.maximum(
        np.abs(per_line_W_L - per_line_W_R),
        np.abs(per_line_C_L - per_line_C_R),
    )

    asymmetry_sum = np.sum(line_diffs)
    charm = (1.0 - asymmetry_sum / (N * 255.0)) * 100.0

    return float(np.clip(charm, 0.0, 100.0))


# ============================================================================
# E7 — Energy (活力)
# ============================================================================

def compute_energy(
    count_max: float,
    sigma: float,
    F_ps: float,
) -> float:
    """
    计算E7 — Energy (活力/能量)。

    方程(9), VCE.pdf p91:
        E7 = (M − σ) / F_ps × 100%

    其中:
        M = 频率直方图峰值计数值 (count_max)
        σ = 频率直方图标准差 [Hz]
        F_ps = 输入频率最大值 (通常为f_max)

    物理含义 (p91-92):
        - 与Aggression同源(频率直方图)
        - 但σ符号相反: 高集中度+低离散度 = 高活力
        - 运动员高活力低攻击(集中)、攻击者高攻击低活力(离散)

    Parameters
    ----------
    count_max : float
        频率直方图峰值计数值。
    sigma : float
        频率直方图标准差 [Hz]。
    F_ps : float
        最大输入频率 [Hz]。

    Returns
    -------
    energy : float
        活力参数 [0-100]%。
    """
    if F_ps <= 0:
        return 0.0

    energy = (count_max - sigma) / F_ps * 100.0
    return float(np.clip(energy, 0.0, 100.0))


# ============================================================================
# E8 — Self-Regulation (自我调节)
# ============================================================================

def compute_self_regulation(
    e5_mean: float,
    e5_range: float,
    e6_mean: float,
    e6_range: float,
) -> float:
    """
    计算E8 — Self-Regulation (自我调节)。

    方程(10), VCE.pdf p95:
        E8 = [1 − (ΔE5 + ΔE6) / (ΔE5 + ΔE6 + E5̄ + E6̄)] × 100%

    物理含义 (p95-96):
        - 正向情绪(E5,E6)越稳定 → 自我调节越高
        - ΔE5, ΔE6 = 参数在测量期间的变化范围
        - E5̄, E6̄ = 参数在测量期间的均值

    Parameters
    ----------
    e5_mean : float
        Balance均值。
    e5_range : float
        Balance变化范围 (max - min)。
    e6_mean : float
        Charm均值。
    e6_range : float
        Charm变化范围 (max - min)。

    Returns
    -------
    self_regulation : float
        自我调节参数 [0-100]%。
    """
    delta_sum = e5_range + e6_range
    total_sum = delta_sum + e5_mean + e6_mean

    if total_sum <= 0:
        return 50.0

    self_reg = (1.0 - delta_sum / total_sum) * 100.0
    return float(np.clip(self_reg, 0.0, 100.0))


# ============================================================================
# E9 — Inhibition (抑制/制动)
# ============================================================================

def compute_inhibition(
    T_m: float,
    T_total: float,
) -> float:
    """
    计算E9 — Inhibition (抑制/制动)。

    方程(11), VCE.pdf p99:
        E9 = T_m(F1) / T × 100%

    物理含义 (p99):
        - T_m = F1参数的平均周期 (F1 = vibraimage变化频率)
        - T = 测量总时长
        - 训练有素者的刺激反应时间约0.1s → E9约10%
        - 反应时间越长 → 抑制越高
        - 受Nyquist-Shannon采样定理限制，取决于帧率

    Parameters
    ----------
    T_m : float
        F1频率变化的平均周期 [s]。
    T_total : float
        测量总时长 [s]。

    Returns
    -------
    inhibition : float
        抑制参数 [0-100]%。
    """
    if T_total <= 0:
        return 0.0

    inhibition = (T_m / T_total) * 100.0
    return float(np.clip(inhibition, 0.0, 100.0))


# ============================================================================
# E10 — Neuroticism (神经质)
# ============================================================================

def compute_neuroticism(e9_std: float) -> float:
    """
    计算E10 — Neuroticism (神经质)。

    方程(12), VCE.pdf p104:
        E10 = 10 × σ(E9) × 100%

    物理含义 (p104-105):
        - σ(E9) = Inhibition值在测量期间的标准差
        - E9和E10共享物理量纲(秒)
        - E10理论上可超过100% (E9周期>10s时)，但仅在系统异常时出现

    Parameters
    ----------
    e9_std : float
        E9 (Inhibition) 在测量时段内的标准差。

    Returns
    -------
    neuroticism : float
        神经质参数 [0-100]% (可超过100%)。
    """
    neuroticism = 10.0 * e9_std * 100.0
    return max(0.0, neuroticism)  # 不clip上界，专著明确说可超过100%


# ============================================================================
# E11 — Depression (抑郁)
# ============================================================================

def compute_depression(
    sigma: float,
    M: float,
    offset: float = 0.5,
) -> float:
    """
    计算E11 — Depression (抑郁)。

    方程(13), VCE.pdf p108:
        E11 = σ / (0.5 + M) × 100%

    物理含义 (p108-109):
        - σ = 频率直方图标准差 [Hz]
        - M = 频率直方图均值 [Hz]
        - 0.5Hz = 病理阈值偏移量
          高于此值的σ指示各种精神病理类型
        - M和σ是任何数学分布的基本特征，频率直方图是
          行为特征中最具信息量的指标之一

    Parameters
    ----------
    sigma : float
        频率直方图标准差 [Hz]。
    M : float
        频率直方图均值 [Hz]。
    offset : float
        病理偏移常数，默认0.5Hz (p108)。

    Returns
    -------
    depression : float
        抑郁参数 [0-100]%。
    """
    denominator = offset + max(M, 0.0)
    if denominator <= 0:
        return 0.0

    depression = (sigma / denominator) * 100.0
    return float(np.clip(depression, 0.0, 100.0))


# ============================================================================
# E12 — Happiness (幸福)
# ============================================================================

def compute_happiness(
    I: float,
    E: float,
    delta_I: float = 0.0,
    delta_E: float = 0.0,
) -> float:
    """
    计算E12 — Happiness (幸福)。

    方程(14), VCE.pdf p112:
        E12 = I / (I + E + ΔI + ΔE) × 100%

    物理含义 (p112-113):
        - I = 信息效能 (正比于1/σ_freq, σ_freq越小效能越高)
        - E = 能量特性 (基于E7)
        - 生物体追求: 最大信息效能 + 最小能量消耗 = 幸福
        - 与Aggression有r=-0.79的强负相关

    Parameters
    ----------
    I : float
        信息效能。
    E : float
        能量特性。
    delta_I : float
        信息效能的变化量。
    delta_E : float
        能量特性的变化量。

    Returns
    -------
    happiness : float
        幸福参数 [0-100]%。
    """
    denominator = I + E + delta_I + delta_E
    if denominator <= 0:
        return 50.0

    happiness = (I / denominator) * 100.0
    return float(np.clip(happiness, 0.0, 100.0))


# ============================================================================
# 信息效能和能量特性的辅助函数
# ============================================================================

def compute_information_efficiency(sigma_freq: float) -> float:
    """
    计算信息效能I。

    VCE.pdf p113:
        "it was proposed to evaluate information efficiency as
        a function of inversely proportional to the standard
        deviation of the frequency component of vibraimage"

    即 I = k / σ_freq，k为比例常数。
    取k=1.0使得I量级在0.1-10范围内。
    """
    if sigma_freq <= 0:
        return 1.0
    return 1.0 / sigma_freq


def compute_energy_characteristic(energy_e7: float) -> float:
    """
    计算能量特性E。

    基于E7值，将[0,100]映射到能量特性空间。
    高E7 = 低能量消耗 (p113: "minimum amount of energy costs")
    """
    return (100.0 - energy_e7) / 100.0  # 归一化到[0,1]
