"""
分析智能体 (AnalysisAgent)
===========================

负责心理健康深度分析。从数据库/OBS拉取学生7天情绪时序数据，
调用EmotionDataPreprocessor进行统计预处理，将结构化指标提交给
Lingshu-32B医疗大模型进行专业心理分析（风险模式识别、趋势预测、干预建议）。

这是多智能体协作系统的第二环——分析层。
"""

from __future__ import annotations
import logging
from langchain_core.tools import tool as langchain_tool

from backend.agents.base_agent import BaseAgent
from backend.tools.mental_health import EmotionDataPreprocessor

logger = logging.getLogger(__name__)


class AnalysisAgent(BaseAgent):
    """
    分析智能体

    职责: 心理健康深度分析
    - 从数据库拉取7天情绪时序数据
    - 数据预处理（统计指标计算）
    - 提交给Lingshu-32B大模型进行专业心理分析
    - 风险等级判定(绿色/黄色/红色)
    - 生成个性化建议
    """

    name = "分析智能体"
    description = (
        "负责心理健康深度分析。预处理7天情绪时序数据，"
        "提交给Lingshu-32B医疗大模型进行风险模式识别、趋势预测和干预建议生成。"
    )

    def _setup_tools(self) -> None:
        """配置分析智能体的工具集"""
        self._preprocessor = EmotionDataPreprocessor()

        @langchain_tool
        def mental_health_analysis(
            student_id: int = 0,
            records: list | None = None,
            baseline: float = 0.7,
            obs_records: list | None = None,
            analysis_window_days: int = 7,
        ) -> dict:
            """
            情绪数据预处理：统计学生7天情绪数据，计算结构化指标，为LLM分析提供上下文。

            输入:
            - student_id: 学生ID
            - records: 当日情绪记录列表
            - baseline: 历史情绪基线
            - obs_records: OBS历史数据
            - analysis_window_days: 分析窗口天数

            输出:
            - 统计指标（稳定性、熵、趋势等12项）
            - 规则兜底风险等级
            - 模板建议
            """
            result = self._preprocessor.execute(
                student_id=student_id,
                records=records or [],
                baseline=baseline,
                obs_records=obs_records,
                analysis_window_days=analysis_window_days,
            )
            return result.data if result.success else {"error": result.error}

        self._tools = [mental_health_analysis]

    def _get_system_prompt(self) -> str:
        """分析智能体的System Prompt"""
        return f"""你是一个心理健康分析智能体，基于Lingshu-32B医疗大模型，专注于学生心理状态的深度分析。

你的核心能力:
- 读取系统预处理后的情绪统计指标（情绪稳定性、波动熵、趋势斜率等）
- 基于统计数据识别风险模式和异常时段
- 评估风险等级（绿色/黄色/红色）
- 预测短期情绪趋势
- 给出可操作的个性化干预建议

系统提供的12项统计指标:
  1. 情绪稳定性指数  2. 情绪波动熵值  3. 负面情绪累积度
  4. 社交互动频次    5. 日间情绪趋势  6. 唤醒度异常指数
  7. 情绪恢复速度    8. 压力累积指数  9. 积极情绪占比
  10. 情绪突变检测   11. 综合心理健康评分

风险等级参考标准:
- 🟢 绿色: 综合评分 ≥ 0.7，心理健康状态良好
- 🟡 黄色: 综合评分 0.4-0.7，需要关注
- 🔴 红色: 综合评分 < 0.4，需要紧急干预

分析维度:
- 情绪稳定性: 方差归一化评估
- 负面情绪累积: 重点关注悲伤、焦虑、愤怒的连续出现
- 恢复能力: 负面→正面情绪转换速率
- 压力水平: 综合负面+高唤醒指标

你当前运行在国产算力平台上（沐曦MetaX GPU / moark.com Lingshu-32B）。
请始终用中文回复，专业、共情、有建设性。"""
