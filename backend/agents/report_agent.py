"""
报告智能体 (ReportAgent)
=========================

基于AIGC能力生成各类心理评估内容。这是比赛任务三的核心亮点——
利用国产算力平台上的大模型，自动生成自然语言的心理报告、干预方案、
家校沟通函等内容。

这是多智能体协作系统的AIGC核心层。
"""

from __future__ import annotations
import logging
from langchain_core.tools import tool as langchain_tool

from backend.agents.base_agent import BaseAgent
from backend.aigc.report_generator import ReportGenerator
from backend.aigc.plan_generator import PlanGenerator
from backend.aigc.letter_generator import LetterGenerator
from backend.aigc.narrative_generator import NarrativeGenerator

logger = logging.getLogger(__name__)


class ReportAgent(BaseAgent):
    """
    报告智能体

    职责: AIGC内容生成
    - 心理评估日报/周报生成
    - 个性化干预方案生成
    - 家校沟通函生成
    - 学生成长叙事生成
    - 数据可视化解读
    """

    name = "AIGC报告智能体"
    description = (
        "基于国产算力平台大模型，自动生成心理健康评估报告、"
        "个性化干预方案、家校沟通文案、学生成长叙事等AIGC内容。"
        "体现AIGC + 智能体技术的深度融合。"
    )

    def __init__(self, streaming: bool = True, platform: str | None = None):
        super().__init__(streaming=streaming, platform=platform)
        self.report_gen = ReportGenerator()
        self.plan_gen = PlanGenerator()
        self.letter_gen = LetterGenerator()
        self.narrative_gen = NarrativeGenerator()

    def _setup_tools(self) -> None:
        """配置报告智能体的工具集"""
        agent_ref = self  # 闭包引用

        @langchain_tool
        def generate_daily_report(
            student_name: str = "",
            date: str = "",
            emotion_data: dict | None = None,
            analysis_result: dict | None = None,
        ) -> dict:
            """
            生成心理评估日报。基于当日情绪数据和12项指标，用大模型生成自然语言评估报告。

            输入:
            - student_name: 学生姓名
            - date: 报告日期
            - emotion_data: 当日情绪数据
            - analysis_result: 心理健康分析结果

            输出:
            - 情绪概况段落
            - 关键发现列表
            - 风险评估
            - 建议措施
            """
            return agent_ref.report_gen.generate(
                student_name=student_name,
                date=date,
                emotion_data=emotion_data or {},
                analysis_result=analysis_result or {},
            )

        @langchain_tool
        def generate_intervention_plan(
            student_name: str = "",
            risk_level: str = "green",
            risk_factors: list | None = None,
            indicators: dict | None = None,
        ) -> dict:
            """
            生成个性化干预方案。根据风险等级和具体因素，用大模型生成有针对性的干预计划。

            输入:
            - student_name: 学生姓名
            - risk_level: 风险等级(green/yellow/red)
            - risk_factors: 风险因素列表
            - indicators: 心理健康指标

            输出:
            - 问题诊断
            - 干预目标
            - 具体措施(3-5条)
            - 预期效果
            - 评估周期
            """
            return agent_ref.plan_gen.generate(
                student_name=student_name,
                risk_level=risk_level,
                risk_factors=risk_factors or [],
                indicators=indicators or {},
            )

        @langchain_tool
        def generate_parent_letter(
            student_name: str = "",
            class_name: str = "",
            emotion_summary: str = "",
            risk_level: str = "green",
            suggestions: list | None = None,
        ) -> dict:
            """
            生成家校沟通函。用自然、温和的语言向家长传达学生情绪状态。

            输入:
            - student_name: 学生姓名
            - class_name: 班级
            - emotion_summary: 情绪概况
            - risk_level: 风险等级
            - suggestions: 建议列表

            输出:
            - 问候语
            - 情况说明(温和措辞)
            - 建议措施
            - 落款信息
            """
            return agent_ref.letter_gen.generate(
                student_name=student_name,
                class_name=class_name,
                emotion_summary=emotion_summary,
                risk_level=risk_level,
                suggestions=suggestions or [],
            )

        @langchain_tool
        def generate_growth_narrative(
            student_name: str = "",
            period_days: int = 30,
            historical_data: dict | None = None,
        ) -> dict:
            """
            生成学生成长叙事。基于长期情绪数据，用大模型撰写学生心理成长轨迹。

            输入:
            - student_name: 学生姓名
            - period_days: 时间跨度(天)
            - historical_data: 历史情绪数据

            输出:
            - 成长轨迹描述
            - 关键转折点
            - 积极变化
            - 未来展望
            """
            return agent_ref.narrative_gen.generate(
                student_name=student_name,
                period_days=period_days,
                historical_data=historical_data or {},
            )

        self._tools = [
            generate_daily_report,
            generate_intervention_plan,
            generate_parent_letter,
            generate_growth_narrative,
        ]

    def _get_system_prompt(self) -> str:
        """报告智能体的System Prompt"""
        return f"""你是一个AIGC心理报告智能体，专门负责生成各类心理健康相关的内容。

你的核心能力（基于国产算力平台沐曦MetaX GPU + Gitee.AI）:
1. 📊 心理评估日报 —— 基于全天情绪数据，用自然语言撰写结构化评估报告
2. 📋 个性化干预方案 —— 针对黄/红色预警，生成可执行的干预计划
3. ✉️  家校沟通函 —— 用温和、专业、易懂的语言向家长传达信息
4. 📈 学生成长叙事 —— 基于长期数据生成学生心理成长轨迹
5. 🔍 数据可视化解读 —— AI解读图表数据，生成描述性分析

写作原则:
- **专业性**: 使用准确的心理学术语，但避免过度学术化
- **共情性**: 站在学生和家长的角度思考，措辞温暖有力
- **建设性**: 不只指出问题，更要给出可操作的建议
- **适度性**: 避免引起不必要的焦虑，但也不能淡化真实风险

输出格式要求:
- 使用自然段落结构
- 要点清晰、层次分明
- 适当使用emoji增强可读性
- 以Markdown格式输出（支持格式化显示）

你当前运行在**国产算力平台**上（沐曦MetaX GPU / Gitee.AI），
是心镜·AIGC智能体平台的核心AIGC引擎。
请始终用中文回复，保持专业、温暖、有建设性的风格。"""
