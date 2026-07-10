"""
心理生理参数 — P14(Stability), P15(Satisfaction)等。

这些参数的特征是它们之间的互相关系数 r < 0.4 (VCE.pdf p117),
与情绪参数(E1-E12)也有意保持低相关性。
"""

import numpy as np
from typing import Dict, List, Optional
from ..core.histogram import HistogramStats


def compute_stability(hist_stats: HistogramStats) -> float:
    """
    计算P14 — Stability (稳定性)。

    方程(16), VCE.pdf p122:
        P14 = 频率直方图与正态分布的拟合度

    物理含义 (p122-123):
        - 心理平衡的稳定状态表现为头部振动分布接近正态分布
        - 显著偏离正态分布 = 低稳定性
        - 频率直方图的形状不依赖于运动的空间特征
          不同面部区域(眼睛高频率,嘴巴中频率,头发低频率)
          的总和分布在稳定状态下接近正态

    Parameters
    ----------
    hist_stats : HistogramStats
        频率直方图统计量。

    Returns
    -------
    stability : float
        稳定性参数 [0-100]%。
    """
    from scipy import stats

    if hist_stats.total_pixels == 0:
        return 0.0

    x = hist_stats.bin_centers
    y_actual = hist_stats.histogram.astype(np.float64)
    total = np.sum(y_actual)

    if total == 0:
        return 0.0

    # 正态分布参考值: N(M, σ²)
    sigma = max(hist_stats.sigma, 0.01)
    y_normal = stats.norm.pdf(x, loc=hist_stats.M, scale=sigma)
    y_normal_scaled = y_normal * (total / max(np.sum(y_normal), 1e-10))

    # K = Σ y'(x) / Σ y(x) (方程16)
    # 等价于 1 - L1_norm(y_actual, y_normal)
    l1_norm = np.sum(np.abs(y_actual - y_normal_scaled)) / total
    stability = max(0.0, (1.0 - l1_norm) * 100.0)

    return float(np.clip(stability, 0.0, 100.0))


def compute_satisfaction(
    pps_before: Dict[str, float],
    pps_after: Dict[str, float],
) -> float:
    """
    计算P15 — Satisfaction (满意度)。

    方程(17), VCE.pdf p126:
        P15 = PPS_after − PPS_before

    物理含义 (p126):
        - 刺激前后PPS(心理生理状态)的变化
        - PPS可以用单一数值表示 (如K值的简化版)
        - 正值 = 正面反应, 负值 = 负面反应

    Parameters
    ----------
    pps_before : dict
        刺激前的心理生理状态 (包含各情绪参数值)。
    pps_after : dict
        刺激后的心理生理状态。

    Returns
    -------
    satisfaction : float
        满意度 (正=满意, 负=不满意)。
    """
    # 用所有参数的加权和作为PPS的简化表示
    # PPS ≈ Σ(归一化参数值)

    def pps_score(params: Dict[str, float]) -> float:
        """简单的PPS评分: 正向情绪权重+1, 负向情绪权重-1"""
        positive = ['balance', 'charm', 'energy', 'self_regulation', 'happiness']
        negative = ['aggression', 'stress', 'tension', 'suspicious', 'depression']

        score = 0.0
        count = 0

        for k, v in params.items():
            if k in positive:
                score += v
                count += 1
            elif k in negative:
                score -= v
                count += 1

        return score / max(count, 1)

    before_score = pps_score(pps_before)
    after_score = pps_score(pps_after)

    return after_score - before_score


def compute_k_value(
    params: Dict[str, float],
    norms: Dict[str, float],
    factors: Dict[str, float],
) -> float:
    """
    计算K值 — 综合心理状态指标 (顾红梅论文, p2)。

    K = Σ m_i × (T_i − T_n_i)

    其中:
        T_i  = 参数i的测量值
        T_n_i = 参数i的常模值
        m_i  = 标准化因子 (= 1/SD_i)

    K值解释:
        |K| < 3: 稳定，接近常模
        3 ≤ |K| < 6: 轻度偏离，建议关注
        |K| ≥ 6: 显著偏离，建议专业干预

    Parameters
    ----------
    params : dict
        各情绪参数的测量值。
    norms : dict
        各参数的常模值。
    factors : dict
        各参数的标准化因子。

    Returns
    -------
    K : float
        综合心理状态指标。
    """
    K = 0.0
    for param_name, value in params.items():
        if param_name in norms and param_name in factors:
            T_n = norms[param_name]
            m = factors[param_name]
            K += m * (value - T_n)

    return K


def interpret_k(K: float) -> str:
    """
    解释K值的含义。

    Returns
    -------
    interpretation : str
    """
    abs_K = abs(K)
    if abs_K < 3:
        return f"K={K:.2f}: 稳定 — 接近常模，无明显异常"
    elif abs_K < 6:
        return f"K={K:.2f}: 轻度偏离 — 建议关注"
    else:
        return f"K={K:.2f}: 显著偏离 — 建议专业干预"
