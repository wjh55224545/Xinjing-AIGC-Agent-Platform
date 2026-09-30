# backend.agents.framework — 通用 Prompt-based ReAct 智能体框架

一个与业务场景解耦的 ReAct 智能体基座，可迁移到任何 LLM 应用：
心理评估、客服、文档处理、多模态分析等。

## 设计目标

- **不依赖 LangChain**：仅要求 LLM 提供 OpenAI 兼容的 chat 调用接口（`.invoke(messages)` 返回带 `.content` 的对象）
- **不依赖具体业务**：工具通过 `ToolSpec` 注册，场景代码自行注入
- **Prompt-based 工具调用**：适配不支持 function calling 的国产大模型（如 lingshu/moark），LLM 以 `<tool_call>JSON</tool_call>` 标签请求工具，框架在 Python 侧执行并回传结果

## 用法

```python
from backend.agents.framework import ReactAgent, ToolSpec

def calc_add(a: int, b: int) -> int:
    return a + b

agent = ReactAgent(
    name="计算助手",
    description="做算术运算",
    system_prompt="你是一个计算助手，需要时调用工具。",
    llm=llm,  # OpenAI 兼容 chat 接口
    tools=[ToolSpec("add", "加法运算", calc_add, {"a": "int", "b": "int"})],
)
result = agent.run("3 + 4 等于多少？")
# => {"final_answer": "7", "tool_calls": ["add"], "messages": [...]}
```

## 核心类

| 类 | 职责 |
|---|---|
| `ReactAgent` | 通用 ReAct 智能体：工具注册、提示词构建、工具调用循环（含循环检测）、结果返回 |
| `ToolSpec` | 通用工具定义：name / description / func / arguments schema |

## 在本仓库中的使用

心镜 5 个场景智能体（感知/分析/报告/预警/编排）基于本框架构建：
`backend/agents/base_agent.py` 将 LangChain 工具适配为 `ToolSpec` 后委托
`ReactAgent.run()` 执行 prompt-based ReAct 循环。
