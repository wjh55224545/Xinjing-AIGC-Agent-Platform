"""
智能体基类 (BaseAgent)
======================

为心镜·AIGC智能体平台提供统一的智能体基类。
每个智能体独立拥有:
- 自己的 System Prompt（角色定义）
- 自己的工具集（LangChain Tools）
- 自己的 LLM 实例
- 独立的推理和执行能力

这实现了真正的多智能体协作架构，每个智能体各司其职。
"""

from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

try:
    from langgraph.prebuilt import create_react_agent
    from langchain_core.tools import BaseTool as LangChainBaseTool
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False
    create_react_agent = None  # type: ignore
    LangChainBaseTool = object  # type: ignore

from backend.llm.platform_adapter import get_llm, get_platform_info

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    智能体抽象基类

    所有智能体必须实现:
    - name: 智能体名称（中文）
    - description: 智能体职责描述
    - system_prompt: 系统提示词
    - _setup_tools(): 配置工具集
    """

    # 子类必须定义
    name: str = "BaseAgent"
    description: str = "智能体基类"

    def __init__(self, streaming: bool = True, platform: str | None = None):
        self.streaming = streaming
        self.platform = platform
        self._llm = None
        self._agent = None
        self._tools: list[LangChainBaseTool] = []
        self._setup_tools()
        logger.info(f"智能体 [{self.name}] 初始化完成, 平台={self._get_platform_name()}")

    @abstractmethod
    def _setup_tools(self) -> None:
        """子类实现：配置智能体的工具集"""
        pass

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """子类实现：获取智能体的System Prompt"""
        pass

    def _get_platform_name(self) -> str:
        """获取当前使用的平台名称"""
        try:
            info = get_platform_info()
            return info.get("name", "未知平台")
        except Exception:
            return "未知平台"

    @property
    def llm(self):
        """延迟初始化 LLM 实例"""
        if self._llm is None:
            self._llm = get_llm(platform=self.platform, streaming=self.streaming)
        return self._llm

    def build_agent(self):
        """
        构建 LangGraph ReAct Agent

        优先使用 prebuilt create_react_agent（支持 function calling 的平台），
        moark.com 等不支持的平台自动降级到 prompt-based 模式。
        """
        if not _LANGGRAPH_AVAILABLE:
            raise ImportError("langgraph 未安装，请运行: pip install langgraph")
        if self._agent is not None:
            return self._agent

        try:
            info = get_platform_info()
            platform_id = info.get("platform", "")
        except Exception:
            platform_id = ""

        # moark.com (lingshu) 平台不支持 function calling，使用空 tools 的 ReAct
        # 实际工具调用在 think() 方法中通过 prompt-based 循环完成
        if platform_id == "lingshu" or self.platform == "lingshu":
            self._agent = create_react_agent(
                model=self.llm,
                tools=[],  # 空工具列表，避免 function calling
                state_modifier=self._get_system_prompt(),
            )
            logger.info(f"智能体 [{self.name}] prompt-based Agent已构建 "
                       f"(lingshu平台), 工具数={len(self._tools)}")
        else:
            self._agent = create_react_agent(
                model=self.llm,
                tools=self._tools,
                state_modifier=self._get_system_prompt(),
            )
            logger.info(f"智能体 [{self.name}] ReAct Agent已构建, 工具数={len(self._tools)}")
        return self._agent

    async def think(self, message: str, context: dict | None = None) -> dict:
        """
        让智能体推理并返回结果

        Args:
            message: 用户消息/任务描述
            context: 附加上下文信息

        Returns:
            包含推理结果和工具调用的字典
        """
        full_message = message
        if context:
            context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
            full_message = f"{message}\n\n上下文信息:\n{context_str}"

        # lingshu 平台：prompt-based 工具调用循环
        if self.platform == "lingshu":
            return await self._think_prompt_react(full_message)

        agent = self.build_agent()
        result = await agent.ainvoke({"messages": [("user", full_message)]})

        messages = result.get("messages", [])
        final_message = messages[-1].content if messages else ""

        return {
            "agent_name": self.name,
            "final_answer": final_message,
            "messages": [str(m) for m in messages],
            "platform": self._get_platform_name(),
        }

    async def _think_prompt_react(self, user_message: str) -> dict:
        """
        Prompt-based ReAct 循环（用于不支持 function calling 的 lingshu 平台）。

        通过系统提示词描述工具，LLM 以 <tool_call>JSON</tool_call> 输出请求，
        Agent 在 Python 侧执行工具后将结果回传 LLM 继续推理。
        """
        import re as _re
        import json as _json

        MAX_ITERATIONS = 5

        # 构建带工具描述的系统提示词
        tool_descs = []
        for t in self._tools:
            t_name = getattr(t, 'name', 'unknown')
            t_desc = getattr(t, 'description', '')
            tool_descs.append(f"- **{t_name}**: {t_desc}")
        tool_list = "\n".join(tool_descs) if tool_descs else "无可用工具"

        react_sys = f"""{self._get_system_prompt()}

## 工具使用说明

你需要通过指定格式来请求工具调用。当需要使用工具时，输出：

<tool_call>
{{"name": "工具名称", "arguments": {{"参数名": "参数值"}} }}
</tool_call>

