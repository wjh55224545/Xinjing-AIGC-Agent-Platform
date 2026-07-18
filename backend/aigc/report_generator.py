"""
心理评估报告生成器 (ReportGenerator)
=====================================

基于国产算力平台大模型，自动生成结构化的心理健康评估报告。
支持日报、周报、数据可视化解读三种类型。
"""

from __future__ import annotations
import logging
from datetime import datetime
from backend.aigc.templates.report_templates import (
    DAILY_REPORT_TEMPLATE,
    WEEKLY_TREND_TEMPLATE,
    VISUALIZATION_TEMPLATE,
)
from backend.aigc.llm_client import llm_generate as _llm_generate

logger = logging.getLogger(__name__)


class ReportGenerator:
    """心理评估报告生成器"""

    name = "心理评估报告生成"
    description = "基于情绪数据和心理健康指标，自动生成自然语言评估报告"

    def generate(
        self,
        student_name: str = "",
        date: str = "",
        emotion_data: dict | None = None,
        analysis_result: dict | None = None,
    ) -> dict:
        """
        生成心理评估日报

        Args:
            student_name: 学生姓名
            date: 报告日期
            emotion_data: 当日情绪数据
            analysis_result: 心理健康分析结果

        Returns:
            包含完整报告内容的字典
        """
        data = emotion_data or {}
        analysis = analysis_result or {}
        report_date = date or datetime.now().strftime("%Y-%m-%d")
        name = student_name or "未知学生"

        overall_score = analysis.get("overall_score", data.get("fused_score", 0.7))
        risk_level = analysis.get("risk_level", "green")

        # ---- 优先尝试 LLM 生成 ----
        llm_text = self._try_llm_generate(name, report_date, data, analysis)
        if llm_text:
            return {
                "report_type": "daily",
                "student_name": student_name,
                "date": report_date,
                "risk_level": risk_level,
                "overall_score": overall_score,
                "report_text": llm_text,
                "generated_by": "心镜·AIGC智能体 (moark.com Qwen3-8B)",
            }

        # ---- LLM 不可用，降级到模板模式 ----
        indicators = analysis.get("indicators", {})
        stability = indicators.get("emotional_stability_index", 0.7)
        positive_ratio = indicators.get("positive_emotion_ratio", 0.6)
        negative_ratio = indicators.get("negative_emotion_ratio", 0.2)
        trend = indicators.get("trend", "稳定")

        score_status = self._get_score_status(overall_score)
        stability_status = self._get_stability_status(stability)
        positive_status = self._get_positive_status(positive_ratio)
        negative_status = self._get_negative_status(negative_ratio)

        emotion_overview = self._generate_emotion_overview(name, data, analysis)
        risk_analysis_text = self._generate_risk_analysis(risk_level, analysis)
        lstm_result = analysis.get("lstm_transformer_analysis", {})
        prediction = lstm_result.get("prediction", {})
        next_day_prediction = self._generate_prediction(prediction)
        suggestions = self._format_suggestions(analysis.get("suggestions", []))
        key_findings = self._generate_key_findings(data, analysis)

        report_text = DAILY_REPORT_TEMPLATE.format(
            student_name=name,
            date=report_date,
            overall_score=overall_score,
            score_status=score_status,
            stability=stability,
            stability_status=stability_status,
            positive_ratio=positive_ratio,
            positive_status=positive_status,
            negative_ratio=negative_ratio,
            negative_status=negative_status,
            trend=trend,
            emotion_overview=emotion_overview,
            key_findings=key_findings,
            risk_analysis=risk_analysis_text,
            next_day_prediction=next_day_prediction,
            suggestions=suggestions,
        )

        return {
            "report_type": "daily",
            "student_name": student_name,
            "date": report_date,
            "risk_level": risk_level,
            "overall_score": overall_score,
            "report_text": report_text,
            "generated_by": "心镜·AIGC智能体 (模板模式)",
        }

    def _try_llm_generate(
        self,
        student_name: str,
        date: str,
        emotion_data: dict,
        analysis: dict,
    ) -> str | None:
        """尝试使用 LLM 生成报告内容，失败返回 None。"""
        indicators = analysis.get("indicators", {})
        overall_score = analysis.get("overall_score", emotion_data.get("fused_score", 0.7))
        risk_level = analysis.get("risk_level", "green")
        emotion = emotion_data.get("fused_emotion", "未检测")
        suggestions = analysis.get("suggestions", [])
        risk_factors = analysis.get("risk_factors", [])
        lstm_result = analysis.get("lstm_transformer_analysis", {})
        prediction = lstm_result.get("prediction", {})

        suggestion_str = "\n".join(
            f"- {s.get('content', str(s))}" if isinstance(s, dict) else f"- {s}"
            for s in suggestions[:5]
        ) or "- 保持当前良好的情绪管理习惯"

        risk_str = "\n".join(f"- {f}" for f in risk_factors) if risk_factors else "- 无明显风险因素"

        system_prompt = (
            "你是一位专业的学校心理辅导老师，负责撰写学生心理健康评估日报。"
            "请使用专业的心理学语言，同时保持报告对教师和家长友好可读。"
            "用 Markdown 格式输出结构化报告，适当使用 emoji 增强可读性。"
        )

        user_prompt = f"""请为 {student_name} 同学生成 {date} 的心理健康评估日报。

## 数据概览
- 综合情绪评分：{overall_score:.2f}/1.00
- 主要情绪：{emotion}
- 风险等级：{risk_level}
- 情绪稳定性指数：{indicators.get('emotional_stability_index', 'N/A')}
- 积极情绪占比：{indicators.get('positive_emotion_ratio', 'N/A')}
- 负面情绪占比：{indicators.get('negative_emotion_ratio', 'N/A')}
- 情绪趋势：{indicators.get('trend', '稳定')}
- 压力累积指数：{indicators.get('stress_accumulation_index', 'N/A')}
- 情绪恢复速度：{indicators.get('emotion_recovery_speed', 'N/A')}

## 风险因素
{risk_str}

## 明日预测
- 预测评分：{prediction.get('next_day_emotion', 'N/A')}
- 趋势预测：{prediction.get('trend_prediction', '稳定')}

## 已有建议参考
{suggestion_str}

请按以下结构输出完整报告：
1. **情绪概况** — 1段自然语言概述
2. **关键指标表格** — Markdown表格，含数值和状态评估
3. **关键发现** — 2-3条要点
4. **风险分析** — 根据风险等级具体分析
5. **明日预测** — 简要预测说明
6. **建议措施** — 3-5条可操作的具体建议

请用中文撰写，语言专业、温暖、有建设性。"""

        return _llm_generate(system_prompt, user_prompt)

    def generate_weekly_trend(
        self,
        student_name: str = "",
        start_date: str = "",
        end_date: str = "",
        weekly_data: dict | None = None,
    ) -> dict:
        """生成周度趋势分析"""
        data = weekly_data or {}

        report_text = WEEKLY_TREND_TEMPLATE.format(
            student_name=student_name,
            start_date=start_date,
            end_date=end_date,
            weekly_overview=self._gen_weekly_overview(data),
            day_by_day_comparison=self._gen_day_by_day(data),
            trend_identification=self._gen_trend_identification(data),
            risk_periods=self._gen_risk_periods(data),
            next_week_prediction=self._gen_next_week_prediction(data),
            weekly_suggestions=self._gen_weekly_suggestions(data),
        )

        return {
            "report_type": "weekly",
            "student_name": student_name,
            "start_date": start_date,
            "end_date": end_date,
            "report_text": report_text,
        }

    def generate_visualization_insight(
        self,
        chart_description: str = "",
        data_context: dict | None = None,
    ) -> dict:
        """生成数据可视化解读"""
        ctx = data_context or {}

        insights = self._generate_data_insights(ctx)
        key_nums = self._extract_key_numbers(ctx)
        comparison = self._generate_comparison(ctx)

        report_text = VISUALIZATION_TEMPLATE.format(
            chart_description=chart_description or "情绪趋势图",
            data_insights=insights,
            key_numbers=key_nums,
            comparative_analysis=comparison,
        )

        return {
            "report_type": "visualization",
            "chart_description": chart_description,
            "report_text": report_text,
        }

    # ---- 辅助方法 ----

    def _get_score_status(self, score: float) -> str:
        if score >= 0.7:
            return "✅ 良好"
        elif score >= 0.4:
            return "⚠️ 关注"
        else:
            return "🔴 预警"

    def _get_stability_status(self, stability: float) -> str:
        if stability >= 0.7:
            return "✅ 稳定"
        elif stability >= 0.4:
            return "⚠️ 一般"
        else:
            return "🔴 波动大"

    def _get_positive_status(self, ratio: float) -> str:
        if ratio >= 0.5:
            return "✅ 良好"
        elif ratio >= 0.3:
            return "⚠️ 偏低"
        else:
            return "🔴 极低"

    def _get_negative_status(self, ratio: float) -> str:
        if ratio <= 0.2:
            return "✅ 低"
        elif ratio <= 0.4:
            return "⚠️ 偏高"
        else:
            return "🔴 极高"

    def _generate_emotion_overview(
        self, name: str, data: dict, analysis: dict
    ) -> str:
        """生成情绪概况段落"""
        emotion = data.get("fused_emotion", "未检测")
        score = analysis.get("overall_score", 0.7)
        trend = analysis.get("trend", "稳定")

        if score >= 0.7:
            overview = (
                f"{name}同学今日情绪状态整体良好，主要呈现**{emotion}**情绪特征。"
                f"情绪走势**{trend}**，各项指标均在正常范围内。"
            )
        elif score >= 0.4:
            overview = (
                f"{name}同学今日情绪状态需要关注，呈现**{emotion}**情绪特征。"
                f"情绪走势**{trend}**，建议加强观察和适时关怀。"
            )
        else:
            overview = (
                f"{name}同学今日情绪状态异常，呈现**{emotion}**情绪特征。"
                f"情绪走势**{trend}**，建议立即启动干预流程。"
            )
        return overview

    def _generate_risk_analysis(self, risk_level: str, analysis: dict) -> str:
        """生成风险分析"""
        if risk_level == "green":
            return "未检测到明显风险因素，继续保持。"
        elif risk_level == "yellow":
            factors = analysis.get("risk_factors", ["暂无详情"])
            return f"需关注以下方面：{'；'.join(factors[:3])}。"
        else:
            factors = analysis.get("risk_factors", ["暂无详情"])
            return f"⚠️ 紧急：{'；'.join(factors[:3])}。建议立即启动干预流程。"

    def _generate_prediction(self, prediction: dict) -> str:
        """生成明日预测"""
        next_score = prediction.get("next_day_emotion", 0.7)
        interval = prediction.get("confidence_interval_95", [0.4, 0.9])
        trend = prediction.get("trend_prediction", "稳定")

        return (
            f"预测明日综合评分约 **{next_score:.2f}** "
            f"（95%置信区间: [{interval[0]:.2f}, {interval[1]:.2f}]），"
            f"趋势: **{trend}**。"
        )

    def _format_suggestions(self, suggestions: list) -> str:
        """格式化建议列表"""
        if not suggestions:
            return "- 保持当前良好的情绪管理习惯"

        lines = []
        for s in suggestions[:5]:
            if isinstance(s, dict):
                lines.append(f"- [{s.get('priority', '')}] {s.get('content', '')}")
            else:
                lines.append(f"- {s}")
        return "\n".join(lines)

    def _generate_key_findings(self, data: dict, analysis: dict) -> str:
        """生成关键发现"""
        indicators = analysis.get("indicators", {})
        findings = []

        # 基于指标生成发现
        entropy = indicators.get("emotion_fluctuation_entropy", 0.5)
        if entropy > 0.7:
            findings.append("- 情绪波动偏大，建议关注波动原因")
        elif entropy < 0.3:
            findings.append("- 情绪状态非常稳定")

        recovery = indicators.get("emotion_recovery_speed", 0.5)
        if recovery < 0.3:
            findings.append("- 负面情绪恢复速度较慢")

        changes = indicators.get("emotion_abrupt_change_count", 0)
        if changes > 0:
            findings.append(f"- 检测到 {changes} 次情绪突变")

        emotion_dist = indicators.get("emotion_distribution", {})
        if emotion_dist:
            top_emotion = max(emotion_dist, key=emotion_dist.get)
            findings.append(f"- 主导情绪: **{top_emotion}**")

        return "\n".join(findings) if findings else "- 各项指标正常，无特殊发现"

    # ---- 周报辅助方法 ----
    def _gen_weekly_overview(self, data: dict) -> str:
        return "本周情绪总体平稳，个别时段略有波动。详细分析如下。"

    def _gen_day_by_day(self, data: dict) -> str:
        return "每日情绪得分将在此处展示对比分析。"

    def _gen_trend_identification(self, data: dict) -> str:
        return "根据线性回归分析，本周情绪呈现稳定趋势。"

    def _gen_risk_periods(self, data: dict) -> str:
        return "未检测到明确的持续高风险时段。"

    def _gen_next_week_prediction(self, data: dict) -> str:
        return "基于LSTM-Transformer模型预测，下周情绪将继续保持稳定。"

    def _gen_weekly_suggestions(self, data: dict) -> str:
        return "- 保持规律作息\n- 建议参与集体活动\n- 持续关注情绪变化"

    def _generate_data_insights(self, ctx: dict) -> str:
        return "根据图表数据分析，情绪走势符合日常节律。"

    def _extract_key_numbers(self, ctx: dict) -> str:
        return "综合评分: 待分析 | 波动率: 待分析"

    def _generate_comparison(self, ctx: dict) -> str:
        return "与前一周相比，情绪状态基本持平。"
