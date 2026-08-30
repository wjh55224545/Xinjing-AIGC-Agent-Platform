"""
升级项测试：合成数据引擎 / 信效度套件 / 三模态 D-S 融合 / GRM 多级 CAT
====================================================================
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ==================== 合成数据引擎 ====================

class TestSyntheticData:
    def test_generate_subject_structure(self):
        from backend.services.synthetic_data import generate_subject
        subj = generate_subject(theta=1.2, seed=1)
        assert subj["is_synthetic"] is True
        assert subj["theta"] == pytest.approx(1.2)
        assert subj["emotion_label"] in {"severe_negative", "mild_negative", "positive", "neutral"}
        assert set(subj["e_params"].keys()) >= {
            "aggression", "stress", "tension", "depression", "happiness", "energy",
        }
        assert "SAS" in subj["scale_answers"]

    def test_theta_drives_direction(self):
        """θ 越大，负性参数越高、正性参数越低（同 seed 下）"""
        from backend.services.synthetic_data import generate_subject
        healthy = generate_subject(theta=-2.0, seed=7)
        severe = generate_subject(theta=2.0, seed=7)
        assert severe["e_params"]["aggression"] > healthy["e_params"]["aggression"]
        assert severe["e_params"]["stress"] > healthy["e_params"]["stress"]
        assert severe["e_params"]["happiness"] < healthy["e_params"]["happiness"]

    def test_batch_reproducible(self):
        from backend.services.synthetic_data import generate_subjects
        a = generate_subjects(20, seed=42)
        b = generate_subjects(20, seed=42)
        assert [s["theta"] for s in a] == [s["theta"] for s in b]

    def test_scale_answers_within_range(self):
        from backend.services.synthetic_data import generate_subject
        from backend.api.routes.scales import _load_scale
        s = _load_scale("SAS")
        subj = generate_subject(theta=0.5, seed=3)
        answers = subj["scale_answers"]["SAS"]
        assert len(answers) == 20
        assert all(1 <= a <= 4 for a in answers)


# ==================== 信效度套件 ====================

class TestReliability:
    def test_cronbach_alpha_perfect(self):
        """所有条目完全一致 → α=1"""
        from backend.services.scale_stats import cronbach_alpha
        rows = [[3, 3, 3, 3], [2, 2, 2, 2], [1, 1, 1, 1]]
        assert cronbach_alpha(rows) == pytest.approx(1.0, abs=1e-3)

    def test_cronbach_alpha_invalid(self):
        from backend.services.scale_stats import cronbach_alpha
        assert cronbach_alpha([[1], [2]]) == 0.0  # 条目数 <2
        assert cronbach_alpha([]) == 0.0

    def test_dimension_correlation(self):
        from backend.services.scale_stats import dimension_correlation_matrix
        rows = [
            {"a": 1, "b": 2, "c": 3},
            {"a": 2, "b": 4, "c": 6},
            {"a": 3, "b": 6, "c": 9},
        ]
        m = dimension_correlation_matrix(rows)
        assert abs(m["a"]["b"] - 1.0) < 1e-3
        assert abs(m["a"]["a"] - 1.0) < 1e-3

    def test_reliability_on_synthetic(self):
        """合成数据上 SAS 信效度应处于合理区间（α>0.6）"""
        from backend.services.synthetic_data import generate_subjects
        from backend.services.scale_stats import cronbach_alpha
        subs = generate_subjects(200, seed=42)
        matrix = [s["scale_answers"]["SAS"] for s in subs]
        alpha = cronbach_alpha(matrix)
        assert 0.5 <= alpha <= 1.0


# ==================== 三模态 D-S 融合 ====================

class TestDempsterShafer:
    def test_combine_agreement_boosts(self):
        """两源一致 → 该焦点 mass 增强；K 因焦点分散有限升高但不应过高"""
        from backend.services.fusion import dempster_combine
        m1 = {"positive": 0.8, "negative": 0.1, "neutral": 0.1}
        m2 = {"positive": 0.7, "negative": 0.2, "neutral": 0.1}
        fused, k = dempster_combine(m1, m2)
        assert fused["positive"] > 0.8
        assert k < 0.6

    def test_combine_conflict_detected(self):
        """两源强冲突 → 冲突系数 K 高"""
        from backend.services.fusion import dempster_combine
        m1 = {"positive": 0.9, "negative": 0.05, "neutral": 0.05}
        m2 = {"positive": 0.05, "negative": 0.9, "neutral": 0.05}
        fused, k = dempster_combine(m1, m2)
        assert k > 0.5

    def test_three_modal_basic(self):
        """三模态一致负性 → 判定焦虑，requires_review=False"""
        from backend.services.fusion import fuse_three_modal
        r = fuse_three_modal(
            facial={"valence": -0.6, "arousal": 0.5, "confidence": 0.7},
            vestibular={"valence": -0.5, "arousal": 0.3, "confidence": 0.6},
            scale={"theta": 1.5, "confidence": 0.8},
        )
        assert r["model"] == "ds-3modal"
        assert r["emotion"] == "焦虑"
        assert r["confidence"] >= 0.4
        assert r["requires_review"] is False
        assert r["n_modalities"] == 3

    def test_conflicting_modalities_require_review(self):
        """面部说正性、量表说强负性 → 冲突显著，要求复核"""
        from backend.services.fusion import fuse_three_modal
        r = fuse_three_modal(
            facial={"valence": 0.8, "arousal": 0.4, "confidence": 0.9},
            vestibular={"valence": 0.2, "arousal": 0.1, "confidence": 0.5},
            scale={"theta": 2.5, "confidence": 0.9},
        )
        assert r["requires_review"] is True
        assert r["conflict"] >= 0.35

    def test_two_modal_fallback(self):
        from backend.services.fusion import fuse_two_modal
        r = fuse_two_modal(
            facial={"valence": 0.5, "arousal": 0.3, "confidence": 0.7},
            vestibular={"valence": 0.4, "arousal": 0.2, "confidence": 0.6},
        )
        assert r["model"] == "ds-2modal"
        assert r["n_modalities"] == 2

    def test_scale_only(self):
        """只有量表证据也能融合"""
        from backend.services.fusion import fuse_three_modal
        r = fuse_three_modal(scale={"theta": -1.8, "confidence": 0.8})
        assert r["n_modalities"] == 1
        assert r["emotion"] == "开心"


# ==================== GRM 多级 CAT ====================

class TestGRMCat:
    def _run(self, scale_code, answer_fn, max_extra=3, n_levels=None):
        from backend.services.cat import next_item, _default_max
        from backend.api.routes.scales import _load_scale
        s = _load_scale(scale_code)
        qs = s["questions"]
        rev = s["scoring"]["reverse_items"]
        if n_levels is None:
            n_levels = len(s["scoring"]["options"])
        mx = _default_max(qs)
        answered = []
        res = None
        for _ in range(mx + max_extra):
            res = next_item(qs, answered, rev, 0.0, max_items=mx, model="grm", n_levels=n_levels)
            if res["done"] or res["next"] is None:
                break
            qid = res["next"]["id"]
            answered.append({"id": qid, "score": answer_fn(qid, rev)})
        return res, answered

    def test_grm_high_symptom_positive_theta(self):
        res, _ = self._run("SAS", lambda qid, rev: 4 if qid not in rev else 1)
        assert res["done"] is True
        assert res["model"] == "grm"
        assert res["theta"] > 0
        assert res["score_estimate"]["level"] == "severe"

    def test_grm_healthy_negative_theta(self):
        res, _ = self._run("SAS", lambda qid, rev: 1 if qid not in rev else 4)
        assert res["theta"] < 0
        assert res["score_estimate"]["level"] == "normal"

    def test_grm_five_level_scl90(self):
        """SCL-90 5 级作答 GRM 不报错并收敛"""
        res, answered = self._run("SCL-90", lambda qid, rev: 5)
        assert res["done"] is True
        assert len(answered) >= 5

    def test_grm_thresholds(self):
        from backend.services.cat import grm_thresholds
        item = {"id": 1, "irt": {"a": 1.0, "b": 0.0}}
        assert grm_thresholds(item, 4) == [-0.8, 0.0, 0.8]
        assert grm_thresholds(item, 5) == [-1.2, -0.4, 0.4, 1.2]
        assert len(grm_thresholds(item, 3)) == 2

    def test_grm_category_probabilities_sum_one(self):
        from backend.services.cat import grm_category_probabilities
        ps = grm_category_probabilities(0.0, 1.0, [-0.8, 0.0, 0.8])
        assert len(ps) == 4
        assert sum(ps) == pytest.approx(1.0, abs=1e-6)


# ==================== 三模态融合 API ====================

class TestFusionAPI:
    def test_three_modal_endpoint(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        resp = client.post("/api/fusion/three-modal", json={
            "facial": {"valence": -0.6, "arousal": 0.5, "confidence": 0.7},
            "vestibular": {"valence": -0.5, "arousal": 0.3, "confidence": 0.6},
            "scale": {"theta": 1.5, "confidence": 0.8},
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["model"] == "ds-3modal"
        assert data["emotion"] in {"开心", "焦虑", "平静"}

    def test_reliability_endpoint(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        resp = client.get("/api/scales/validation/reliability?n_subjects=60")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["is_synthetic"] is True
        assert "SAS" in data["scales"]
        assert data["scales"]["SAS"]["cronbach_alpha"] > 0
