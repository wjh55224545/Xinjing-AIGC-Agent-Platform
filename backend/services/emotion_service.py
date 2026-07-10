from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models.emotion_record import EmotionRecord
from backend.tools.emotion_recognition import EmotionRecognitionTool
from backend.tools.obs_storage import OBSPersistenceTool


class EmotionService:
    def __init__(self, db: Session):
        self.db = db
        self.emotion_tool = EmotionRecognitionTool()
        self.obs_tool = OBSPersistenceTool()

    def process_emotion(self, student_id: int, image_path: str, trigger_type: str = "manual") -> dict:
        result = self.emotion_tool.execute(image_path=image_path, student_id=student_id)
        if not result.success:
            return {"error": result.error}

        record = EmotionRecord(
            student_id=student_id, image_path=image_path,
            facial_emotion=result.data.get("facial_emotion", "未知"),
            facial_conf=result.data.get("facial_conf", 0.0),
            vestibular_valence=result.data.get("vestibular_valence", 0.0),
            vestibular_arousal=result.data.get("vestibular_arousal", 0.0),
            fused_emotion=result.data.get("fused_emotion", "未知"),
            fused_score=result.data.get("fused_score", 0.0),
            is_manual=1 if trigger_type == "manual" else 0,
            recorded_at=datetime.now().isoformat(),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        _ = self.obs_tool.execute(record_id=record.id, data=result.data)
        return {"record_id": record.id, **result.data}
