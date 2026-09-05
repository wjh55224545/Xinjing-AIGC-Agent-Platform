from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models.emotion_record import EmotionRecord
from backend.tools.emotion_recognition import EmotionRecognitionTool
from backend.tools.vestibular_recognition import VestibularRecognitionTool
from backend.tools.multi_modal_fusion import MultiModalEmotionFuser
from backend.tools.obs_storage import OBSPersistenceTool


class EmotionService:
    """情绪服务：面部 + 前庭双模态融合。"""

    def __init__(self, db: Session):
        self.db = db
        self.emotion_tool = EmotionRecognitionTool()
        self.vestibular_tool = VestibularRecognitionTool()
        self.fuser = MultiModalEmotionFuser()
        self.obs_tool = OBSPersistenceTool()

    def process_emotion(
        self,
        student_id: int,
        image_path: str,
        video_path: str = "",
        trigger_type: str = "manual",
    ) -> dict:
        """
        处理情绪识别请求，融合面部与前庭结果。

        Args:
            student_id: 学生 ID
            image_path: 图片路径（用于面部识别）
            video_path: 视频路径（用于前庭识别），可选
            trigger_type: 触发类型（manual / auto）
        """
        # 1. 面部情绪识别
        # 优先使用视频多帧平均；无视频时回退单帧图片
        facial_kwargs = {"student_id": student_id}
        if video_path:
            facial_kwargs["video_path"] = video_path
        else:
            facial_kwargs["image_path"] = image_path
        facial_result = self.emotion_tool.execute(**facial_kwargs)
        if not facial_result.success:
            return {"error": facial_result.error}

        # 2. 前庭情绪识别（如果提供视频路径）
        vestibular_result = None
        if video_path:
            vestibular_result = self.vestibular_tool.execute(video_path=video_path)
            if vestibular_result.success:
                vestibular_data = vestibular_result.data
            else:
                # 前庭识别失败，仅使用面部结果
                vestibular_data = {}
        else:
            vestibular_data = {}

        # 3. 双模态融合
        fused_data = {}
        if vestibular_data:
            # 构造融合输入
            facial_input = {
                "facial_valence": facial_result.data.get("facial_valence", 0.0),
                "facial_arousal": facial_result.data.get("facial_arousal", 0.0),
                "facial_emotion": facial_result.data.get("facial_emotion", "中性"),
                "emotion_probs": facial_result.data.get("emotion_probs", {}),
            }

            vestibular_input = {
                "valence": vestibular_data.get("valence", 0.0),
                "arousal": vestibular_data.get("arousal", 0.0),
                "vestibular_emotion": vestibular_data.get("emotion", "中性"),
                "window_results": vestibular_data.get("window_results", []),
            }

            fused_result = self.fuser.fuse(facial_input, vestibular_input)
            if fused_result is not None:
                fused_data = fused_result.to_dict()

        # 4. 提取各模态字段（前庭字段直接来自前庭工具，融合字段来自 fuser）
        facial_valence = facial_result.data.get("facial_valence", 0.0)
        facial_arousal = facial_result.data.get("facial_arousal", 0.0)

        vestibular_valence = vestibular_data.get("valence", 0.0)
        vestibular_arousal = vestibular_data.get("arousal", 0.0)
        vestibular_confidence = vestibular_data.get("confidence", 0.0)
        vestibular_intensity = vestibular_data.get("intensity", 0.0)

        fused_valence = fused_data.get("fused_valence", 0.0)
        fused_arousal = fused_data.get("fused_arousal", 0.0)
        fused_conf = fused_data.get("fused_conf", 0.0)
        # 融合标签：7 类基本情绪（设计规范第5步），无前庭数据时回退面部标签
        fused_emotion = (
            fused_data.get("fused_emotion_7")
            or facial_result.data.get("facial_emotion", "未知")
        )

        # 质量指标
        c_face = fused_data.get("c_face", 0.0)
        c_vi = fused_data.get("c_vi", 0.0)
        confidence_diff = abs(c_face - c_vi)
        estimated_accuracy = fused_conf if fused_data else facial_result.data.get("facial_conf", 0.0)
        # 模态一致性复核（设计规范第5步）: d = sqrt((V_face-V_vi)²+(A_face-A_vi)²)
        # d > 0.5 → 需复核（由 fuser 计算 modal_inconsistent 并随 fused_data 持久化）
        requires_review = 1 if fused_data.get("modal_inconsistent", False) else 0

        # 5. 写入数据库
        record = EmotionRecord(
            student_id=student_id,
            image_path=image_path,
            facial_emotion=facial_result.data.get("facial_emotion", "未知"),
            facial_conf=facial_result.data.get("facial_conf", 0.0),
            facial_valence=facial_valence,
            facial_arousal=facial_arousal,
            vestibular_valence=vestibular_valence,
            vestibular_arousal=vestibular_arousal,
            vestibular_confidence=vestibular_confidence,
            vestibular_intensity=vestibular_intensity,
            fused_emotion=fused_emotion,
            fused_score=fused_conf,
            fused_valence=fused_valence,
            fused_arousal=fused_arousal,
            confidence_diff=confidence_diff,
            requires_review=requires_review,
            estimated_accuracy=estimated_accuracy,
            is_manual=1 if trigger_type == "manual" else 0,
            recorded_at=datetime.now().isoformat(),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        # 5. 持久化完整数据
        _ = self.obs_tool.execute(record_id=record.id, data={
            **facial_result.data,
            **vestibular_data,
            **fused_data,
        })

        return {
            "record_id": record.id,
            **facial_result.data,
            **vestibular_data,
            **fused_data,
        }
