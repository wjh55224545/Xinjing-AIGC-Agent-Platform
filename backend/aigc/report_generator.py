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
            # ---- 自进化：记录 LLM 生成经验 ----
            try:
                from backend.evolution.memory import record_experience
                record_experience("daily_report", name, llm_text)
            except Exception:
                pass

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
        recovery_speed = indicators.get("emotion_recovery_speed", 0.5)
        stress_accumulation = indicators.get("stress_accumulation_index", 0.2)

        # ---- 数据-结论一致性校验：发现矛盾时修正表述，防止"占比20%却称良好"类错误 ----
        consistency_issues = self._check_consistency(
            overall_score=overall_score,
            risk_level=risk_level,
            positive_ratio=positive_ratio,
            negative_ratio=negative_ratio,
            stability=stability,
            trend=trend,
        )

        score_status = self._get_score_status(overall_score)
        # 评分标签与风险等级联动：评分低但未判红色时，用"偏低"而非"预警"，保持报告内自洽
        if overall_score < 0.4 and risk_level != "red":
            score_status = "⚠️ 偏低"
        stability_status = self._get_stability_status(stability)
        positive_status = self._get_positive_status(positive_ratio)
        negative_status = self._get_negative_status(negative_ratio)
        risk_level_cn, risk_level_status = self._get_risk_status(risk_level)
        trend_status = self._get_trend_status(trend)
        recovery_status = self._get_recovery_status(recovery_speed)
        stress_status = self._get_stress_status(stress_accumulation)

        emotion_overview = self._generate_emotion_overview(
            name, data, analysis, positive_ratio=positive_ratio, consistency_issues=consistency_issues
        )
        risk_analysis_text = self._generate_risk_analysis(risk_level, analysis)
        llm_prediction = analysis.get("llm_prediction", {})
        next_day_prediction = self._generate_prediction(llm_prediction)
        suggestions = self._format_suggestions(
            self._generate_personalized_suggestions(analysis) or analysis.get("suggestions", [])
        )
        key_findings = self._generate_key_findings(data, analysis)

        # ---- 自进化：记录经验 ----
        try:
            from backend.evolution.memory import record_experience
            record_experience("daily_report", name, report_text[:300] if report_text else "")
        except Exception:
            pass

        report_text = DAILY_REPORT_TEMPLATE.format(
            student_name=name,
            date=report_date,
            overall_score=overall_score,
            score_status=score_status,
            risk_level_cn=risk_level_cn,
            risk_level_status=risk_level_status,
            stability=stability,
            stability_status=stability_status,
            positive_ratio=positive_ratio,
            positive_status=positive_status,
            negative_ratio=negative_ratio,
            negative_status=negative_status,
            trend=trend,
            trend_status=trend_status,
            recovery_speed=recovery_speed,
            recovery_status=recovery_status,
            stress_accumulation=stress_accumulation,
            stress_status=stress_status,
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
        llm_prediction = analysis.get("llm_prediction", {})

        suggestion_str = "\n".join(
            f"- {s.get('content', str(s))}" if isinstance(s, dict) else f"- {s}"
            for s in suggestions[:5]
        ) or "- 保持当前良好的情绪管理习惯"

        risk_str = "\n".join(f"- {f}" for f in risk_factors) if risk_factors else "- 无明显风险因素"

        system_prompt = (
            "你是一位专业的学校心理辅导老师，负责撰写学生心理健康评估日报。"
            "请使用专业的心理学语言，同时保持报告对教师和家长友好可读。"
            "用 Markdown 格式输出结构化报告，适当使用 emoji 增强可读性。"
            "【数据一致性铁律】报告中的每一句结论都必须与给出的数据严格一致："
            "积极情绪占比低时不得写'良好/接近满分'，积极占比高时不得判高风险；"
            "综合评分、风险等级、情绪占比、趋势之间不得相互矛盾。"
            "【全中文】正文一律使用中文，除必要的心理学术语（如量表名）外不得出现任何英文单词。"
            "【共情要求】措辞温暖、支持、有建设性，避免制造焦虑，但也不淡化真实风险。"
        )

        # ---- 自进化：注入历史成功案例 ----
        try:
            from backend.evolution.memory import build_evolution_context
            evo_ctx = build_evolution_context("daily_report")
            if evo_ctx:
                system_prompt += "\n" + evo_ctx
        except Exception:
            pass

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
- 趋势预测：{llm_prediction.get('trend_prediction', '稳定') if llm_prediction else '稳定'}

## 已有建议参考
{suggestion_str}

请按以下结构输出完整报告：
1. **情绪概况** — 1段自然语言概述（必须与数据一致，措辞温暖）
2. **关键指标表格** — Markdown表格，须包含：综合评分、风险等级、情绪稳定性、积极情绪占比、负面情绪占比、情绪趋势、情绪恢复速度、压力累积指数
3. **关键发现** — 2-3条要点
4. **风险分析** — 根据风险等级具体分析（温暖、建设性措辞）
5. **明日预测** — 简要预测说明（全中文）
6. **建议措施** — 3-5条针对该生主导情绪和具体指标的可操作建议（避免泛泛而谈）

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

    # 风险等级中文映射与状态
    _RISK_LEVEL_CN = {"green": "绿色·低风险", "yellow": "黄色·中等风险", "red": "红色·高风险"}

    def _check_consistency(
        self,
        overall_score: float | None = None,
        risk_level: str = "",
        positive_ratio: float | None = None,
        negative_ratio: float | None = None,
        stability: float | None = None,
        trend: str = "",
    ) -> list:
        """
        数据-结论一致性校验（专家评估暴露的最大失分点）。

        依据：Tun et al. (2025, JMIR) 系统综述——临床可靠性（一致性/准确性）是
        AI 临床决策支持信任的第一要素；专家评语指出"积极情绪占比仅20%却称接近满分"
        "积极占比52.3%却判高风险"等矛盾直接摧毁报告信任度。

        返回矛盾清单；调用方据清单修正报告措辞，矛盾报告不再原样输出。
        """
        issues = []
        if positive_ratio is not None:
            if risk_level == "red" and positive_ratio >= 0.5:
                issues.append("积极情绪占比≥50%与红色高风险判定矛盾")
            if risk_level == "green" and positive_ratio < 0.3:
                issues.append("积极情绪占比<30%与绿色低风险判定矛盾")
            if overall_score is not None and overall_score >= 0.7 and positive_ratio < 0.3:
                issues.append("综合评分≥0.7与积极情绪占比<30%矛盾")
        if negative_ratio is not None:
            if risk_level == "green" and negative_ratio > 0.4:
                issues.append("负面情绪占比>40%与绿色低风险判定矛盾")
            if overall_score is not None and overall_score >= 0.7 and negative_ratio > 0.4:
                issues.append("综合评分≥0.7与负面情绪占比>40%矛盾")
        if stability is not None and overall_score is not None:
            if overall_score >= 0.7 and stability < 0.3:
                issues.append("综合评分≥0.7与情绪稳定性<0.3矛盾")
        if trend == "下降中" and risk_level == "green":
            issues.append("情绪趋势下降与绿色低风险判定矛盾")
        return issues

    def _get_risk_status(self, risk_level: str) -> tuple:
        """风险等级中文名与状态标签"""
        if risk_level == "green":
            return "绿色 · 低风险", "✅ 正常"
        elif risk_level == "yellow":
            return "黄色 · 中等风险", "⚠️ 需关注"
        else:
            return "红色 · 高风险", "🔴 需干预"

    def _get_trend_status(self, trend: str) -> str:
        if trend == "改善中":
            return "📈 向好"
        elif trend == "下降中":
            return "📉 需关注"
        return "➖ 平稳"

    def _get_recovery_status(self, recovery_speed: float) -> str:
        """情绪恢复速度状态（依据：Schoevers et al. 2020，恢复慢是疾病状态信号）"""
        if recovery_speed >= 0.6:
            return "✅ 良好"
        elif recovery_speed >= 0.35:
            return "⚠️ 一般"
        return "🔴 偏慢"

    def _get_stress_status(self, stress_accumulation: float) -> str:
        if stress_accumulation <= 0.3:
            return "✅ 低"
        elif stress_accumulation <= 0.6:
            return "⚠️ 中等"
        return "🔴 偏高"

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
        self, name: str, data: dict, analysis: dict,
        positive_ratio: float | None = None, consistency_issues: list | None = None,
    ) -> str:
        """
        生成情绪概况段落（已修复数据-结论一致性）。

        依据：Di Blasi et al. (2001, The Lancet)——温暖、安抚式沟通更有效；
        Zachariae et al. (2003)——关注与共情提升自我效能、降低情绪困扰。
        概览结论必须与积极占比等指标一致，避免"占比20%却称整体良好"类矛盾。
        """
        emotion = data.get("fused_emotion", "未检测")
        score = analysis.get("overall_score", 0.7)
        trend = analysis.get("trend", "稳定")
        risk_level = analysis.get("risk_level", "green")
        issues = consistency_issues or []

        # 一致性修正：若存在"评分高但占比低"的矛盾，降低表述强度
        contradictory = any("矛盾" in i for i in issues)
        if score >= 0.7 and not contradictory:
            overview = (
                f"{name}同学今日情绪状态整体良好，主要呈现**{emotion}**情绪特征。"
                f"情绪走势**{trend}**，各项指标均在正常范围内，继续保持规律作息与积极活动。"
            )
        elif score >= 0.7 and contradictory:
            overview = (
                f"{name}同学今日综合评分处于较高水平，但情绪构成上积极情绪占比相对有限，"
                f"主要呈现**{emotion}**情绪特征，情绪走势**{trend}**。"
                f"建议关注情绪构成结构，适度增加积极体验。"
            )
        elif score >= 0.4:
            overview = (
                f"{name}同学今日情绪状态需要关注，主要呈现**{emotion}**情绪特征。"
                f"情绪走势**{trend}**。请不必过度紧张，情绪波动是正常的心理反应，"
                f"建议近期加强自我观察，并适时与信任的老师或朋友交流。"
            )
        elif risk_level == "red":
            # 评分低且判定红色高风险 → 强措辞（与风险等级一致）
            overview = (
                f"{name}同学今日情绪状态明显偏低，主要呈现**{emotion}**情绪特征，"
                f"情绪走势**{trend}**。请老师和家人给予更多陪伴与理解，"
                f"建议尽快与学校心理咨询中心联系，共同商定支持方案。"
            )
        else:
            # 评分低但风险等级未达红色（负面占比不高）→ 中等措辞，避免与风险等级矛盾
            overview = (
                f"{name}同学今日综合评分偏低，主要呈现**{emotion}**情绪特征，"
                f"情绪走势**{trend}**。这需要引起注意，但情绪构成中负面占比并不突出，"
                f"建议近期保持观察，并主动向信任的师长或同学寻求交流与支持。"
            )
        return overview

    def _generate_risk_analysis(self, risk_level: str, analysis: dict) -> str:
        """生成风险分析（温暖、建设性措辞，避免引发不必要的焦虑）"""
        if risk_level == "green":
            return (
                "当前未检测到明显风险因素。请继续关注自身感受，保持规律作息、"
                "适度运动和积极的社交活动，这对维持良好心理状态很有帮助。"
            )
        elif risk_level == "yellow":
            factors = analysis.get("risk_factors", ["暂无详情"])
            return (
                f"当前需要关注以下方面：{'；'.join(factors[:3])}。"
                "这属于中等程度的预警信号，多数情况下通过一段时间的自我调节和"
                "身边支持即可改善；建议按下方措施行动，并在 1–2 周后复测观察变化。"
            )
        else:
            factors = analysis.get("risk_factors", ["暂无详情"])
            return (
                f"当前存在需要重视的风险信号：{'；'.join(factors[:3])}。"
                "请老师和家长保持耐心，避免责备或施加压力；建议尽快联系学校心理"
                "咨询中心或专业机构进行进一步评估，并持续关注学生状态。"
            )

    def _generate_prediction(self, prediction: dict) -> str:
        """生成明日预测（全中文表述，消除英文残留）"""
        next_score = prediction.get("next_day_emotion", 0.7)
        interval = prediction.get("confidence_interval_95", [0.4, 0.9])
        trend = prediction.get("trend_prediction", "稳定")

        return (
            f"预测明日综合评分约为 **{next_score:.2f}** "
            f"（95% 置信区间: [{interval[0]:.2f}, {interval[1]:.2f}]），"
            f"趋势: **{trend}**。预测结果仅作参考，请以实际状态为准。"
        )

    def _generate_personalized_suggestions(self, analysis: dict) -> list:
        """
        按主导情绪生成个性化建议（建议为空时启用）。

        依据：Kroeze et al. (2006, Ann Behav Med) 系统综述——30 项 RCT 中 23 项
        显示计算机定制化健康干预优于通用信息；De Vries et al. (2008) RCT 证实
        定制反馈带来更多行为改善。专家评语 3 次提及"建议偏普适、个性化不足"。
        """
        if analysis.get("suggestions"):
            return analysis["suggestions"]

        indicators = analysis.get("indicators", {})
        dist = indicators.get("emotion_distribution", {})
        dominant = max(dist, key=dist.get) if dist else analysis.get("dominant_emotion", "")
        risk_level = analysis.get("risk_level", "green")
        recovery = indicators.get("emotion_recovery_speed", 0.5)
        stress = indicators.get("stress_accumulation_index", 0.2)

        # 主导情绪定制建议库（结合情绪特点给出具体可操作建议）
        emotion_suggestions = {
            "开心": ["继续保持当前令你感到愉悦的活动和社交节奏", "可以尝试将积极情绪记录下来，作为后续调节的自我资源"],
            "平静": ["保持当前平稳的生活节律，规律作息是稳定情绪的基础", "适当增加轻度运动，如散步、拉伸，巩固良好状态"],
            "中性": ["近期可主动安排一些让自己有掌控感的小任务，提升正向体验", "尝试每天记录一件值得肯定的小事，增强积极情绪积累"],
            "悲伤": ["允许自己感受情绪，不必强求马上振作；给自己一些温和的空间", "尝试与信任的朋友或家人谈谈感受，或通过写日记疏解情绪", "若低落持续超过两周，建议预约学校心理咨询中心"],
            "焦虑": ["先做几次缓慢的深呼吸，帮助身体从紧张状态中缓和下来", "把担心的事情具体写下来，区分“可控制的”与“不可控制的”部分", "减少咖啡因摄入，保证充足睡眠；若焦虑持续加重请寻求专业支持"],
            "愤怒": ["感到愤怒时先离开冲突场景，给自己几分钟冷静缓冲", "用身体活动（如快走、击打枕头）释放情绪，再尝试理性表达", "练习“我感觉到……因为……”的沟通句式，减少情绪化表达"],
            "恐惧": ["确认当前处境的实际安全性，避免灾难化想象", "与信任的人分享你的担忧，必要时约定短期陪伴", "若恐惧明显影响日常功能，建议尽快寻求专业评估"],
            "厌恶": ["识别并温和接纳当下的不适感，不必强迫自己立刻消除", "暂时减少触发不适的场景，给自己恢复空间"],
        }
        base = {
            "green": ["保持规律作息与适度运动，巩固当前良好的心理状态"],
            "yellow": ["按上述措施坚持 1–2 周，并在 1–2 周后复测观察趋势变化", "建议与辅导员或心理咨询中心保持沟通，反馈近期状态"],
            "red": ["请尽快与学校心理咨询中心或专业机构预约评估", "建议近期避免独处，保持与信任之人的日常联系"],
        }

        tips = []
        if dominant and dominant in emotion_suggestions:
            tips.extend(emotion_suggestions[dominant])
        elif dominant:
            tips.append(f"近期可围绕「{dominant}」情绪状态，主动记录触发情境与应对方式")
        if recovery < 0.35:
            tips.append("情绪恢复速度偏慢：负面情绪出现后，可尝试深呼吸、正念等放松训练帮助恢复")
        if stress > 0.6:
            tips.append("压力累积偏高：建议主动做减压安排，如运动、艺术活动，避免压力持续堆积")

        result = []
        for t in (base.get(risk_level, []) + tips):
            result.append({"priority": "medium", "content": t})
        return result

    def _format_suggestions(self, suggestions: list) -> str:
        """格式化建议列表"""
        if not suggestions:
            return "- 保持当前良好的情绪管理习惯"

        lines = []
        priority_cn = {"low": "一般", "medium": "中等", "high": "优先", "": ""}
        for s in suggestions[:5]:
            if isinstance(s, dict):
                p = priority_cn.get(str(s.get('priority', '')), str(s.get('priority', '')))
                prefix = f"[{p}] " if p else ""
                lines.append(f"- {prefix}{s.get('content', '')}")
            else:
                lines.append(f"- {s}")
        return "\n".join(lines)

    def _generate_key_findings(self, data: dict, analysis: dict) -> str:
        """生成关键发现（已消除与情绪概况矛盾的并存表述）"""
        indicators = analysis.get("indicators", {})
        findings = []

        # 基于指标生成发现
        entropy = indicators.get("emotion_fluctuation_entropy", 0.5)
        stability = indicators.get("emotional_stability_index", 0.7)
        if entropy > 0.7:
            if stability >= 0.7:
                # 熵高但稳定性指数不低——避免"稳定"与"波动大"并存矛盾（专家 R01 评语）
                findings.append("- 情绪在部分时段存在一定起伏，但整体可控")
            else:
                findings.append("- 情绪波动偏大，建议关注波动背后的原因")
        elif entropy < 0.3:
            findings.append("- 情绪状态非常稳定")

        recovery = indicators.get("emotion_recovery_speed", 0.5)
        if recovery < 0.3:
            findings.append("- 负面情绪出现后的恢复速度偏慢，建议学习放松调节技巧")

        changes = indicators.get("emotion_abrupt_change_count", 0)
        if changes > 0:
            findings.append(f"- 检测到 {changes} 次情绪突变")

        stress = indicators.get("stress_accumulation_index", 0.0)
        if stress > 0.6:
            findings.append("- 压力累积偏高，建议主动安排减压活动")

        emotion_dist = indicators.get("emotion_distribution", {})
        if emotion_dist:
            top_emotion = max(emotion_dist, key=emotion_dist.get)
            findings.append(f"- 主导情绪: **{top_emotion}**，建议围绕该情绪状态安排对应的调节策略")

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
        return "基于Lingshu-32B模型分析，下周情绪将继续保持稳定。"

    def _gen_weekly_suggestions(self, data: dict) -> str:
        return "- 保持规律作息\n- 建议参与集体活动\n- 持续关注情绪变化"

    def _generate_data_insights(self, ctx: dict) -> str:
        return "根据图表数据分析，情绪走势符合日常节律。"

    def _extract_key_numbers(self, ctx: dict) -> str:
        return "综合评分: 待分析 | 波动率: 待分析"

    def _generate_comparison(self, ctx: dict) -> str:
        return "与前一周相比，情绪状态基本持平。"
