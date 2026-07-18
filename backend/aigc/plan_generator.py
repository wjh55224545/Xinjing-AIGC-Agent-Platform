"""
干预方案生成器 (PlanGenerator)
===============================

基于风险等级和具体指标，自动生成个性化心理干预方案。
不同风险等级采用不同的干预策略和措施建议。
"""

from __future__ import annotations
import hashlib
import logging
from datetime import datetime
from backend.aigc.templates.plan_templates import (
    INTERVENTION_PLAN_TEMPLATE,
    RISK_LEVEL_MEASURES,
    SUPPORT_RESOURCES_LIST,
)
from backend.aigc.llm_client import llm_generate as _llm_generate

logger = logging.getLogger(__name__)

# 风险等级映射
RISK_LEVEL_MAP = {
    "green": ("🟢", "低风险 - 正常关注"),
    "yellow": ("🟡", "中风险 - 需要关注"),
    "red": ("🔴", "高风险 - 紧急干预"),
}


class PlanGenerator:
    """干预方案生成器"""

    name = "干预方案生成"
    description = "根据风险等级和心理健康指标，自动生成个性化干预方案"

    def generate(
        self,
        student_name: str = "",
        risk_level: str = "green",
        risk_factors: list | None = None,
        indicators: dict | None = None,
    ) -> dict:
        """
        生成个性化干预方案

        Args:
            student_name: 学生姓名
            risk_level: 风险等级 (green/yellow/red)
            risk_factors: 风险因素列表
            indicators: 心理健康指标

        Returns:
            包含完整干预方案的字典
        """
        factors = risk_factors or []
        ind = indicators or {}

        name = student_name or "未知学生"
        plan_id = self._generate_plan_id(name)
        plan_date = datetime.now().strftime("%Y-%m-%d")

        # ---- 优先尝试 LLM 生成 ----
        llm_text = self._try_llm_generate(name, risk_level, factors, ind, plan_id)
        if llm_text:
            return {
                "plan_type": "intervention",
                "student_name": student_name,
                "plan_id": plan_id,
                "risk_level": risk_level,
                "plan_text": llm_text,
                "generated_by": "心镜·AIGC智能体 (moark.com Qwen3-8B)",
                "generated_at": plan_date,
            }

        # ---- LLM 不可用，降级到模板模式 ----
        emoji, level_text = RISK_LEVEL_MAP.get(risk_level, RISK_LEVEL_MAP["green"])
        diagnosis = self._generate_diagnosis(risk_level, factors, ind)
        goals = self._generate_goals(risk_level, factors, ind)
        measures = self._generate_measures(risk_level, factors, ind)
        resources = self._generate_resources(risk_level)
        outcomes = self._generate_outcomes(risk_level)
        checkpoints = self._generate_checkpoints(risk_level)

        plan_text = INTERVENTION_PLAN_TEMPLATE.format(
            student_name=name,
            date=plan_date,
            risk_level_emoji=emoji,
            risk_level_text=level_text,
            plan_id=plan_id,
            problem_diagnosis=diagnosis,
            intervention_goals=goals,
            intervention_measures=measures,
            support_resources=resources,
            expected_outcomes=outcomes,
            review_checkpoints=checkpoints,
        )

        return {
            "plan_type": "intervention",
            "student_name": student_name,
            "plan_id": plan_id,
            "risk_level": risk_level,
            "plan_text": plan_text,
            "generated_by": "心镜·AIGC智能体 (模板模式)",
            "generated_at": plan_date,
        }

    def _try_llm_generate(
        self,
        student_name: str,
        risk_level: str,
        risk_factors: list,
        indicators: dict,
        plan_id: str,
    ) -> str | None:
        """尝试使用 LLM 生成干预方案，失败返回 None。"""
        factors_str = "\n".join(f"- {f}" for f in risk_factors) if risk_factors else "- 无明显风险因素"
        level_map = {"green": "低风险 - 正常关注", "yellow": "中风险 - 需要关注", "red": "高风险 - 紧急干预"}
        level_text = level_map.get(risk_level, "未知")

        system_prompt = (
            "你是一位资深的学校心理健康教育专家，负责为学生制定个性化心理干预方案。"
            "请用中文撰写，语言专业、具体、可操作。使用 Markdown 格式。"
        )

        user_prompt = f"""请为 {student_name} 同学生成个性化心理干预方案。

## 基本信息
- 方案编号：{plan_id}
- 风险等级：{risk_level}（{level_text}）
- 情绪稳定性指数：{indicators.get('emotional_stability_index', 'N/A')}
- 综合心理健康评分：{indicators.get('overall_mental_health_score', 'N/A')}
- 情绪恢复速度：{indicators.get('emotion_recovery_speed', 'N/A')}

## 风险因素
{factors_str}

请按以下结构输出完整的干预方案：
1. **问题诊断** — 基于风险因素的具体分析
2. **干预目标** — 3-5个明确可量化的目标
3. **具体措施** — 按紧急程度排序的具体步骤
4. **资源支持** — 可利用的校内外资源
5. **预期效果** — 各时间节点的预期改善
6. **评估计划** — 检查点和评估指标表格

根据风险等级调整方案紧急程度和措辞力度。"""

        return _llm_generate(system_prompt, user_prompt, max_tokens=2048)

    def _generate_plan_id(self, student_name: str) -> str:
        """生成方案编号"""
        date_str = datetime.now().strftime("%Y%m%d")
        hash_str = hashlib.md5(
            f"{student_name}{date_str}".encode()
        ).hexdigest()[:6].upper()
        return f"IP-{date_str}-{hash_str}"

    def _generate_diagnosis(
        self, risk_level: str, factors: list, indicators: dict
    ) -> str:
        """生成问题诊断"""
        if risk_level == "green":
            return "当前心理状态良好，无需特别干预。本方案旨在维持和促进心理健康。"

        factor_text = "\n".join(f"- {f}" for f in factors[:5]) if factors else "- 详见心理健康分析报告"

        if risk_level == "yellow":
            return (
                f"经心镜智能体分析，检测到以下需要关注的方面：\n\n"
                f"{factor_text}\n\n"
                f"建议采取温和的预防性干预措施，防止情况进一步发展。"
            )
        else:  # red
            return (
                f"经心镜智能体紧急评估，检测到以下风险因素：\n\n"
                f"{factor_text}\n\n"
                f"需要立即启动紧急干预流程，家校联动，确保学生得到及时支持。"
            )

    def _generate_goals(
        self, risk_level: str, factors: list, indicators: dict
    ) -> str:
        """生成干预目标"""
        if risk_level == "green":
            return (
                "1. 维持当前良好的心理健康状态\n"
                "2. 培养积极的心理资本（韧性、乐观、自我效能感）\n"
                "3. 预防潜在的心理风险"
            )
        elif risk_level == "yellow":
            return (
                "1. 稳定情绪状态，减少负面情绪波动\n"
                "2. 提升情绪调节能力\n"
                "3. 建立有效的社会支持网络\n"
                "4. 2周内将综合评分提升至0.7以上"
            )
        else:  # red
            return (
                "1. 立刻缓解当前的负面情绪状态\n"
                "2. 建立安全的心理支持环境\n"
                "3. 家校联动形成24小时监护网络\n"
                "4. 1周内完成专业心理评估\n"
                "5. 制定中长期心理健康恢复计划"
            )

    def _generate_measures(
        self, risk_level: str, factors: list, indicators: dict
    ) -> str:
        """生成具体措施"""
        measures_list = RISK_LEVEL_MEASURES.get(
            risk_level, RISK_LEVEL_MEASURES["green"]
        )
        return "\n".join(f"{i+1}. {m}" for i, m in enumerate(measures_list))

    def _generate_resources(self, risk_level: str) -> str:
        """生成资源支持"""
        if risk_level == "green":
            return "\n".join(SUPPORT_RESOURCES_LIST[:2])
        elif risk_level == "yellow":
            return "\n".join(SUPPORT_RESOURCES_LIST[:4])
        else:
            return "\n".join(SUPPORT_RESOURCES_LIST)

    def _generate_outcomes(self, risk_level: str) -> str:
        """生成预期效果"""
        if risk_level == "green":
            return (
                "- 继续保持0.7以上的综合评分\n"
                "- 积极情绪占比维持在50%以上\n"
                "- 无新增风险因素"
            )
        elif risk_level == "yellow":
            return (
                "- 2周内综合评分回升至0.7以上\n"
                "- 负面情绪占比降至20%以下\n"
                "- 情绪稳定性指数提升至0.7以上"
            )
        else:
            return (
                "- 1周内完成紧急状态评估\n"
                "- 建立有效的家校沟通机制\n"
                "- 制定中长期恢复计划\n"
                "- 2周内实现情绪状态初步稳定"
            )

    def _generate_checkpoints(self, risk_level: str) -> str:
        """生成评估检查点"""
        if risk_level == "green":
            return (
                "| 第1周 | 1周后 | 综合评分 |\n"
                "| 第1月 | 1月后 | 整体评估 |"
            )
        elif risk_level == "yellow":
            return (
                "| 第3天 | 3天后 | 情绪稳定性 |\n"
                "| 第1周 | 1周后 | 综合评分 |\n"
                "| 第2周 | 2周后 | 整体评估 |"
            )
        else:
            return (
                "| 第1天 | 24小时后 | 紧急评估 |\n"
                "| 第3天 | 3天后 | 情绪状态 |\n"
                "| 第1周 | 1周后 | 综合评估 |\n"
                "| 第2周 | 2周后 | 恢复评估 |"
            )
