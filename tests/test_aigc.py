"""
AIGC模块测试
=============

测试AIGC内容生成器的各项功能。
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestReportGenerator:
    """心理评估报告生成器测试"""

    def test_generate_daily_report(self):
        """测试生成心理评估日报"""
        from backend.aigc.report_generator import ReportGenerator
        gen = ReportGenerator()

        result = gen.generate(
            student_name="张三",
            date="2026-06-13",
            emotion_data={"fused_emotion": "开心", "fused_score": 0.85},
            analysis_result={
                "overall_score": 0.82,
                "risk_level": "green",
                "indicators": {
                    "emotional_stability_index": 0.78,
                    "positive_emotion_ratio": 0.65,
                    "negative_emotion_ratio": 0.15,
                    "trend": "稳定",
                },
                "suggestions": [
                    {"priority": "low", "content": "保持良好状态"},
                ],
            },
        )

        assert "report_type" in result
        assert result["report_type"] == "daily"
        assert result["student_name"] == "张三"
        assert result["risk_level"] == "green"
        assert "report_text" in result
        assert "张三" in result["report_text"]
        assert "心镜" in result["generated_by"]

    def test_generate_weekly_trend(self):
        """测试生成周度趋势分析"""
        from backend.aigc.report_generator import ReportGenerator
        gen = ReportGenerator()

        result = gen.generate_weekly_trend(
            student_name="李四",
            start_date="2026-06-07",
            end_date="2026-06-13",
        )

        assert result["report_type"] == "weekly"
        assert "李四" in result["report_text"]

    def test_score_status(self):
        """测试评分状态判断"""
        from backend.aigc.report_generator import ReportGenerator
        gen = ReportGenerator()

        assert "良好" in gen._get_score_status(0.85)
        assert "关注" in gen._get_score_status(0.55)
        assert "预警" in gen._get_score_status(0.25)


class TestPlanGenerator:
    """干预方案生成器测试"""

    def test_generate_green_plan(self):
        """测试绿色等级干预方案"""
        from backend.aigc.plan_generator import PlanGenerator
        gen = PlanGenerator()

        result = gen.generate(
            student_name="王五",
            risk_level="green",
            risk_factors=[],
            indicators={},
        )

        assert result["risk_level"] == "green"
        assert "plan_text" in result
        assert "王五" in result["plan_text"]
        assert "IP-" in result["plan_id"]

    def test_generate_red_plan(self):
        """测试红色等级干预方案"""
        from backend.aigc.plan_generator import PlanGenerator
        gen = PlanGenerator()

        result = gen.generate(
            student_name="李四",
            risk_level="red",
            risk_factors=["综合评分极低", "频繁情绪突变"],
            indicators={"emotional_stability_index": 0.3},
        )

        assert result["risk_level"] == "red"
        assert "紧急干预" in result["plan_text"]

    def test_plan_id_format(self):
        """测试方案编号格式"""
        from backend.aigc.plan_generator import PlanGenerator
        gen = PlanGenerator()

        plan_id = gen._generate_plan_id("测试学生")
        assert plan_id.startswith("IP-")
        assert len(plan_id) > 10


class TestLetterGenerator:
    """家校沟通函生成器测试"""

    def test_generate_green_letter(self):
        """测试绿色等级沟通函"""
        from backend.aigc.letter_generator import LetterGenerator
        gen = LetterGenerator()

        result = gen.generate(
            student_name="张三",
            risk_level="green",
            emotion_summary="情绪状态良好",
        )

        assert result["risk_level"] == "green"
        assert "needs_review" in result
        assert result["needs_review"] is False
        assert "letter_text" in result

    def test_generate_yellow_letter(self):
        """测试黄色等级沟通函"""
        from backend.aigc.letter_generator import LetterGenerator
        gen = LetterGenerator()

        result = gen.generate(
            student_name="李四",
            risk_level="yellow",
            emotion_summary="情绪有轻微波动",
            suggestions=[{"content": "建议多关注"}],
        )

        assert result["risk_level"] == "yellow"
        assert result["needs_review"] is True

    def test_generate_red_letter(self):
        """测试红色等级沟通函"""
        from backend.aigc.letter_generator import LetterGenerator
        gen = LetterGenerator()

        result = gen.generate(
            student_name="王五",
            risk_level="red",
            emotion_summary="情绪状态异常，需立即关注",
        )

        assert result["risk_level"] == "red"
        assert "紧急" in result["letter_text"]


class TestNarrativeGenerator:
    """成长叙事生成器测试"""

    def test_generate_narrative(self):
        """测试生成成长叙事"""
        from backend.aigc.narrative_generator import NarrativeGenerator
        gen = NarrativeGenerator()

        result = gen.generate(
            student_name="张三",
            period_days=30,
            historical_data={
                "avg_score": 0.75,
                "trend_direction": "改善中",
            },
        )

        assert result["narrative_type"] == "growth"
        assert result["student_name"] == "张三"
        assert result["period_days"] == 30
        assert "narrative_text" in result
        assert "成长足迹" in result["narrative_text"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
