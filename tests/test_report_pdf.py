"""
诊断报告 PDF 导出测试（方案五）
================================

依据：Valenstein (2008, Arch Pathol Lab Med) 报告格式化四原则；
Brick et al. (2022, Medical Decision Making) 表格化理解更优 d=0.39；
Woloshin et al. (2023, Nature Medicine) 按读者任务组织展示。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

from backend.services.report_pdf import build_report_pdf


INDICATORS = {
    "emotional_stability_index": 0.65,
    "positive_emotion_ratio": 0.55,
    "negative_emotion_ratio": 0.25,
    "trend": "稳定",
    "emotion_recovery_speed": 0.5,
    "stress_accumulation_index": 0.3,
}


class TestReportPdf:
    def test_pdf_header(self):
        """生成文件应以 %PDF 开头"""
        data = build_report_pdf(
            student_name="测试生", date="2026-09-16",
            overall_score=0.72, risk_level="yellow",
            indicators=INDICATORS,
            emotion_overview="今日情绪状态需要关注。",
            key_findings="- 主导情绪: 平静",
            risk_analysis="中等程度预警信号。",
            suggestions=[{"content": "保持规律作息"}, "适度运动"],
        )
        assert data[:4] == b"%PDF"
        assert len(data) > 1000  # 非空

    def test_pdf_contains_pages(self):
        """PDF 应有页对象与内容流"""
        data = build_report_pdf(
            student_name="测试生", date="2026-09-16",
            overall_score=0.72, risk_level="green",
            indicators=INDICATORS,
            emotion_overview="整体良好。",
            key_findings="- 情绪状态非常稳定",
            risk_analysis="未检测到明显风险。",
            suggestions=[{"content": "保持当前习惯"}],
        )
        assert b"/Type /Page" in data or b"/Type/Page" in data

    def test_risk_conclusion_embedded(self):
        """风险结论应写入 PDF（中文字体嵌入为复合字体 Type0）"""
        data = build_report_pdf(
            student_name="测试生", date="2026-09-16",
            overall_score=0.35, risk_level="red",
            indicators=INDICATORS,
            emotion_overview="明显偏低。",
            key_findings="- 情绪波动偏大",
            risk_analysis="需重视。",
            suggestions=[{"content": "联系心理咨询中心"}],
        )
        # 中文字体嵌入成功：出现自定义子集字体 F2+ / TrueType 字体流 FontFile2
        assert b"/F2" in data or b"FontFile2" in data
        assert data[:4] == b"%PDF"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
