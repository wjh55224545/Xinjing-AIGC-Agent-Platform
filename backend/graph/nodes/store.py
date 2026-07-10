from __future__ import annotations
from datetime import datetime
from backend.database import SessionLocal
from backend.models.student import Student
from backend.models.emotion_record import EmotionRecord
from backend.tools.obs_storage import OBSPersistenceTool
from backend.graph.state import InnerLoopState


def store_node(state: InnerLoopState) -> dict:
    """
    存储节点 - 将情绪识别结果保存到数据库并上传至OBS

    增强版功能：
    - 保存完整的双模态识别结果（面部+前庭）
    - 调用OBS持久化工具，按学校/班级/学号/日期层级存储
    - 支持复核机制（当置信度差异超过阈值时标记）
    """
    db = SessionLocal()
    try:
        # 获取学生信息用于OBS存储
        student = db.query(Student).filter(Student.id == state["student_id"]).first()
        student_info = {
            "student_id": state["student_id"],
            "student_code": student.student_code if student else "unknown",
            "name": student.name if student else "未知",
            "class_name": student.class_name if student else "",
            "school": getattr(student, 'school', ''),
            "baseline_mood": student.baseline_mood if student else 0.7,
        }

        # 创建情绪记录
        record = EmotionRecord(
            student_id=state["student_id"],
            image_path=state["video_path"],

            # 面部微表情识别结果
            facial_emotion=state.get("facial_emotion", "未知"),
            facial_conf=state.get("facial_conf", 0.0),
            facial_valence=state.get("facial_valence", 0.0),
            facial_arousal=state.get("facial_arousal", 0.0),

            # 前庭振动识别结果
            vestibular_valence=state.get("vestibular_valence", 0.0),
            vestibular_arousal=state.get("vestibular_arousal", 0.0),
            vestibular_confidence=state.get("vestibular_confidence", 0.0),
            vestibular_intensity=state.get("vestibular_intensity", 0.0),

            # VibraImage E1-E12 情绪参数
            vi_aggression=state.get("vi_aggression"),
            vi_stress=state.get("vi_stress"),
            vi_tension=state.get("vi_tension"),
            vi_suspect=state.get("vi_suspect"),
            vi_balance=state.get("vi_balance"),
            vi_charm=state.get("vi_charm"),
            vi_energy=state.get("vi_energy"),
            vi_self_regulation=state.get("vi_self_regulation"),
            vi_inhibition=state.get("vi_inhibition"),
            vi_neuroticism=state.get("vi_neuroticism"),
            vi_depression=state.get("vi_depression"),
            vi_happiness=state.get("vi_happiness"),
            vi_stability=state.get("vi_stability"),
            vi_K_value=state.get("vi_K_value"),
            vi_K_interpretation=state.get("vi_K_interpretation"),
            vi_n_windows=state.get("vi_n_windows"),
            vi_duration_sec=state.get("vi_duration_sec"),

            # 融合结果
            fused_emotion=state.get("fused_emotion", "未知"),
            fused_score=state.get("fused_score", 0.0),
            fused_valence=state.get("fused_valence", 0.0),
            fused_arousal=state.get("fused_arousal", 0.0),

            # 质量指标
            confidence_diff=state.get("confidence_diff", 0.0),
            requires_review=1 if state.get("requires_review", False) else 0,
            estimated_accuracy=state.get("estimated_accuracy", 0.92),

            # 触发类型
            is_manual=1 if state.get("trigger_type") == "manual" else 0,
            recorded_at=datetime.now().isoformat(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        record_id = record.id

        # 调用OBS持久化工具
        obs = OBSPersistenceTool()
        emotion_data = {
            # 面部微表情
            "facial_emotion": state.get("facial_emotion"),
            "facial_conf": state.get("facial_conf"),
            "facial_valence": state.get("facial_valence"),
            "facial_arousal": state.get("facial_arousal"),

            # 前庭振动
            "vestibular_valence": state.get("vestibular_valence"),
            "vestibular_arousal": state.get("vestibular_arousal"),
            "vestibular_confidence": state.get("vestibular_confidence"),
            "vestibular_intensity": state.get("vestibular_intensity"),

            # VibraImage E1-E12 + K值
            "vi_aggression": state.get("vi_aggression"),
            "vi_stress": state.get("vi_stress"),
            "vi_tension": state.get("vi_tension"),
            "vi_suspect": state.get("vi_suspect"),
            "vi_balance": state.get("vi_balance"),
            "vi_charm": state.get("vi_charm"),
            "vi_energy": state.get("vi_energy"),
            "vi_self_regulation": state.get("vi_self_regulation"),
            "vi_inhibition": state.get("vi_inhibition"),
            "vi_neuroticism": state.get("vi_neuroticism"),
            "vi_depression": state.get("vi_depression"),
            "vi_happiness": state.get("vi_happiness"),
            "vi_stability": state.get("vi_stability"),
            "vi_K_value": state.get("vi_K_value"),
            "vi_K_interpretation": state.get("vi_K_interpretation"),
            "vi_n_windows": state.get("vi_n_windows"),
            "vi_duration_sec": state.get("vi_duration_sec"),

            # 融合结果
            "fused_emotion": state.get("fused_emotion"),
            "fused_score": state.get("fused_score"),
            "fused_valence": state.get("fused_valence"),
            "fused_arousal": state.get("fused_arousal"),

            # 质量指标
            "confidence_diff": state.get("confidence_diff"),
            "requires_review": state.get("requires_review"),
            "estimated_accuracy": state.get("estimated_accuracy"),
            "processing_time_ms": state.get("processing_time_ms"),
        }

        obs_result = obs.execute(
            record_id=record_id,
            data=emotion_data,
            student_info=student_info,
        )

        return {
            "record_id": record_id,
            "stored": obs_result.success,
            "obs_key": obs_result.data.get("obs_key") if obs_result.success else None,
            "obs_full_path": obs_result.data.get("obs_full_path") if obs_result.success else None,
            "upload_id": obs_result.data.get("upload_id") if obs_result.success else None,
            "requires_review": state.get("requires_review", False),
            "error": "" if obs_result.success else obs_result.error,
        }
    except Exception as e:
        db.rollback()
        return {"error": str(e), "stored": False}
    finally:
        db.close()
