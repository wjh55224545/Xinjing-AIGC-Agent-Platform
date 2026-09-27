"""升级 26-28 测试：诊断一致性统计（ROC AUC）、SJT 情境判断测验、个体多维心理画像"""
import pytest

from backend.services.scale_stats import roc_auc, roc_points
from backend.services.sjt import public_questions, score_sjt
from backend.services.diagnostic_calibration import run_diagnostic_calibration
from backend.services.psychological_profile import build_virtual_profile


# ==================== 升级 26：ROC AUC / 统计检验 ====================

def test_roc_auc_perfect_separation():
    """完全可分数据 AUC=1.0。"""
    scores = [0.95, 0.9, 0.8, 0.3, 0.1, 0.05]
    labels = [True, True, True, False, False, False]
    assert roc_auc(scores, labels) == 1.0


def test_roc_auc_random_chance():
    """无判别力数据 AUC≈0.5（阳性在各分数段均匀分布）。"""
    scores = [0.1, 0.9, 0.2, 0.8, 0.3, 0.7, 0.4, 0.6]
    labels = [True, True, False, False, True, False, True, False]
    assert 0.35 <= roc_auc(scores, labels) <= 0.65


def test_roc_auc_insufficient():
    """单类样本返回 0.0。"""
    assert roc_auc([1.0, 2.0], [True, True]) == 0.0
    assert roc_auc([], []) == 0.0


def test_roc_points_shape():
    """ROC 曲线离散点数量与坐标合法。"""
    scores = [0.9, 0.7, 0.5, 0.3, 0.1, 0.0]
    labels = [True, True, False, True, False, False]
    pts = roc_points(scores, labels, n_points=11)
    assert len(pts) == 11
    for p in pts:
        assert 0 <= p["fpr"] <= 1
        assert 0 <= p["tpr"] <= 1


def test_calibration_statistics_fields():
    """校准报告含统计检验字段与文献基准。"""
    r = run_diagnostic_calibration(seed=42, n_per_profile=8)
    stats = r["statistics"]
    assert 0 <= stats["roc_auc"] <= 1
    assert stats["roc_curve"]  # 非空
    assert -1 <= stats["pearson_r_scale_theta"] <= 1
    assert 0 <= stats["cohen_kappa"] <= 1
    assert stats["is_synthetic"] is True
    assert len(stats["literature_benchmarks"]) >= 3
    # interpretation 应包含 AUC 表述
    assert "AUC" in r["interpretation"] or "ROC" in r["interpretation"]


# ==================== 升级 27：SJT 情境判断测验 ====================

def test_sjt_questions_public_no_scores():
    """公开题库不泄露选项分值。"""
    q = public_questions()
    assert q["questions_count"] == 10
    assert len(q["questions"]) == 10
    assert len(q["dimensions"]) >= 5
    for item in q["questions"]:
        assert len(item["options"]) == 4
        assert "score" not in item["options"][0]  # 选项是字符串，不含分值


def test_sjt_score_full_good():
    """全部选择最优选项（score=3）→ 高分健康。"""
    bank_public = public_questions()
    answers = [{"id": item["id"], "choice": 2} for item in bank_public["questions"]]
    # 需要知道哪个选项 score=3：通过题库内部文件确认第一题最优为选项2
    # 这里用引导式：直接构造每个题最优选项（score=3）
    import json, os
    bank_path = os.path.join(os.path.dirname(__file__), "..", "data", "scales", "SJT.json")
    with open(bank_path, "r", encoding="utf-8") as f:
        bank = json.load(f)
    best = []
    for q in bank["questions"]:
        scores = [o["score"] for o in q["options"]]
        best.append({"id": q["id"], "choice": scores.index(max(scores))})
    r = score_sjt(best)
    assert r["success"] is True
    d = r["data"]
    assert d["total_level"]["level"] == "healthy"
    assert d["total_score"] >= 90
    assert not d["risk_signals"]["low_dims"]


def test_sjt_score_all_poor():
    """全部选择最差选项（score=0）→ 低分需关注。"""
    import json, os
    bank_path = os.path.join(os.path.dirname(__file__), "..", "data", "scales", "SJT.json")
    with open(bank_path, "r", encoding="utf-8") as f:
        bank = json.load(f)
    worst = []
    for q in bank["questions"]:
        scores = [o["score"] for o in q["options"]]
        worst.append({"id": q["id"], "choice": scores.index(min(scores))})
    r = score_sjt(worst)
    assert r["success"] is True
    d = r["data"]
    assert d["total_level"]["level"] == "concern"
    assert len(d["risk_signals"]["low_dims"]) >= 3
    assert d["recommendations"]


def test_sjt_score_partial():
    """混合作答 → 中间分数，维度画像完整。"""
    bank_public = public_questions()
    answers = [{"id": item["id"], "choice": 1} for item in bank_public["questions"]]
    r = score_sjt(answers)
    assert r["success"] is True
    d = r["data"]
    assert 0 <= d["total_score"] <= 100
    assert len(d["dimension_scores"]) == len(d["dimension_levels"]) == len(d["dimension_notes"])
    assert d["method_note"]


def test_sjt_score_empty():
    """空作答 → 失败提示。"""
    r = score_sjt([])
    assert r["success"] is False


# ==================== 升级 28：个体多维心理画像 ====================

def test_virtual_profile_structure():
    """虚拟被试画像包含量表/E1-E12/风险/SJT/诊断一致性五块。"""
    r = build_virtual_profile("mild_anxiety", seed=42)
    assert r["success"] is True
    d = r["data"]
    assert d["is_synthetic"] is True
    assert d["profile_name"] == "轻度焦虑"
    assert d["scale_profile"]["scl90_dimensions"]
    assert d["scale_profile"]["sas_standard_score"] is not None
    assert d["vestibular_profile"]["params"]
    assert len(d["vestibular_profile"]["params"]) == 12  # E1-E12
    assert d["risk"]["overall_level"] in {"low", "medium", "high", "extreme"}
    assert d["sjt_profile"] is not None
    assert "scale_level_match" in d["diagnosis_consistency"]


def test_virtual_profile_reproducible():
    """同种子画像可复现。"""
    a = build_virtual_profile("severe_symptoms", seed=7)
    b = build_virtual_profile("severe_symptoms", seed=7)
    assert a["data"]["scale_profile"]["sas_standard_score"] == b["data"]["scale_profile"]["sas_standard_score"]
    assert a["data"]["vestibular_profile"]["params"][0]["value"] == b["data"]["vestibular_profile"]["params"][0]["value"]


def test_virtual_profile_unknown():
    """未知剖面返回失败。"""
    r = build_virtual_profile("not_exist")
    assert r["success"] is False


def test_virtual_profile_healthy_vs_severe():
    """健康对照风险低于严重症状（画像区分度）。"""
    h = build_virtual_profile("healthy_control", seed=42)["data"]
    s = build_virtual_profile("severe_symptoms", seed=42)["data"]
    assert h["risk"]["overall_level"] != "extreme"
    assert h["risk"]["overall_score"] < s["risk"]["overall_score"]
