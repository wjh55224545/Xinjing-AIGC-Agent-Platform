"""
AIGC 报告多轮追问测试（方案四）
================================

依据：治疗性评估协作反馈（Finn & Tonsager 1997）、元分析效应（Poston & Hanson
2010）、反馈干预理论（Kluger & DeNisi 1996）。LLM 未配置时走模板解释，
测试即验证模板解释的证据链质量。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from backend.services.report_followup import answer_followup, _extract_evidence


def _analysis(**overrides):
    a = {
        "overall_score": 0.55,
        "risk_level": "yellow",
        "indicators": {
            "emotional_stability_index": 0.5,
            "positive_emotion_ratio": 0.35,
            "negative_emotion_ratio": 0.4,
            "trend": "下降中",
            "emotion_recovery_speed": 0.3,
            "stress_accumulation_index": 0.65,
        },
    }
    a.update(overrides)
    return a


REPORT = "## 测试生 心理健康评估日报\n综合评分 0.55，黄色·中等风险。"


class TestFollowUp:
    def test_extract_evidence(self):
        """证据链应包含指标数据点"""
        ev = _extract_evidence(_analysis())
        metrics = {e["metric"] for e in ev}
        assert "综合评分" in metrics
        assert "风险等级" in metrics
        assert "积极情绪占比" in metrics
        assert "压力累积指数" in metrics

    def test_risk_question(self):
        """问风险等级 → 回答引用具体指标依据"""
        ans = answer_followup(REPORT, "为什么是黄色风险？", _analysis())["answer"]
        assert "黄色" in ans
        assert "综合评分" in ans
        assert "判定依据" in ans

    def test_ratio_question(self):
        """问积极占比 → 回答引用占比数值"""
        ans = answer_followup(REPORT, "积极情绪占比是多少？", _analysis())["answer"]
        assert "0.35" in ans or "35%" in ans or "35" in ans

    def test_recovery_question(self):
        """问恢复速度 → 回答引用恢复速度与压力累积"""
        ans = answer_followup(REPORT, "恢复速度怎么样？", _analysis())["answer"]
        assert "恢复速度" in ans
        assert "0.3" in ans

    def test_fallback_lists_evidence_chain(self):
        """无法识别的问题 → 兜底列出完整证据链"""
        ans = answer_followup(REPORT, "这是什么奇怪的术语xyz？", _analysis())["answer"]
        assert "证据链" in ans
        assert "综合评分" in ans

    def test_red_risk_question(self):
        """红色风险追问 → 引用评分偏低与负面占比"""
        ans = answer_followup(REPORT, "为什么是红色？", _analysis(
            overall_score=0.32, risk_level="red",
            indicators={"negative_emotion_ratio": 0.6, "emotional_stability_index": 0.2}))["answer"]
        assert "红色" in ans
        assert "0.32" in ans or "偏低" in ans


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
