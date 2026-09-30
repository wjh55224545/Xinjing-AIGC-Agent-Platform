"""
通用 Prompt-based ReAct 智能体框架（可复用组件）
==================================================

一个与业务场景解耦的通用 ReAct 智能体基座，可迁移到任何 LLM 场景：
心理评估、客服、文档处理、多模态分析等。

设计要点:
- 不依赖 LangChain：仅要求 LLM 提供一个 OpenAI 兼容的 chat 调用接口
- 不依赖具体业务：工具通过 `ToolSpec` 注册，场景代码自行注入
- Prompt-based 工具调用：LLM 输出 <tool_call>JSON</tool_call> 标签请求工具，
  框架在 Python 侧执行工具并回传结果继续推理（适配不支持 function
  calling 的国产大模型，如 lingshu/moark 平台）

用法:
    from backend.agents.framework import ReactAgent, ToolSpec

    def calc_add(a: int, b: int) -> int:
        return a + b

    agent = ReactAgent(
        name="计算助手",
        description="做算术运算",
        system_prompt="你是一个计算助手，需要时调用工具。",
        llm=llm,                      # OpenAI 兼容 chat 接口
        tools=[ToolSpec("add", "加法运算", calc_add, {"a": "int", "b": "int"})],
    )
    result = agent.run("3 + 4 等于多少？")
"""

from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class ToolSpec:
    """
    通用工具定义。

    Parameters
    ----------
    name : str
        工具名，LLM 通过该名称调用。
    description : str
        工具功能描述（会注入系统提示词）。
    func : Callable
        工具执行函数，接收 `arguments` 字典。
    arguments : dict
        参数 schema 描述（name -> 类型/说明），用于提示 LLM 生成合法 JSON。
    """

    name: str
    description: str
    func: Callable[..., Any]
    arguments: dict[str, str] = field(default_factory=dict)

    def invoke(self, arguments: dict[str, Any]) -> str:
        """执行工具并返回字符串结果。"""
        try:
            result = self.func(**arguments)
            return str(result)[:2000]
        except Exception as e:  # noqa: BLE001 - 工具异常需反馈给 LLM
            return f"工具执行失败: {e}"


class ReactAgent:
    """
    通用 Prompt-based ReAct 智能体。

    Attributes
    ----------
    name : str
        智能体名称。
    description : str
        智能体职责描述。
    system_prompt : str
        角色系统提示词。
    llm : Any
        OpenAI 兼容 chat 接口（必须有 `.invoke(messages)` 返回带 `.content` 的对象）。
    tools : list[ToolSpec]
        注册的工具列表。
    """

    def __init__(
        self,
        name: str,
        description: str,
        system_prompt: str,
        llm: Any,
        tools: Optional[list[ToolSpec]] = None,
        max_iterations: int = 5,
    ):
        self.name = name
        self.description = description
        self.system_prompt = system_prompt
        self.llm = llm
        self.tools: list[ToolSpec] = list(tools or [])
        self.max_iterations = max_iterations
        logger.info(f"[ReactAgent] 初始化: {name}, 工具数={len(self.tools)}")

    # ------------------------------------------------------------------
    # 工具注册
    # ------------------------------------------------------------------
    def add_tool(self, tool: ToolSpec) -> None:
        """动态注册一个工具。"""
        self.tools.append(tool)

    def get_tool(self, name: str) -> Optional[ToolSpec]:
        """按名称查找工具。"""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None

    # ------------------------------------------------------------------
    # 提示词构建
    # ------------------------------------------------------------------
    def _build_react_prompt(self) -> str:
        """构建带工具描述的 ReAct 系统提示词。"""
        tool_lines = []
        for t in self.tools:
            arg_desc = ", ".join(f"{k}: {v}" for k, v in t.arguments.items())
            tool_lines.append(f"- **{t.name}**: {t.description} (参数: {arg_desc or '无'})")
        tool_list = "\n".join(tool_lines) if tool_lines else "无可用工具"

        return f"""{self.system_prompt}

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

    # ------------------------------------------------------------------
    # 工具调用解析
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_tool_call(response: str) -> Optional[dict]:
        """从 LLM 输出中解析工具调用（支持 <tool_call> 标签与裸 JSON）。"""
        match = re.search(r"<tool_call>\s*(.*?)\s*</tool_call>", response, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        # 裸 JSON: {"name": "...", "arguments": {...}}
        json_match = re.search(
            r'\{[^{}]*"name"\s*:\s*"[^"]+"\s*,\s*"arguments"\s*:\s*\{[^{}]*\}\s*\}',
            response,
            re.DOTALL,
        )
        if json_match:
            return json.loads(json_match.group(0))
        return None

    # ------------------------------------------------------------------
    # 核心循环
    # ------------------------------------------------------------------
    def run(self, user_message: str, context: Optional[dict] = None) -> dict:
        """
        执行一轮 ReAct 推理循环。

        Parameters
        ----------
        user_message : str
            用户消息/任务描述。
        context : dict, optional
            附加上下文（键值对拼接到消息尾部）。

        Returns
        -------
        dict:
            {"final_answer": str, "messages": list[str], "tool_calls": list[str]}
        """
        full_message = user_message
        if context:
            context_str = "\n".join(f"- {k}: {v}" for k, v in context.items())
            full_message = f"{user_message}\n\n上下文信息:\n{context_str}"

        history: list[dict] = [
            {"role": "system", "content": self._build_react_prompt()},
            {"role": "user", "content": full_message},
        ]
        messages: list[str] = []
        tool_calls: list[str] = []
        executed: set[str] = set()

        for _ in range(self.max_iterations):
            result = self.llm.invoke(history)
            response = result.content if hasattr(result, "content") else str(result)
            messages.append(response)
            history.append({"role": "assistant", "content": response})

            try:
                tool_req = self._parse_tool_call(response)
            except (json.JSONDecodeError, ValueError):
                return self._done(messages, tool_calls, response)

            if tool_req is None:
                return self._done(messages, tool_calls, response)

            tool_name = tool_req.get("name", "")
            tool_args = tool_req.get("arguments", {})

            # 循环检测：相同工具+参数不重复执行
            call_key = f"{tool_name}:{json.dumps(tool_args, sort_keys=True)}"
            if call_key in executed:
                return self._done(messages, tool_calls, response)
            executed.add(call_key)

            tool = self.get_tool(tool_name)
            if tool is None:
                tool_result = f"错误: 未找到工具 '{tool_name}'"
            else:
                tool_result = tool.invoke(tool_args)
            tool_calls.append(tool_name)

            messages.append(f"[工具 {tool_name} 执行结果]\n{tool_result}")
            history.append({
                "role": "user",
                "content": f"[工具 {tool_name} 的执行结果]\n{tool_result}\n\n请基于以上结果继续推理。",
            })

        return self._done(messages, tool_calls, messages[-1] if messages else "")

    def _done(self, messages: list[str], tool_calls: list[str], final: str) -> dict:
        """构造返回结果。"""
        return {
            "final_answer": final,
            "messages": messages,
            "tool_calls": tool_calls,
        }

    def get_info(self) -> dict:
        """智能体信息（用于 API 展示）。"""
        return {
            "name": self.name,
            "description": self.description,
            "tools": [t.name for t in self.tools],
            "max_iterations": self.max_iterations,
        }

    def __repr__(self) -> str:
        return f"<ReactAgent: {self.name}>"
