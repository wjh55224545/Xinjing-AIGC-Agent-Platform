"""
Prompt 与解析器自动化测试
验证典型场景下 LLM 输出能被正确解析，确保智能体决策准确。
执行方式：python tests/test_prompt.py
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from parsers.output_parser import parse_agent_output


# ========== 原有8个测试（保持向后兼容） ==========

def test_emotion_detector_normal():
    """测试情绪识别工具正常调用"""
    llm_output = """
    Thought: 用户要求分析图片情绪，我有 EmotionDetector 工具，需要提供图片路径。
    Action: EmotionDetector
    Action Input: {"image_path": "/tmp/test.jpg"}
    """
    result = parse_agent_output(llm_output)
    assert "action" in result
    assert result["action"] == "EmotionDetector"
    assert result["action_input"]["image_path"] == "/tmp/test.jpg"
    print("✅ 测试1通过：正常情绪识别调用")


def test_search_tool():
    """测试搜索工具调用"""
    llm_output = """
    Thought: 需要查询抑郁症症状。
    Action: Search
    Action Input: {"query": "抑郁症症状"}
    """
    result = parse_agent_output(llm_output)
    assert result["action"] == "Search"
    assert result["action_input"]["query"] == "抑郁症症状"
    print("✅ 测试2通过：搜索工具调用")


def test_calculator_tool():
    """测试计算器工具调用"""
    llm_output = """
    Thought: 计算比例。
    Action: Calculator
    Action Input: {"expression": "3/25"}
    """
    result = parse_agent_output(llm_output)
    assert result["action"] == "Calculator"
    assert result["action_input"]["expression"] == "3/25"
    print("✅ 测试3通过：计算器调用")


def test_final_answer_direct():
    """测试直接返回最终答案（无工具调用）"""
    llm_output = """
    Thought: 这是一个简单的问候，不需要工具。
    Final Answer: 你好！我是心理监测助手，有什么可以帮你的吗？
    """
    result = parse_agent_output(llm_output)
    assert "final_answer" in result
    assert "你好" in result["final_answer"]
    print("✅ 测试4通过：直接 Final Answer")


def test_missing_action():
    """测试缺失 Action 的错误处理"""
    llm_output = "我不知道该怎么办。"
    result = parse_agent_output(llm_output)
    assert "error" in result
    print("✅ 测试5通过：缺失 Action 返回错误信息")


def test_invalid_json():
    """测试 Action Input 格式错误时的容错"""
    llm_output = """
    Thought: 测试错误格式
    Action: EmotionDetector
    Action Input: image_path='/tmp/error.jpg'
    """
    result = parse_agent_output(llm_output)
    assert result.get("action") == "EmotionDetector"
    assert result["action_input"]["image_path"] == "/tmp/error.jpg"
    print("✅ 测试6通过：非标准 JSON 格式容错")


def test_final_answer_after_action():
    """当输出同时包含 Action 和 Final Answer，应优先 Action"""
    llm_output = """
    Thought: 需要搜索。
    Action: Search
    Action Input: {"query": "心理健康"}
    Observation: ...
    Final Answer: 根据搜索结果...
    """
    result = parse_agent_output(llm_output)
    assert "action" in result
    print("✅ 测试7通过：Action 优先级高于 Final Answer")


def test_tool_whitelist():
    """测试非法工具名被拒绝"""
    llm_output = """
    Action: FakeTool
    Action Input: {"arg": "value"}
    """
    result = parse_agent_output(llm_output)
    assert "error" in result
    print("✅ 测试8通过：非法工具名检测")


# ========== 新增4个工具测试 ==========

def test_multimodal_emotion():
    """测试多模态情绪识别工具（新工具名）"""
    llm_output = """
    Thought: 用户要求分析图片情绪，使用多模态情绪识别工具。
    Action: 多模态情绪识别
    Action Input: {"image_path": "/tmp/test.jpg", "student_id": 1}
    """
    result = parse_agent_output(llm_output)
    assert result["action"] == "多模态情绪识别"
    assert result["action_input"]["image_path"] == "/tmp/test.jpg"
    assert result["action_input"]["student_id"] == 1
    print("✅ 测试9通过：多模态情绪识别工具调用")


def test_obs_tool():
    """测试华为云OBS持久化工具"""
    llm_output = """
    Thought: 需要将结果持久化。
    Action: 华为云OBS持久化
    Action Input: {"record_id": 42, "data": {"fused_emotion": "开心"}}
    """
    result = parse_agent_output(llm_output)
    assert result["action"] == "华为云OBS持久化"
    assert result["action_input"]["record_id"] == 42
    print("✅ 测试10通过：华为云OBS持久化工具调用")


def test_analysis_tool():
    """测试时序心理分析工具"""
    llm_output = """
    Thought: 需要对情绪数据进行时序分析。
    Action: 时序心理分析
    Action Input: {"student_id": 1, "records": [{"fused_score": 0.85}], "baseline": 0.72}
    """
    result = parse_agent_output(llm_output)
    assert result["action"] == "时序心理分析"
    assert result["action_input"]["student_id"] == 1
    print("✅ 测试11通过：时序心理分析工具调用")


def test_feedback_tool():
    """测试多渠道反馈工具"""
    llm_output = """
    Thought: 需要发送预警反馈。
    Action: 多渠道反馈
    Action Input: {"alert_id": 100, "severity": "yellow", "student_name": "张三", "content": "关注"}
    """
    result = parse_agent_output(llm_output)
    assert result["action"] == "多渠道反馈"
    assert result["action_input"]["severity"] == "yellow"
    print("✅ 测试12通过：多渠道反馈工具调用")


if __name__ == "__main__":
    test_emotion_detector_normal()
    test_search_tool()
    test_calculator_tool()
    test_final_answer_direct()
    test_missing_action()
    test_invalid_json()
    test_final_answer_after_action()
    test_tool_whitelist()
    test_multimodal_emotion()
    test_obs_tool()
    test_analysis_tool()
    test_feedback_tool()
    print("\n🎉 所有12个测试通过！")
