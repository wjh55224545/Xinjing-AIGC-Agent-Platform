# -*- coding: utf-8 -*-
"""
通用 Prompt-based ReAct 框架测试（backend.agents.framework）
============================================================

覆盖: ToolSpec 工具执行 / ReactAgent 工具注册 / ReAct 循环 /
      循环检测 / 未知工具 / 无工具直答 / 上下文注入。

说明: 使用内存假 LLM，不依赖外部 API 与 langchain 环境。
"""

import os
import sys
from dataclasses import dataclass

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.agents.framework import ReactAgent, ToolSpec  # noqa: E402


@dataclass
class FakeChatResult:
    """模拟 LLM 返回对象（.content 属性）。"""

    content: str


class ScriptedLLM:
    """按脚本顺序返回内容的假 LLM。"""

    def __init__(self, responses: list[str]):
        self.responses = list(responses)
        self.calls: list[list[dict]] = []

    def invoke(self, messages: list[dict]):
        self.calls.append(messages)
        if self.responses:
            return FakeChatResult(self.responses.pop(0))
        return FakeChatResult("（结束）")


def _add(a: int, b: int) -> int:
    return a + b


def _echo(text: str) -> str:
    return f"echo:{text}"


def _build_agent(llm, tools=None, name="测试助手", system_prompt="你是测试助手。"):
    return ReactAgent(
        name=name,
        description="测试用智能体",
        system_prompt=system_prompt,
        llm=llm,
        tools=tools or [],
    )


class TestToolSpec:
    """工具定义"""

    def test_tool_executes_and_returns_str(self):
        """工具正常执行并返回字符串。"""
        tool = ToolSpec("add", "加法", _add, {"a": "int", "b": "int"})
        result = tool.invoke({"a": 3, "b": 4})
        assert result == "7"

    def test_tool_error_returned_as_message(self):
        """工具抛异常时返回错误信息而非崩溃。"""

        def boom():
            raise ValueError("bad")

        tool = ToolSpec("boom", "会炸", boom)
        result = tool.invoke({})
        assert "工具执行失败" in result


class TestToolRegistration:
    """工具注册"""

    def test_add_and_get_tool(self):
        """add_tool 注册后可通过 get_tool 取回。"""
        llm = ScriptedLLM([])
        agent = _build_agent(llm)
        tool = ToolSpec("add", "加法", _add)
        agent.add_tool(tool)
        assert agent.get_tool("add") is tool
        assert agent.get_tool("missing") is None

    def test_get_info_lists_tools(self):
        """get_info 返回名称/描述/工具列表。"""
        llm = ScriptedLLM([])
        agent = _build_agent(llm, tools=[ToolSpec("add", "加法", _add)])
        info = agent.get_info()
        assert info["name"] == "测试助手"
        assert "add" in info["tools"]


class TestReactLoop:
    """ReAct 循环"""

    def test_direct_answer_without_tool(self):
        """无工具调用时直接返回最终答案。"""
        llm = ScriptedLLM(["你好，我是测试助手。"])
        agent = _build_agent(llm)
        result = agent.run("打个招呼")
        assert result["final_answer"] == "你好，我是测试助手。"
        assert result["tool_calls"] == []

    def test_tool_call_flow(self):
        """工具调用循环：请求工具 -> 执行 -> 回传 -> 最终答案。"""
        llm = ScriptedLLM([
            '<tool_call>{"name": "add", "arguments": {"a": 3, "b": 4}}</tool_call>',
            "结果是 7。",
        ])
        agent = _build_agent(llm, tools=[ToolSpec("add", "加法", _add, {"a": "int", "b": "int"})])
        result = agent.run("3+4=?")
        assert result["final_answer"] == "结果是 7。"
        assert result["tool_calls"] == ["add"]
        # 第二次 LLM 调用应包含工具执行结果
        assert any("7" in str(m) for m in llm.calls[1])

    def test_multiple_tool_calls_sequential(self):
        """连续多次工具调用。"""
        llm = ScriptedLLM([
            '<tool_call>{"name": "add", "arguments": {"a": 1, "b": 2}}</tool_call>',
            '<tool_call>{"name": "echo", "arguments": {"text": "done"}}</tool_call>',
            "全部完成。",
        ])
        agent = _build_agent(llm, tools=[
            ToolSpec("add", "加法", _add),
            ToolSpec("echo", "回显", _echo, {"text": "str"}),
        ])
        result = agent.run("测试")
        assert result["final_answer"] == "全部完成。"
        assert result["tool_calls"] == ["add", "echo"]

    def test_unknown_tool_returns_error_feedback(self):
        """未知工具时返回错误反馈给 LLM。"""
        llm = ScriptedLLM([
            '<tool_call>{"name": "nope", "arguments": {}}</tool_call>',
            "该工具不可用。",
        ])
        agent = _build_agent(llm)
        result = agent.run("调用不存在的工具")
        assert "该工具不可用。" in result["final_answer"]

    def test_loop_detection_stops_repeated_calls(self):
        """相同工具+参数重复调用被循环检测终止。"""
        llm = ScriptedLLM([
            '<tool_call>{"name": "add", "arguments": {"a": 1, "b": 2}}</tool_call>',
            '<tool_call>{"name": "add", "arguments": {"a": 1, "b": 2}}</tool_call>',
        ])
        agent = _build_agent(llm, tools=[ToolSpec("add", "加法", _add)])
        result = agent.run("循环")
        # 循环检测后返回当前响应
        assert result["tool_calls"] == ["add"]

    def test_max_iterations_bound(self):
        """超过最大迭代次数后终止并返回最后内容。"""
        responses = ['<tool_call>{"name": "add", "arguments": {"a": 1, "b": 2}}</tool_call>'] * 10
        llm = ScriptedLLM(responses)
        agent = _build_agent(llm, tools=[ToolSpec("add", "加法", _add)])
        agent.max_iterations = 3
        result = agent.run("压力测试")
        assert len(llm.calls) <= 4  # 初始 + 最多 3 轮

    def test_context_injected_into_message(self):
        """context 键值对拼接进用户消息。"""
        llm = ScriptedLLM(["基于上下文回答。"])
        agent = _build_agent(llm)
        agent.run("分析", context={"性别": "男", "年龄": "20"})
        first_user_msg = llm.calls[0][1]["content"]
        assert "性别" in first_user_msg
        assert "年龄" in first_user_msg


class TestReactPrompt:
    """提示词构建"""

    def test_prompt_contains_tools_and_rules(self):
        """系统提示词包含工具描述与调用规则。"""
        llm = ScriptedLLM(["回答"])
        agent = _build_agent(llm, tools=[
            ToolSpec("add", "加法", _add, {"a": "int", "b": "int"}),
        ])
        prompt = agent._build_react_prompt()
        assert "add" in prompt
        assert "tool_call" in prompt
        assert "一次只请求一个工具调用" in prompt
