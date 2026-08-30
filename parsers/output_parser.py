"""
智能体 LLM 输出解析器
=====================

解析 LLM 输出的 ReAct 格式：
    Thought: ...
    Action: <工具名>
    Action Input: {json}

或直接结束：
    Final Answer: <回答文本>

能力：
  - Action / Final Answer 优先级（同时出现时 Action 优先）
  - 工具白名单校验（拒绝未授权工具，防注入）
  - Action Input 容错解析：标准 JSON、key='value'、key=value、key=中文值
  - 无 Action 且无 Final Answer 时返回错误信息
"""

from __future__ import annotations
import json
import re

# 平台已注册工具白名单（含项目真实工具 + 通用扩展工具）
TOOL_WHITELIST = {
    # ---- 项目真实工具（backend/tools/）----
    "多模态情绪识别",       # EmotionRecognitionTool
    "前庭振动识别",          # VestibularRecognitionTool
    "情绪数据预处理",        # MentalHealthAnalysisTool
    "华为云OBS持久化",       # ObsStorageTool
    "多渠道反馈",            # FeedbackTool
    "时序心理分析",          # TimeSeriesAnalysisTool
    # ---- 通用扩展工具 ----
    "EmotionDetector",
    "Search",
    "Calculator",
}


def _extract(text: str, label: str) -> str | None:
    """按标签提取首行内容，兼容半角/全角冒号。"""
    pattern = re.compile(
        rf"^\s*{re.escape(label)}\s*[:：]\s*(.+?)\s*$",
        re.MULTILINE,
    )
    m = pattern.search(text)
    return m.group(1).strip() if m else None


def _parse_action_input(raw: str) -> dict:
    """容错解析 Action Input。"""
    raw = raw.strip()
    if not raw:
        return {}
    # 标准 JSON
    try:
        value = json.loads(raw)
        if isinstance(value, dict):
            return value
    except (json.JSONDecodeError, TypeError):
        pass
    # 兼容外层花括号
    if raw.startswith("{") and raw.endswith("}"):
        try:
            value = json.loads(raw)
            if isinstance(value, dict):
                return value
        except (json.JSONDecodeError, TypeError):
            pass

    # 容错：key='value', key=value, key="value", key=中文值
    result: dict = {}
    # 去掉包裹花括号
    body = raw.strip()
    if body.startswith("{") and body.endswith("}"):
        body = body[1:-1]
    # 按逗号切分（忽略引号内的逗号）
    parts = _split_top_level(body)
    for part in parts:
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^([A-Za-z_][\w]*)\s*=\s*(.*)$", part, re.DOTALL)
        if not m:
            continue
        key, val = m.group(1), m.group(2).strip()
        val = val.strip()
        if (val.startswith("'") and val.endswith("'")) or (
            val.startswith('"') and val.endswith('"')
        ):
            val = val[1:-1]
        # 尝试转成数字 / 布尔
        result[key] = _coerce(val)
    return result


def _split_top_level(body: str) -> list[str]:
    """按顶层逗号切分，忽略引号/括号内的逗号。"""
    parts: list[str] = []
    depth = 0
    in_str: str | None = None
    current: list[str] = []
    for ch in body:
        if in_str:
            current.append(ch)
            if ch == in_str:
                in_str = None
            continue
        if ch in "'\"":
            in_str = ch
            current.append(ch)
        elif ch in "[{(":
            depth += 1
            current.append(ch)
        elif ch in "]})":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current))
    return parts


def _coerce(val: str):
    """尽力把字符串转成数字/布尔。"""
    if val in ("true", "True"):
        return True
    if val in ("false", "False"):
        return False
    if val in ("null", "None"):
        return None
    try:
        if re.fullmatch(r"-?\d+", val):
            return int(val)
        if re.fullmatch(r"-?\d+\.\d+", val):
            return float(val)
    except ValueError:
        pass
    return val


def parse_agent_output(text: str) -> dict:
    """
    解析智能体输出。

    Returns:
        - 有 Action：{action, action_input}
        - 有 Final Answer：{final_answer}
        - 无法解析 / 非法工具：{error, ...}
    """
    if not text or not text.strip():
        return {"error": "输出为空"}

    action = _extract(text, "Action")
    action_input_raw = _extract(text, "Action Input")
    final_answer = _extract(text, "Final Answer")

    # Action 优先级高于 Final Answer
    if action:
        action = action.strip()
        if action not in TOOL_WHITELIST:
            return {
                "error": f"未授权工具：{action}",
                "action": action,
                "allowed_tools": sorted(TOOL_WHITELIST),
            }
        try:
            action_input = _parse_action_input(action_input_raw or "")
        except Exception:
            action_input = {}
        return {"action": action, "action_input": action_input}

    if final_answer:
        return {"final_answer": final_answer}

    return {"error": "输出中未识别到 Action 或 Final Answer，请检查 LLM 输出格式"}
