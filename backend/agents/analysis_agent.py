"""
分析智能体 (AnalysisAgent)
===========================

负责心理健康深度分析。从数据库/OBS拉取学生7天情绪时序数据，
计算12项心理健康指标，使用LSTM-Transformer混合模型识别风险模式，
输出风险等级和具体建议。

这是多智能体协作系统的第二环——分析层。
"""

from __future__ import annotations
import logging
from langchain_core.tools import tool as langchain_tool

from backend.agents.base_agent import BaseAgent
from backend.tools.mental_health import MentalHealthAnalysisTool

logger = logging.getLogger(__name__)


class AnalysisAgent(BaseAgent):
    """
    分析智能体

    职责: 心理健康深度分析
    - 从数据库拉取7天情绪时序数据
    - 计算12项心理健康指标
    - LSTM-Transformer混合模型时序分析
    - 风险等级判定(绿色/黄色/红色)
    - 生成具体建议
    """

    name = "分析智能体"
    description = (
        "负责心理健康深度分析。基于LSTM-Transformer混合模型，"
        "计算12项心理健康指标，识别异常情绪模式，"
        "输出绿色/黄色/红色风险等级及具体建议。"
    )

    def _setup_tools(self) -> None:
        """配置分析智能体的工具集"""
        self._mh_tool = MentalHealthAnalysisTool()

        @langchain_tool
        def mental_health_analysis(
            student_id: int = 0,
            records: list | None = None,
            baseline: float = 0.7,
            obs_records: list | None = None,
            analysis_window_days: int = 7,
        ) -> dict:
            """
            时序心理分析：基于LSTM-Transformer混合模型分析学生7天情绪数据。

            输入:
            - student_id: 学生ID
            - records: 当日情绪记录列表
            - baseline: 历史情绪基线
            - obs_records: OBS历史数据
            - analysis_window_days: 分析窗口天数

            输出:
            - 12项心理健康指标
            - LSTM-Transformer分析结果
            - 风险等级(green/yellow/red)
            - 个性化建议
            - 次日情绪预测（95%置信区间）
            """
            result = self._mh_tool.execute(
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
        return f"""你是一个心理健康分析智能体，专注于学生心理状态的深度分析。

你的核心能力:
- 从数据库拉取学生7天情绪时序数据，构建时序特征矩阵
- 计算12项心理健康指标:
  1. 情绪稳定性指数  2. 情绪波动熵值  3. 负面情绪累积度
  4. 社交互动频次    5. 日间情绪趋势  6. 唤醒度异常指数
  7. 情绪恢复速度    8. 睡眠质量预测  9. 压力累积指数
  10. 积极情绪占比   11. 情绪突变检测  12. 综合心理健康评分
- 使用LSTM提取短期模式+长期依赖，Transformer注意力机制识别风险时段
- 预测次日情绪趋势（95%置信区间）

风险等级判定标准:
- 🟢 绿色: 综合评分 ≥ 0.7，心理健康状态良好
- 🟡 黄色: 综合评分 0.4-0.7，需要关注
- 🔴 红色: 综合评分 < 0.4，需要紧急干预

分析维度:
- 情绪稳定性: 方差归一化评估
- 负面情绪累积: 重点关注悲伤、焦虑、愤怒的连续出现
- 恢复能力: 负面→正面情绪转换速率
- 压力水平: 综合负面+高唤醒指标

你当前运行在国产算力平台上（沐曦MetaX GPU / Gitee.AI）。
请始终用中文回复，专业、共情、有建设性。"""
