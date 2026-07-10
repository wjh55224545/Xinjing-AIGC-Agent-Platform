from __future__ import annotations
from backend.database import SessionLocal
from backend.models.student import Student
from backend.tools.emotion_recognition import EmotionRecognitionTool
from backend.graph.state import InnerLoopState


def recognize_node(state: InnerLoopState) -> dict:
    """
    识别节点 - 执行多模态情绪识别

    增强版功能：
    - 集成面部微表情与前庭振动双模态识别
    - 加权融合策略生成综合情绪评估
    - 置信度差异校验（超过35%触发复核机制）
    - 与学生基线对比检测异常
    """
    tool = EmotionRecognitionTool()

    # 获取学生基线
    db = SessionLocal()
    try:
        student = db.query(Student).filter(Student.id == state["student_id"]).first()
        baseline = student.baseline_mood if student else 0.7
    finally:
        db.close()

    result = tool.execute(
        video_path=state["video_path"],
        student_id=state.get("student_id"),
        baseline_mood=baseline,
    )

    if not result.success:
        return {"error": result.error}

    # 返回所有识别结果
    return {**result.data}
