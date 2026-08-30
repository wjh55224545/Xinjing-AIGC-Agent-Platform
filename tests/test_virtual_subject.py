"""
虚拟被试教学闭环测试
=====================
覆盖：剖面库、生成器（隐藏真值）、自动批改（满分/半分/零分）、API 端点。
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.services.virtual_subject import (
    PROFILES, generate_virtual_subject, student_view, grade_diagnosis,
    _LEVEL_CN, _EMOTION_CN,
)


class TestProfiles:
    def test_profiles_count(self):
        assert len(PROFILES) >= 5

    def test_profiles_fields(self):
        for p in PROFILES:
            assert "id" in p and "name" in p and "theta" in p
            assert "dominant_scale" in p

    def test_theta_range(self):
        for p in PROFILES:
            assert -3 <= p["theta"] <= 3


class TestGenerator:
    def test_generate_structure(self):
        subj = generate_virtual_subject("mild_anxiety", seed=1)
        assert subj["is_virtual"] is True
        assert subj["profile_name"] == "轻度焦虑"
        assert "student_view" in subj
        assert "ground_truth" in subj
        assert "scale_answers" in subj["student_view"]
        assert "e_params" in subj["student_view"]

    def test_student_view_hides_truth(self):
        subj = generate_virtual_subject("moderate_anxiety", seed=2)
        view = student_view(subj)
        assert "ground_truth" not in view
        assert "true_level" not in view
        assert "emotion_label" not in view
        assert view["is_virtual"] is True

    def test_unknown_profile_raises(self):
        with pytest.raises(ValueError):
            generate_virtual_subject("nope")

    def test_reproducible(self):
        a = generate_virtual_subject("healthy_control", seed=42)
        b = generate_virtual_subject("healthy_control", seed=42)
        assert a["student_view"]["scale_answers"] == b["student_view"]["scale_answers"]
        assert a["ground_truth"]["true_level"] == b["ground_truth"]["true_level"]

    def test_healthy_vs_severe(self):
        healthy = generate_virtual_subject("healthy_control", seed=1)
        severe = generate_virtual_subject("severe_symptoms", seed=1)
        assert healthy["ground_truth"]["true_level"] in {"normal", "mild"}
        assert severe["ground_truth"]["true_level"] in {"moderate", "severe"}


class TestGrading:
    # 各等级的"满分建议"（包含该等级全部关键词）
    _PERFECT_SUGGESTION = {
        "normal": "保持健康心态，维持规律作息，坚持锻炼，关注身心健康",
        "mild": "注意放松心情，多向朋友倾诉，适当运动调节，持续关注情绪变化",
        "moderate": "建议寻求心理咨询，联系心理老师，进行放松训练，定期评估情绪状态",
        "severe": "应立即转介专业机构，必要时精神科就诊，进行危机干预，并由家人陪同",
    }

    def test_perfect_answer(self):
        subj = generate_virtual_subject("moderate_anxiety", seed=5)
        truth = subj["ground_truth"]
        result = grade_diagnosis(subj, {
            "level_judgment": truth["true_level"],
            "emotion_judgment": truth["emotion_label"],
            "suggestion": self._PERFECT_SUGGESTION[truth["true_level"]],
        })
        assert result["total"] == 100
        assert result["grade"] == "优秀"
        assert all("✅" in f for f in result["feedback"])

    def test_wrong_answer(self):
        subj = generate_virtual_subject("severe_symptoms", seed=3)
        result = grade_diagnosis(subj, {
            "level_judgment": "normal",
            "emotion_judgment": "positive",
            "suggestion": "保持现状即可",
        })
        assert result["total"] < 40
        assert result["grade"] == "需加强"

    def test_adjacent_level_half_score(self):
        subj = generate_virtual_subject("moderate_anxiety", seed=7)
        truth = subj["ground_truth"]
        # 相邻等级
        levels = ["normal", "mild", "moderate", "severe"]
        idx = levels.index(truth["true_level"])
        adjacent = levels[max(0, idx - 1)] if idx > 0 else levels[1]
        result = grade_diagnosis(subj, {
            "level_judgment": adjacent,
            "emotion_judgment": truth["emotion_label"],
            "suggestion": self._PERFECT_SUGGESTION[truth["true_level"]],
        })
        # 等级半分（20）+ 情绪满分（30）+ 建议满分（30）= 80
        assert result["breakdown"]["量表等级判断"] == 20
        assert result["total"] == 80

    def test_suggestion_keywords(self):
        subj = generate_virtual_subject("severe_symptoms", seed=8)
        result = grade_diagnosis(subj, {
            "level_judgment": "severe",
            "emotion_judgment": "severe_negative",
            "suggestion": "应立即转介专业机构，必要时精神科就诊，进行危机干预",
        })
        assert result["breakdown"]["干预建议合理性"] >= 20

    def test_correct_answer_field(self):
        subj = generate_virtual_subject("mild_anxiety", seed=9)
        result = grade_diagnosis(subj, {
            "level_judgment": "normal",
            "emotion_judgment": "positive",
            "suggestion": "无",
        })
        assert "量表等级" in result["correct_answer"]
        assert "情绪状态" in result["correct_answer"]
        assert "建议要点" in result["correct_answer"]


class TestVirtualSubjectAPI:
    def test_profiles_endpoint(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        resp = client.get("/api/virtual-subjects/profiles")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 5
        assert any(p["id"] == "mild_anxiety" for p in data)

    def test_generate_and_grade_flow(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        # 生成
        resp = client.post("/api/virtual-subjects/generate",
                           json={"profile_id": "moderate_anxiety", "seed": 11})
        assert resp.status_code == 200
        subj = resp.json()["data"]
        assert subj["is_virtual"] is True
        assert "ground_truth" not in subj
        # 批改（用正确答案——这里学生不知道真值，但测试里我们用真值验证满分路径）
        # 注意：API 不暴露真值，这里用一个合理答案验证批改流程可用
        resp2 = client.post("/api/virtual-subjects/grade", json={
            "subject_id": subj["subject_id"],
            "level_judgment": "moderate",
            "emotion_judgment": "mild_negative",
            "suggestion": "建议心理咨询，定期评估，放松训练",
        })
        assert resp2.status_code == 200
        grade_data = resp2.json()["data"]
        assert "total" in grade_data
        assert "feedback" in grade_data
        assert "correct_answer" in grade_data

    def test_grade_unknown_subject_404(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        resp = client.post("/api/virtual-subjects/grade", json={
            "subject_id": "VS-NOPE",
            "level_judgment": "normal",
            "emotion_judgment": "positive",
            "suggestion": "无",
        })
        assert resp.status_code == 404
