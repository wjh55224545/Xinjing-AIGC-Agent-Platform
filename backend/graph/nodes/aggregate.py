from __future__ import annotations
from datetime import datetime, timedelta
from backend.database import SessionLocal
from backend.models.emotion_record import EmotionRecord
from backend.graph.state import OuterLoopState


def aggregate_node(state: OuterLoopState) -> dict:
    """
    聚合节点 - 从数据库拉取学生的情绪记录

    增强版功能：
    - 拉取7天历史数据用于时序分析
    - 返回完整的双模态识别结果
    """
    target_date = state["target_date"]
    student_ids = state["student_ids"]
    db = SessionLocal()
    try:
        # 计算7天窗口
        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        start_date = (target_dt - timedelta(days=6)).strftime("%Y-%m-%d")

        daily_records: dict[int, list[dict]] = {}
        for sid in student_ids:
            records = (
                db.query(EmotionRecord)
                .filter(
                    EmotionRecord.student_id == sid,
                    EmotionRecord.recorded_at >= f"{start_date}T00:00:00",
                    EmotionRecord.recorded_at <= f"{target_date}T23:59:59",
                )
                .all()
            )
            daily_records[sid] = [
                {
                    # 基本信息
                    "id": r.id,
                    "recorded_at": r.recorded_at,

                    # 面部微表情
                    "facial_emotion": r.facial_emotion,
                    "facial_conf": r.facial_conf,
                    "facial_valence": r.facial_valence,
                    "facial_arousal": r.facial_arousal,

                    # 前庭振动
                    "vestibular_valence": r.vestibular_valence,
                    "vestibular_arousal": r.vestibular_arousal,
                    "vestibular_confidence": r.vestibular_confidence,
                    "vestibular_intensity": r.vestibular_intensity,

                    # 融合结果
                    "fused_emotion": r.fused_emotion,
                    "fused_score": r.fused_score,
                    "fused_valence": r.fused_valence,
                    "fused_arousal": r.fused_arousal,

                    # 质量指标
                    "confidence_diff": r.confidence_diff,
                    "requires_review": bool(r.requires_review),
                    "estimated_accuracy": r.estimated_accuracy,
                }
                for r in records
            ]
        return {"daily_records": daily_records}
    finally:
        db.close()
