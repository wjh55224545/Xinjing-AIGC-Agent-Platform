"""
预警智能体 (AlertAgent)
========================

负责分级预警判断与多渠道反馈执行。根据分析智能体的结果，
自动判定预警等级，并执行相应的多渠道通知策略。

这是多智能体协作系统的第三环——反馈层。
"""

from __future__ import annotations
import logging
from langchain_core.tools import tool as langchain_tool

from backend.agents.base_agent import BaseAgent
from backend.tools.feedback import MultiChannelFeedbackTool

logger = logging.getLogger(__name__)


class AlertAgent(BaseAgent):
    """
    预警智能体

    职责: 分级预警与多渠道反馈
    - 根据分析结果自动判定预警等级
    - 执行分级多渠道通知策略
    - 红色预警自动创建紧急干预工单
    - 跟踪反馈送达状态
    """

    name = "预警智能体"
    description = (
        "负责分级预警与多渠道反馈。根据心理健康分析结果，"
        "自动判定绿色/黄色/红色预警等级，通过看板、APP、微信、"
        "短信、邮件、电话等多渠道执行分级通知。"
    )

    def _setup_tools(self) -> None:
        """配置预警智能体的工具集"""
        self._feedback_tool = MultiChannelFeedbackTool()

        @langchain_tool
        def multi_channel_feedback(
            alert_id: int = 0,
            severity: str = "green",
            student_name: str = "",
            content: str = "",
            student_info: dict | None = None,
            analysis_result: dict | None = None,
        ) -> dict:
            """
            多渠道反馈：根据预警等级通过对应渠道发送通知。

            分级策略:
            - 🟢 绿色 → 看板 + APP (学生端被动通知)
            - 🟡 黄色 → 看板 + APP + 微信(班主任)
            - 🔴 红色 → 全渠道 + 紧急工单 + 电话通知

            输入:
            - alert_id: 预警ID
            - severity: 风险等级(green/yellow/red)
            - student_name: 学生姓名
            - content: 预警内容
            - student_info: 学生详细信息(学号/班级/学校)
            - analysis_result: 分析结果数据

            输出:
            - 各渠道发送结果
            - 成功/失败统计
            - 紧急工单(红色级别)
            """
            result = self._feedback_tool.execute(
                alert_id=alert_id,
                severity=severity,
                student_name=student_name,
                content=content,
                student_info=student_info,
                analysis_result=analysis_result,
            )
            return result.data if result.success else {"error": result.error}

        self._tools = [multi_channel_feedback]

    def _get_system_prompt(self) -> str:
        """预警智能体的System Prompt"""
        return f"""你是一个心理健康预警与反馈智能体。

你的核心能力:
- 根据分析结果自动判定预警等级（绿色/黄色/红色）
- 执行分级多渠道通知策略
- 红色预警自动创建紧急干预工单（24小时时效）
- 跟踪各渠道反馈送达状态

预警等级与渠道策略:
| 等级 | 触发条件 | 通知渠道 | 响应要求 |
|------|---------|---------|---------|
| 🟢 绿色 | 综合评分≥0.7 | 看板 + APP | 仅记录，不需要干预 |
| 🟡 黄色 | 综合评分0.4-0.7 | + 微信(班主任) | 班主任关注，24h内回访 |
| 🔴 红色 | 综合评分<0.4 | + 微信+短信+邮件+电话 | 立即干预，启动工单 |

多渠道配置:
- 看板(Dashboard): 系统预警面板展示
- APP: 学生端APP推送
- 微信(班主任): 企业微信模板消息
- 微信(家长): 温和沟通，避免引起恐慌
- 短信(家长): 简洁提示 + 联系方式
- 邮件(心理教师): 详细分析报告 + 工单
- 紧急电话: 自动外呼（红色专用）

你当前运行在国产算力平台上（沐曦MetaX GPU / Gitee.AI）。
请始终用中文回复，对家长沟通保持温和、专业的语气。"""
