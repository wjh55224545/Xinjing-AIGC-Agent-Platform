"""
测试 emotions 模块 — 所有公式的正确性和边界条件。
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from vibraimage.core.histogram import HistogramStats, FrequencyHistogram
from vibraimage.core.spatial_analyzer import SpatialAnalyzer, PerLineStats
from vibraimage.emotions.primary import (
    compute_aggression, compute_stress, compute_tension,
    compute_primary_emotions,
)
from vibraimage.emotions.derived import (
    compute_suspect, compute_balance, compute_charm,
    compute_energy, compute_self_regulation,
    compute_inhibition, compute_neuroticism,
    compute_depression, compute_happiness,
    compute_information_efficiency, compute_energy_characteristic,
)
from vibraimage.emotions.psychophysiological import (
    compute_stability, compute_k_value, interpret_k,
)


def make_test_histogram() -> HistogramStats:
    """创建测试用直方图。"""
    histogram = FrequencyHistogram(n_bins=50)
    # 模拟: 以3Hz为中心的正态分布频率图
    np.random.seed(42)
    freq_map = np.random.normal(3.0, 1.5, (100, 100)).astype(np.float32)
    freq_map = np.clip(freq_map, 0.1, 10.0)
    return histogram.build(freq_map)


def make_test_per_line() -> PerLineStats:
    """创建测试用空间分析结果。"""
    n = 50
    np.random.seed(42)
    # 模拟轻微不对称
    A_L = np.random.uniform(10, 30, n).astype(np.float32)
    A_R = A_L * np.random.uniform(0.8, 1.2, n).astype(np.float32)
    F_L = np.random.uniform(2.0, 5.0, n).astype(np.float32)
    F_R = F_L * np.random.uniform(0.7, 1.3, n).astype(np.float32)
    W_L = A_L.copy()
    W_R = A_R.copy()
    C_L = F_L.copy()
    C_R = F_R.copy()

    return PerLineStats(
        A_L=A_L, A_R=A_R,
        F_L=F_L, F_R=F_R,
        W_L=W_L, W_R=W_R,
        C_L=C_L, C_R=C_R,
        n_lines=n,
    )


# ============================================================================
# E1-E3 Tests
# ============================================================================

def test_e1_aggression():
    """E1 = F_max × σ / (2 × F_in) × 100%"""
    hist = make_test_histogram()
    e1 = compute_aggression(hist, frame_rate=30.0)
    assert 0 <= e1 <= 100, f"E1 out of range: {e1}"
    print(f"  E1 = {e1:.2f}% (F_max={hist.F_max:.2f}, σ={hist.sigma:.2f})")
    print("[PASS] test_e1_aggression passed")


def test_e2_stress():
    """E2: 完全对称 → 接近100%, 不对称 → 降低"""
    per_line = make_test_per_line()
    e2 = compute_stress(per_line)
    assert 0 <= e2 <= 100, f"E2 out of range: {e2}"
    print(f"  E2 = {e2:.2f}%")

    # 完全对称应该接近100%
    n = 10
    identical = np.ones(n, dtype=np.float32) * 10.0
    symmetric = PerLineStats(
        A_L=identical.copy(), A_R=identical.copy(),
        F_L=identical.copy() * 2, F_R=identical.copy() * 2,
        W_L=identical.copy(), W_R=identical.copy(),
        C_L=identical.copy() * 2, C_R=identical.copy() * 2,
        n_lines=n,
    )
    e2_sym = compute_stress(symmetric)
    assert e2_sym > 90, f"Symmetry should give high E2, got {e2_sym}"
    print(f"  完全对称 E2 = {e2_sym:.2f}%")
    print("[PASS] test_e2_stress passed")


def test_e3_tension():
    """E3 = 高频功率 / 总功率"""
    # 模拟: 高频为主的频谱
    n_bins = 50
    power = np.ones(n_bins, dtype=np.float64)
    power[30:] = 10.0  # 高频功率高
    e3 = compute_tension(power, high_freq_threshold=3.0, freq_band=(0.1, 10.0))
    assert 0 <= e3 <= 100, f"E3 out of range: {e3}"
    print(f"  E3 = {e3:.2f}% (高频功率占比)")
    print("[PASS] test_e3_tension passed")


def test_compute_primary_emotions():
    """测试一次性计算三个基础参数。"""
    hist = make_test_histogram()
    per_line = make_test_per_line()
    power = np.ones(50, dtype=np.float64)
    e1, e2, e3 = compute_primary_emotions(hist, per_line, power)
    assert all(0 <= e <= 100 for e in [e1, e2, e3])
    print(f"  E1={e1:.2f}, E2={e2:.2f}, E3={e3:.2f}")
    print("[PASS] test_compute_primary_emotions passed")


# ============================================================================
# E4-E12 Tests
# ============================================================================

def test_e4_suspect():
    """E4 = (E1+E2+E3)/3"""
    e4 = compute_suspect(40, 30, 20)
    assert abs(e4 - 30.0) < 0.01, f"E4 should be 30, got {e4}"
    print(f"  E4 = {e4:.2f}%")

    # 极值关闭算法
    e4_extreme = compute_suspect(80, 70, 60)
    assert e4_extreme >= 70, f"Extreme should trigger clamp, got {e4_extreme}"
    print(f"  极值 E4 = {e4_extreme:.2f}%")
    print("[PASS] test_e4_suspect passed")


def test_e5_balance():
    """E5 = 100 - 2 × Va"""
    e5 = compute_balance(0.0)  # 零变异性 → 100%
    assert e5 > 95, f"Zero variability should give high balance, got {e5}"
    print(f"  E5 (零变异性) = {e5:.2f}%")

    e5_high = compute_balance(0.5)  # 高变异性 → 低平衡
    assert e5_high < 50, f"High variability should give low balance, got {e5_high}"
    print(f"  E5 (高变异性) = {e5_high:.2f}%")
    print("[PASS] test_e5_balance passed")


def test_e7_energy():
    """E7 = (M - σ) / F_ps"""
    e7_high = compute_energy(100, 5, 10)   # 高峰值低离散 → 高活力
    e7_low = compute_energy(10, 20, 10)    # 低峰值高离散 → 低活力
    assert e7_high > e7_low, f"E7: high count should > low count: {e7_high} vs {e7_low}"
    print(f"  E7 (高活力) = {e7_high:.2f}%, E7 (低活力) = {e7_low:.2f}%")
    print("[PASS] test_e7_energy passed")


def test_e8_self_regulation():
    """E8: 稳定 → 高; 波动 → 低"""
    e8_stable = compute_self_regulation(80, 5, 60, 5)   # 低波动
    e8_unstable = compute_self_regulation(40, 60, 30, 40)  # 高波动
    assert e8_stable > e8_unstable, f"Stable should > unstable: {e8_stable} vs {e8_unstable}"
    print(f"  E8 (稳定) = {e8_stable:.2f}%, E8 (不稳定) = {e8_unstable:.2f}%")
    print("[PASS] test_e8_self_regulation passed")


def test_e11_depression():
    """E11 = σ / (0.5 + M)"""
    e11_low = compute_depression(1.0, 5.0)    # 低σ/高M → 低抑郁
    e11_high = compute_depression(5.0, 1.0)   # 高σ/低M → 高抑郁
    assert e11_high > e11_low, f"High sigma should give higher depression: {e11_high} vs {e11_low}"
    print(f"  E11 (低) = {e11_low:.2f}%, E11 (高) = {e11_high:.2f}%")
    print("[PASS] test_e11_depression passed")


def test_e12_happiness():
    """E12 = I / (I + E + ΔI + ΔE)"""
    e12_high = compute_happiness(10, 1, 0, 0)   # 高效能低能量
    e12_low = compute_happiness(1, 10, 0, 0)    # 低效能高能量
    assert e12_high > e12_low, f"High I should give happiness: {e12_high} vs {e12_low}"
    print(f"  E12 (高) = {e12_high:.2f}%, E12 (低) = {e12_low:.2f}%")
    print("[PASS] test_e12_happiness passed")


# ============================================================================
# K-value Test
# ============================================================================

def test_k_value():
    from vibraimage.utils.constants import NORMAL_NORMS, STANDARDIZATION_FACTORS
    params = {k: v for k, v in NORMAL_NORMS.items()}
    K = compute_k_value(params, NORMAL_NORMS, STANDARDIZATION_FACTORS)
    assert abs(K) < 0.01, f"All-normal should give K≈0, got {K}"
    print(f"  K (全常模) = {K:.4f}")
    print(f"  解释: {interpret_k(K)}")
    print("[PASS] test_k_value passed")


# ============================================================================
# Range Tests
# ============================================================================

def test_all_outputs_in_range():
    """测试所有参数输出在[0,100]范围内 (E10除外)。"""
    hist = make_test_histogram()
    per_line = make_test_per_line()
    power = np.ones(50, dtype=np.float64)
    e1, e2, e3 = compute_primary_emotions(hist, per_line, power)

    params = {
        'E1': e1, 'E2': e2, 'E3': e3,
        'E4': compute_suspect(e1, e2, e3),
        'E5': compute_balance(0.1),
        'E6': compute_charm(per_line.W_L, per_line.W_R, per_line.C_L, per_line.C_R, per_line.n_lines),
        'E7': compute_energy(hist.count_max, hist.sigma, 10.0),
        'E8': compute_self_regulation(60, 10, 50, 10),
        'E9': compute_inhibition(0.1, 3.3),
        'E11': compute_depression(hist.sigma, hist.M),
        'E12': compute_happiness(5, 1, 0, 0),
    }

    for name, value in params.items():
        if name == 'E10':
            continue
        assert 0 <= value <= 100, f"{name} out of range: {value:.2f}"

    # E10 may exceed 100%
    e10 = compute_neuroticism(2.0)
    assert e10 > 0, f"E10 should be positive: {e10}"
    print(f"  E10 = {e10:.2f}% (可能超过100%)")

    print("[PASS] test_all_outputs_in_range passed")


if __name__ == '__main__':
    print("E1-E3 Tests...")
    test_e1_aggression()
    test_e2_stress()
    test_e3_tension()
    test_compute_primary_emotions()

    print("\nE4-E12 Tests...")
    test_e4_suspect()
    test_e5_balance()
    test_e7_energy()
    test_e8_self_regulation()
    test_e11_depression()
    test_e12_happiness()

    print("\nK-value Test...")
    test_k_value()

    print("\nRange Test...")
    test_all_outputs_in_range()

    print("\n所有 emotions 测试通过！")
