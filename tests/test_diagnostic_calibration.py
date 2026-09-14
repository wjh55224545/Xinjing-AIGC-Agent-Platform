"""诊断算法校准工具测试（升级 25）"""
import pytest

from backend.services.diagnostic_calibration import (
    run_diagnostic_calibration,
    _level_cn_to_rank,
    _LEVEL_RANK,
)


def test_level_rank_mapping():
    """中文等级 → 数字等级映射正确。"""
    assert _level_cn_to_rank("正常") == 0
    assert _level_cn_to_rank("轻度") == 1
    assert _level_cn_to_rank("中度") == 2
    assert _level_cn_to_rank("重度") == 3
    assert _level_cn_to_rank("未知") == 0  # 兜底
    assert _LEVEL_RANK == {"normal": 0, "mild": 1, "moderate": 2, "severe": 3}


def test_calibration_basic_output():
    """校准返回结构完整、指标在合法区间。"""
    r = run_diagnostic_calibration(seed=42, n_per_profile=5)
    assert r["total_samples"] == 18 * 5
    assert 0 <= r["overall_scale_accuracy"] <= 100
    assert 0 <= r["overall_emotion_accuracy"] <= 100
    assert 0 <= r["sensitivity"] <= 100
    assert 0 <= r["specificity"] <= 100
    assert r["boundary_cases"] >= 0
    assert len(r["profile_details"]) == 18
    assert isinstance(r["interpretation"], str) and r["interpretation"]


def test_calibration_reproducible():
    """同一种子结果可复现。"""
    a = run_diagnostic_calibration(seed=7, n_per_profile=6)
    b = run_diagnostic_calibration(seed=7, n_per_profile=6)
    assert a["overall_scale_accuracy"] == b["overall_scale_accuracy"]
    assert a["overall_emotion_accuracy"] == b["overall_emotion_accuracy"]
    assert a["sensitivity"] == b["sensitivity"]
    assert a["specificity"] == b["specificity"]


def test_calibration_profile_details_fields():
    """每个剖面的明细字段完整。"""
    r = run_diagnostic_calibration(seed=42, n_per_profile=4)
    for d in r["profile_details"]:
        assert d["n"] == 4
        assert 0 <= d["scale_accuracy"] <= 100
        assert 0 <= d["emotion_accuracy"] <= 100
        assert 0 <= d["boundary_cases"] <= d["n"]
        assert d["mean_true_rank"] >= 0


def test_calibration_sensitivity_specificity_healthy():
    """健康对照剖面应体现高特异度（判定为正常）。"""
    r = run_diagnostic_calibration(seed=42, n_per_profile=20)
    healthy = next(d for d in r["profile_details"] if d["profile_id"] == "healthy_control")
    assert healthy["scale_accuracy"] >= 90
    assert r["specificity"] >= 90
