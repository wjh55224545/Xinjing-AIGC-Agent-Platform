"""
AIGC 报告质量修复测试（方案一）
=================================

针对湖北大学心理学系专家评估暴露的缺陷：
1. 数据-结论一致性（"积极占比20%却称接近满分"/"积极占比52.3%却判高风险"）
2. 指标表缺项（风险等级/情绪恢复速度/压力累积）
3. 共情措辞与矛盾表述
4. 按主导情绪生成个性化建议
5. 全中文（无英文残留）
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.aigc.report_generator import ReportGenerator

gen = ReportGenerator()


# ---------- 1. 一致性校验 ----------

class TestConsistencyCheck:
    def test_detects_positive_ratio_vs_red_risk(self):
        """积极占比≥50% 与红色高风险 → 应检出矛盾（专家 R05 场景）"""
        issues = gen._check_consistency(
            overall_score=0.35, risk_level="red", positive_ratio=0.523,
        )
        assert any("积极情绪占比≥50%" in i for i in issues)

    def test_detects_high_score_vs_low_positive(self):
        """综合评分≥0.7 与积极占比<30% → 应检出矛盾（专家 R03 场景）"""
        issues = gen._check_consistency(
            overall_score=0.8, risk_level="green", positive_ratio=0.2,
        )
        assert any("综合评分≥0.7与积极情绪占比<30%" in i for i in issues)

    def test_no_issue_when_consistent(self):
        """数据一致时不应检出矛盾"""
        issues = gen._check_consistency(
            overall_score=0.85, risk_level="green", positive_ratio=0.7,
            negative_ratio=0.1, stability=0.8, trend="稳定",
        )
        assert issues == []


# ---------- 2. 指标表补全 ----------

class TestIndicatorTable:
    def _build_report(self, **overrides):
        analysis = {
            "overall_score": 0.72,
            "risk_level": "yellow",
            "indicators": {
                "emotional_stability_index": 0.65,
                "positive_emotion_ratio": 0.55,
                "negative_emotion_ratio": 0.25,
                "trend": "稳定",
                "emotion_recovery_speed": 0.5,
                "stress_accumulation_index": 0.3,
                "emotion_distribution": {"开心": 3, "平静": 2, "焦虑": 1},
            },
        }
        analysis.update(overrides)
        return gen.generate(
            student_name="测试生",
            date="2026-09-16",
            emotion_data={"fused_emotion": "开心", "fused_score": 0.72},
            analysis_result=analysis,
        )

    def test_template_has_full_indicator_table(self):
        """指标表应含风险等级/情绪恢复速度/压力累积（专家点名缺失项）"""
        result = self._build_report()
        text = result["report_text"]
        assert "风险等级" in text
        assert "情绪恢复速度" in text
        assert "压力累积" in text
        assert "情绪趋势" in text

    def test_risk_level_rendered(self):
        """风险等级中文名应渲染"""
        result = self._build_report(risk_level="red")
        assert "红色 · 高风险" in result["report_text"]
        result = self._build_report(risk_level="green")
        assert "绿色 · 低风险" in result["report_text"]


# ---------- 3. 数据-结论一致性（模板文案） ----------

class TestTemplateConsistency:
    def test_low_positive_ratio_does_not_say_good(self):
        """积极占比低 + 评分高 → 概览不得写"整体良好"（专家 R03 场景）"""
        result = gen.generate(
            student_name="测试生",
            date="2026-09-16",
            emotion_data={"fused_emotion": "平静", "fused_score": 0.75},
            analysis_result={
                "overall_score": 0.75,
                "risk_level": "green",
                "indicators": {
                    "emotional_stability_index": 0.7,
                    "positive_emotion_ratio": 0.2,
                    "negative_emotion_ratio": 0.3,
                    "trend": "稳定",
                    "emotion_recovery_speed": 0.5,
                    "stress_accumulation_index": 0.3,
                },
            },
        )
        text = result["report_text"]
        assert "整体良好" not in text

    def test_stable_and_volatile_not_contradictory(self):
        """稳定性高 + 熵高 → 关键发现不得同时写"稳定"与"波动大"（专家 R01 场景）"""
        result = gen.generate(
            student_name="测试生",
            date="2026-09-16",
            emotion_data={"fused_emotion": "开心", "fused_score": 0.75},
            analysis_result={
                "overall_score": 0.75,
                "risk_level": "green",
                "indicators": {
                    "emotional_stability_index": 0.75,
                    "positive_emotion_ratio": 0.6,
                    "negative_emotion_ratio": 0.2,
                    "trend": "稳定",
                    "emotion_fluctuation_entropy": 0.8,
                    "emotion_recovery_speed": 0.5,
                    "stress_accumulation_index": 0.2,
                },
            },
        )
        text = result["report_text"]
        assert "波动偏大" not in text  # 稳定性高时不得写"波动偏大"

    def test_warm_wording_for_yellow_risk(self):
        """黄色风险分析应有建设性/安抚措辞，而非制造焦虑"""
        result = gen.generate(
            student_name="测试生",
            date="2026-09-16",
            emotion_data={"fused_emotion": "焦虑", "fused_score": 0.55},
            analysis_result={
                "overall_score": 0.55,
                "risk_level": "yellow",
                "risk_factors": ["情绪波动偏大"],
                "indicators": {
                    "emotional_stability_index": 0.5,
                    "positive_emotion_ratio": 0.4,
                    "negative_emotion_ratio": 0.35,
                    "trend": "下降中",
                    "emotion_recovery_speed": 0.4,
                    "stress_accumulation_index": 0.45,
                },
            },
        )
        text = result["report_text"]
        assert "不必过度紧张" in text or "自我调节" in text


# ---------- 4. 个性化建议 ----------

class TestPersonalizedSuggestions:
    def test_dominant_emotion_suggestions(self):
        """按主导情绪生成定制建议（专家评语：建议偏普适）"""
        result = gen.generate(
            student_name="测试生",
            date="2026-09-16",
            emotion_data={"fused_emotion": "焦虑", "fused_score": 0.6},
            analysis_result={
                "overall_score": 0.6,
                "risk_level": "yellow",
                "indicators": {
                    "emotional_stability_index": 0.55,
                    "positive_emotion_ratio": 0.4,
                    "negative_emotion_ratio": 0.35,
                    "trend": "稳定",
                    "emotion_recovery_speed": 0.5,
                    "stress_accumulation_index": 0.4,
                    "emotion_distribution": {"焦虑": 4, "平静": 2, "开心": 1},
                },
            },
        )
        text = result["report_text"]
        assert "深呼吸" in text          # 焦虑专属建议
        assert "区分" in text or "具体写下来" in text

    def test_green_keeps_habit_suggestion(self):
        """绿色等级应有巩固类建议"""
        result = gen.generate(
            student_name="测试生",
            date="2026-09-16",
            emotion_data={"fused_emotion": "开心", "fused_score": 0.82},
            analysis_result={
                "overall_score": 0.82,
                "risk_level": "green",
                "indicators": {
                    "emotional_stability_index": 0.8,
                    "positive_emotion_ratio": 0.7,
                    "negative_emotion_ratio": 0.1,
                    "trend": "改善中",
                    "emotion_recovery_speed": 0.7,
                    "stress_accumulation_index": 0.15,
                    "emotion_distribution": {"开心": 5, "平静": 2},
                },
            },
        )
        text = result["report_text"]
        assert "规律作息" in text or "保持" in text


# ---------- 5. 全中文（消除英文残留） ----------

class TestNoEnglishResidue:
    def _english_chars(self, text: str) -> list:
        import re
        # 允许必要符号与术语白名单（Markdown 语法、emoji、数字、量表缩写）
        allowed = {"Markdown", "95%", "IP-", "Gitee.AI", "MetaX", "GPU", "emoji",
                   "PHQ", "SDS", "SAS", "GAD", "CBT", "NICE", "AI", "AIGC"}
        words = re.findall(r"[A-Za-z][A-Za-z0-9.\-]*", text)
        return [w for w in words if w not in allowed]

    def test_template_report_no_english(self):
        """模板报告正文不应有英文残留（专家评语：明日预测处混入英文）"""
        result = gen.generate(
            student_name="测试生",
            date="2026-09-16",
            emotion_data={"fused_emotion": "平静", "fused_score": 0.7},
            analysis_result={
                "overall_score": 0.7,
                "risk_level": "green",
                "indicators": {
                    "emotional_stability_index": 0.7,
                    "positive_emotion_ratio": 0.6,
                    "negative_emotion_ratio": 0.2,
                    "trend": "稳定",
                    "emotion_recovery_speed": 0.6,
                    "stress_accumulation_index": 0.2,
                },
            },
        )
        residue = self._english_chars(result["report_text"])
        assert residue == [], f"报告存在英文残留: {residue}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
