"""
心镜·AIGC智能体平台 — 多智能体协作系统
========================================

基于国产算力平台（沐曦MetaX GPU / Gitee.AI）的多智能体架构。

智能体列表:
- PerceptionAgent: 感知智能体 — 多模态情绪识别
- AnalysisAgent: 分析智能体 — 心理健康深度分析
- ReportAgent: 报告智能体 — AIGC内容生成
- AlertAgent: 预警智能体 — 分级预警与多渠道反馈
- OrchestratorAgent: 协调智能体 — 多智能体调度与协作
"""

from backend.agents.base_agent import BaseAgent
from backend.agents.perception_agent import PerceptionAgent
from backend.agents.analysis_agent import AnalysisAgent
from backend.agents.report_agent import ReportAgent
from backend.agents.alert_agent import AlertAgent
from backend.agents.orchestrator_agent import OrchestratorAgent

__all__ = [
    "BaseAgent",
    "PerceptionAgent",
    "AnalysisAgent",
    "ReportAgent",
    "AlertAgent",
    "OrchestratorAgent",
]
