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

说明: 业务智能体采用惰性导入（__getattr__），保证通用框架
`backend.agents.framework` 可在不安装 langchain 的环境中独立使用。
"""

from backend.agents.base_agent import BaseAgent

__all__ = [
    "BaseAgent",
    "PerceptionAgent",
    "AnalysisAgent",
    "ReportAgent",
    "AlertAgent",
    "OrchestratorAgent",
]

_LAZY_AGENTS = {
    "PerceptionAgent": "backend.agents.perception_agent",
    "AnalysisAgent": "backend.agents.analysis_agent",
    "ReportAgent": "backend.agents.report_agent",
    "AlertAgent": "backend.agents.alert_agent",
    "OrchestratorAgent": "backend.agents.orchestrator_agent",
}


def __getattr__(name: str):
    """惰性导入业务智能体，避免 langchain 未安装时拖垮通用框架导入。"""
    if name in _LAZY_AGENTS:
        import importlib

        module = importlib.import_module(_LAZY_AGENTS[name])
        agent_cls = getattr(module, name)
        globals()[name] = agent_cls
        return agent_cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
