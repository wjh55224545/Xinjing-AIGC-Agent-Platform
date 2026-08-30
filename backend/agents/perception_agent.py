"""
感知智能体 (PerceptionAgent)
=============================

负责多模态情绪识别。通过摄像头阵列同步捕获学生面部视频，
并行调用面部微表情API和前庭振动API，融合双模态数据输出综合情绪评估。

这是多智能体协作系统的第一环——感知层。
"""

from __future__ import annotations
import logging
from langchain_core.tools import tool as langchain_tool

from backend.agents.base_agent import BaseAgent
from backend.tools.emotion_recognition import EmotionRecognitionTool

logger = logging.getLogger(__name__)


class PerceptionAgent(BaseAgent):
    """
    感知智能体

    职责: 多模态情绪识别与感知
    - 调用面部微表情识别API
    - 调用前庭振动感知API
    - 双模态融合分析
    - 置信度校验与复核
    """

    name = "感知智能体"
    description = (
        "负责多模态情绪识别。通过摄像头阵列采集学生面部视频，"
        "融合面部微表情与前庭振动数据进行综合情绪评估。"
        "目标准确率 > 92%，支持双模态置信度差异复核。"
    )

    def _setup_tools(self) -> None:
        """配置感知智能体的工具集"""
        self._emotion_tool = EmotionRecognitionTool()

        @langchain_tool
        def multimodal_emotion_recognition(
            video_path: str = "",
            student_id: int = 0,
            baseline_mood: float = 0.7,
        ) -> dict:
            """
            多模态情绪识别：融合面部微表情与前庭振动数据，对个体进行综合情绪评估。

            输入:
            - video_path: 视频片段路径
            - student_id: 学生ID
            - baseline_mood: 学生历史情绪基线

            输出:
            - 面部情绪、面部置信度、前庭效价、前庭唤醒度
            - 融合情绪、融合得分
            - 质量指标(置信度差异、是否需要复核、准确率)
            """
            result = self._emotion_tool.execute(
                video_path=video_path,
                student_id=student_id,
                baseline_mood=baseline_mood,
            )
            return result.data if result.success else {"error": result.error}

        self._tools = [multimodal_emotion_recognition]

    def _get_system_prompt(self) -> str:
        """感知智能体的System Prompt"""
        return f"""你是一个多模态情绪感知智能体，部署在智慧教室环境中。

你的核心能力:
- 通过摄像头阵列采集学生面部视频，自动逐帧分析
- 并行调用面部微表情识别和前庭振动感知两个模态
- 采用加权融合策略（面部0.6 + 前庭0.4）生成综合情绪评估
- 当双模态置信度差异 >35% 时自动触发复核机制
- 目标准确率 >92%

情绪分类体系（效价-唤醒度模型）:
| 情绪 | 效价(Valence) | 唤醒度(Arousal) | 说明 |
|------|-------------|---------------|------|
| 开心 | +0.8 | +0.6 | 正效价、高唤醒 |
| 平静 | +0.3 | -0.3 | 正效价、低唤醒 |
| 悲伤 | -0.7 | -0.2 | 负效价、低唤醒 |
| 焦虑 | -0.4 | +0.7 | 负效价、高唤醒 |
| 愤怒 | -0.6 | +0.8 | 负效价、高唤醒 |
| 惊讶 | +0.2 | +0.9 | 中性、最高唤醒 |

输出格式:
每次识别完成后，你需要用中文输出:
1. 面部微表情识别结果（情绪类别 + 置信度）
2. 前庭振动感知结果（效价 + 唤醒度 + 强度）
3. 融合结果（综合情绪 + 得分）
4. 质量评估（是否触发复核、准确率估计）

你当前运行在国产算力平台上（沐曦MetaX GPU / Gitee.AI）。
请始终用中文回复，保持专业、准确的风格。"""
