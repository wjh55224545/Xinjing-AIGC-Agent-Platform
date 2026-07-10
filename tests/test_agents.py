"""
多智能体系统测试
=================

测试多智能体协作系统的各项功能。
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestAgentCreation:
    """智能体创建测试"""

    def test_create_perception_agent(self):
        """测试创建感知智能体"""
        from backend.agents.perception_agent import PerceptionAgent
        agent = PerceptionAgent(streaming=False)
        assert agent.name == "感知智能体"
        info = agent.get_info()
        assert len(info["tools"]) >= 1

    def test_create_analysis_agent(self):
        """测试创建分析智能体"""
        from backend.agents.analysis_agent import AnalysisAgent
        agent = AnalysisAgent(streaming=False)
        assert agent.name == "分析智能体"
        info = agent.get_info()
        assert len(info["tools"]) >= 1

    def test_create_report_agent(self):
        """测试创建报告智能体（含AIGC工具）"""
        from backend.agents.report_agent import ReportAgent
        agent = ReportAgent(streaming=False)
        assert "AIGC" in agent.name
        info = agent.get_info()
        # 报告智能体应有4个AIGC工具
        assert len(info["tools"]) >= 4

    def test_create_alert_agent(self):
        """测试创建预警智能体"""
        from backend.agents.alert_agent import AlertAgent
        agent = AlertAgent(streaming=False)
        assert agent.name == "预警智能体"

    def test_create_orchestrator(self):
        """测试创建协调智能体"""
        from backend.agents.orchestrator_agent import OrchestratorAgent
        orch = OrchestratorAgent(streaming=False)
        assert orch.name == "协调智能体"
        info = orch.get_agent_info()
        assert len(info["agents"]) == 4

    def test_agent_platform_info(self):
        """测试智能体平台信息"""
        from backend.agents.perception_agent import PerceptionAgent
        agent = PerceptionAgent(streaming=False)
        info = agent.get_info()
        assert "platform" in info

    def test_orchestrator_get_queue(self):
        """测试协调智能体队列管理"""
        import asyncio
        from backend.agents.orchestrator_agent import OrchestratorAgent

        orch = OrchestratorAgent(streaming=False)
        queue = orch.get_queue("test-run-001")
        assert queue is not None
        assert isinstance(queue, asyncio.Queue)

        orch.remove_queue("test-run-001")


class TestBaseAgent:
    """智能体基类测试"""

    def test_base_agent_abstract(self):
        """测试基类为抽象类"""
        from backend.agents.base_agent import BaseAgent
        with pytest.raises(TypeError):
            BaseAgent()  # 不能直接实例化抽象类

    def test_agent_repr(self):
        """测试智能体字符串表示"""
        from backend.agents.perception_agent import PerceptionAgent
        agent = PerceptionAgent(streaming=False)
        repr_str = repr(agent)
        assert "PerceptionAgent" in repr_str
        assert agent.name in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