系统会自动执行工具并把结果返回给你，你基于结果继续推理。

## 当前可用工具

{tool_list}

## 规则
1. 一次只请求一个工具调用
2. JSON 必须合法且参数名与工具定义一致
3. 最终答案用自然语言，不要包含 <tool_call> 标签
4. 不需要工具就直接回答"""

        history = [{"role": "system", "content": react_sys}]
        all_messages = []
        executed_tools = set()  # 防止重复调用同一工具

        for iteration in range(MAX_ITERATIONS):
            # 构建用户消息
            if iteration == 0:
                history.append({"role": "user", "content": user_message})
            all_messages.append(("user" if iteration == 0 else "system", user_message if iteration == 0 else ""))

            # 调用 LLM
            try:
                result = self.llm.invoke(history)
                response = result.content if hasattr(result, 'content') else str(result)
            except Exception as e:
                logger.error(f"LLM调用失败: {e}")
                response = f"[LLM调用失败: {e}]"

            all_messages.append(("assistant", response))
            history.append({"role": "assistant", "content": response})

            # 检查是否有工具调用（支持 <tool_call> 标签和裸 JSON 两种格式）
            tool_json = None
            match = _re.search(
                r'<tool_call>\s*(.*?)\s*</tool_call>', response, _re.DOTALL
            )
            if match:
                tool_json = match.group(1)
            else:
                # 尝试匹配裸 JSON 格式: {"name": "...", "arguments": {...}}
                json_match = _re.search(
                    r'\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}\s*\}',
                    response, _re.DOTALL
                )
                if json_match:
                    tool_json = json_match.group(0)

            if not tool_json:
                return {
                    "agent_name": self.name,
                    "final_answer": response,
                    "messages": [str(m) for m in all_messages],
                    "platform": self._get_platform_name(),
                }

            # 解析并执行工具
            try:
                tool_req = _json.loads(tool_json)
                tool_name = tool_req.get("name", "")
                tool_args = tool_req.get("arguments", {})
            except _json.JSONDecodeError:
                # JSON 解析失败，可能不是真正的工具调用，返回答案
                return {
                    "agent_name": self.name,
                    "final_answer": response,
                    "messages": [str(m) for m in all_messages],
                    "platform": self._get_platform_name(),
                }

            # 防止重复调用同一工具（循环检测）
            call_key = f"{tool_name}:{_json.dumps(tool_args, sort_keys=True)}"
            if call_key in executed_tools:
                return {
                    "agent_name": self.name,
                    "final_answer": response,
                    "messages": [str(m) for m in all_messages],
                    "platform": self._get_platform_name(),
                }
            executed_tools.add(call_key)

            # 执行工具
            tool_result = f"错误: 未找到工具 '{tool_name}'"
            for tool in self._tools:
                if getattr(tool, 'name', '') == tool_name:
                    try:
                        tool_result = str(tool.invoke(tool_args))[:2000]
                    except Exception as e:
                        tool_result = f"工具执行失败: {e}"
                    break

            all_messages.append(("tool_result", tool_result))
            history.append({
                "role": "user",
                "content": f"[工具 {tool_name} 的执行结果]\n{tool_result}\n\n请基于以上结果继续推理。"
            })
            logger.info(f"Agent [{self.name}] 执行工具: {tool_name}")

        # 超过最大迭代次数
        return {
            "agent_name": self.name,
            "final_answer": all_messages[-1][1] if all_messages else "",
            "messages": [str(m) for m in all_messages],
            "platform": self._get_platform_name(),
        }

    async def stream_think(self, message: str, context: dict | None = None):
        """
        流式推理（生成器），用于SSE推送

        Yields:
            dict: 每个推理步骤的事件
        """
        full_message = message
        if context:
            context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
            full_message = f"{message}\n\n上下文信息:\n{context_str}"

        agent = self.build_agent()

        async for event in agent.astream_events(
            {"messages": [("user", full_message)]},
            version="v2",
        ):
            kind = event.get("event", "")
            data = event.get("data", {})

            if kind == "on_chat_model_stream":
                chunk = data.get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield {
                        "event": "thought",
                        "content": chunk.content,
                        "agent_name": self.name,
                        "platform": self._get_platform_name(),
                    }

            elif kind == "on_tool_start":
                yield {
                    "event": "action",
                    "tool": data.get("name", "未知工具"),
                    "input": data.get("input", {}),
                    "agent_name": self.name,
                }

            elif kind == "on_tool_end":
                yield {
                    "event": "observation",
                    "tool": data.get("name", "未知工具"),
                    "result": str(data.get("output", ""))[:500],
                    "agent_name": self.name,
                }

        yield {
            "event": "final",
            "content": f"[{self.name}] 推理完成",
            "agent_name": self.name,
            "platform": self._get_platform_name(),
        }

    def get_info(self) -> dict:
        """获取智能体信息"""
        return {
            "name": self.name,
            "description": self.description,
            "tools": [t.name for t in self._tools],
            "platform": self._get_platform_name(),
            "streaming": self.streaming,
        }

    def add_tool(self, tool: LangChainBaseTool) -> None:
        """动态添加工具"""
        self._tools.append(tool)
        self._agent = None  # 重置agent以使用新工具集

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}: {self.name}>"
