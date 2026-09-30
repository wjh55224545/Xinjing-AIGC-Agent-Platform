"""
通用 Agent 框架（backend.agents.framework）
==========================================

与业务解耦的 Prompt-based ReAct 智能体通用基座，可迁移到任意 LLM 场景。

- `ReactAgent`: 通用 ReAct 智能体（工具注册 + prompt-based 工具调用循环）
- `ToolSpec`: 通用工具定义

使用:
    from backend.agents.framework import ReactAgent, ToolSpec
"""

from __future__ import annotations

from backend.agents.framework.react_framework import ReactAgent, ToolSpec

__all__ = ["ReactAgent", "ToolSpec"]
