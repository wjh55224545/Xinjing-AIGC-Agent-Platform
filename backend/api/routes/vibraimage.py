"""
VibraImage前庭振动分析 API路由。

提供:
- POST /api/vibraimage/analyze    离线视频分析
- GET  /api/vibraimage/health      引擎健康检查
"""
from __future__ import annotations
import os
import uuid
from datetime import datetime

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.config import get_settings
from backend.tools.vestibular_recognition import VestibularRecognitionTool

router = APIRouter(prefix="/api/vibraimage", tags=["VibraImage前庭振动"])


@router.get("/health")
def vibraimage_health():
    """检查VibraImage引擎是否就绪。"""
    try:
        from backend.vibraimage import __version__ as vi_version
        import cv2
        cv2_ok = True
    except ImportError:
        vi_version = "unknown"
        cv2_ok = False

    try:
        from ultralytics import YOLO
        yolo_ok = True
    except ImportError:
        yolo_ok = False

    model_path = get_settings().vibraimage_model_path
    model_exists = os.path.exists(os.path.abspath(model_path)) if model_path else False

    return {
        "status": "ok" if (cv2_ok and yolo_ok and model_exists) else "degraded",
        "vibraimage_version": vi_version,
        "opencv_available": cv2_ok,
        "yolo_available": yolo_ok,
        "model_exists": model_exists,
        "model_path": str(os.path.abspath(model_path)) if model_path else None,
    }


@router.get("/norms")
def vibraimage_norms():
    """
    返回 E1–E12 常模数据（10,266 人）、Z-Score 标准化参数、参数中文名与 K 值解释。

    用途：前端教学实验组件做「个体 vs 常模」对照可视化（雷达图/百分位）。
    数据来源：VCE.pdf (Minkin, 2020) Table 6-18 "All" 列（N=10,266）。
    """
    from backend.vibraimage.utils.constants import (
        NORMAL_NORMS,
        NORMAL_SDS,
        PARAM_NAMES_ZH,
        K_INTERPRETATION,
        STANDARDIZATION_FACTORS,
        ALL_EMOTION_PARAMS,
        NEGATIVE_EMOTIONS,
        POSITIVE_EMOTIONS,
        PHYSIOLOGICAL_EMOTIONS,
    )

    params = []
    for p in ALL_EMOTION_PARAMS:
        group = (
            "negative" if p in NEGATIVE_EMOTIONS
            else "positive" if p in POSITIVE_EMOTIONS
            else "physiological"
        )
        params.append({
            "key": p,
            "name_zh": PARAM_NAMES_ZH.get(p, p),
            "norm_mean": NORMAL_NORMS.get(p),
            "norm_sd": NORMAL_SDS.get(p),
            "standardization_factor": STANDARDIZATION_FACTORS.get(p),
            "group": group,
        })

    return {
        "success": True,
        "data": {
            "source": "VCE.pdf (Minkin, 2020) Table 6-18 'All' 列",
            "sample_size": 10266,
            "params": params,
            "k_interpretation": [
                {"label": "稳定（|K|<3）", "desc": K_INTERPRETATION.get((-float('inf'), 3))},
                {"label": "关注（3≤|K|<6）", "desc": K_INTERPRETATION.get((3, 6))},
                {"label": "预警（|K|≥6）", "desc": K_INTERPRETATION.get((6, float('inf')))},
            ],
        },
    }


@router.get("/latest")
def vibraimage_latest(student_id: int | None = None):
    """
    返回最近一条包含 E1–E12 的情绪记录，用于教学实验页的「个体 vs 常模」对照。

    若指定 student_id 则返回该学生最近记录，否则返回全库最近记录。
    当数据库中仅有早期记录（未含 E1-E12 字段）时，自动基于常模均值生成一组
    演示参数（demo=true），保证教学实验组件可直接演示「个体 vs 常模」对照。
    """
    from backend.database import SessionLocal
    from backend.models.emotion_record import EmotionRecord
    from backend.vibraimage.utils.constants import NORMAL_NORMS, K_INTERPRETATION

    db = SessionLocal()
    try:
        q = db.query(EmotionRecord)
        if student_id is not None:
            q = q.filter(EmotionRecord.student_id == student_id)
        rec = q.order_by(EmotionRecord.recorded_at.desc()).first()
        if rec is None:
            return {"success": False, "detail": "暂无情绪记录，请先上传视频或触发采集"}

        def g(field):
            v = getattr(rec, field, None)
            return round(float(v), 2) if v is not None else None

        e_params = {
            "aggression": g("vi_aggression"),
            "stress": g("vi_stress"),
            "tension": g("vi_tension"),
            "suspicious": g("vi_suspect"),
            "balance": g("vi_balance"),
            "charm": g("vi_charm"),
            "energy": g("vi_energy"),
            "self_regulation": g("vi_self_regulation"),
            "inhibition": g("vi_inhibition"),
            "neuroticism": g("vi_neuroticism"),
            "depression": g("vi_depression"),
            "happiness": g("vi_happiness"),
        }
        k_value = g("vi_K_value")
        demo = False

        if all(v is None for v in e_params.values()):
            # 早期记录未含 E1-E12 字段 → 以常模均值叠加小扰动生成演示参数
            demo = True
            for i, key in enumerate(e_params):
                mean = NORMAL_NORMS.get(key)
                base = mean if mean is not None else 50.0
                e_params[key] = round(base + ((i % 5) - 2) * 2.8, 2)
            if k_value is None:
                k_value = 3.6

        # K 值解释（按区间）
        k_text = None
        if k_value is not None:
            for (lo, hi), text in K_INTERPRETATION.items():
                if lo <= abs(k_value) < hi:
                    k_text = text
                    break
            if k_text is None:
                k_text = rec.vi_K_interpretation

        return {
            "success": True,
            "demo": demo,
            "data": {
                "record_id": rec.id,
                "student_id": rec.student_id,
                "recorded_at": rec.recorded_at,
                "demo": demo,
                "e_params": e_params,
                "k_value": k_value,
                "k_interpretation": k_text,
                "fused_emotion": rec.fused_emotion,
                "fused_score": round(rec.fused_score, 3),
            },
        }
    finally:
        db.close()


@router.post("/analyze")
async def analyze_video(
    file: UploadFile = File(...),
    student_id: int = Form(...),
    db: Session = Depends(get_db),
):
    """
    对上传的视频执行VibraImage前庭振动分析。

    返回:
    - E1-E12情绪参数
    - K值心理状态指标
    - 效价-唤醒度映射
    - 逐窗口趋势数据
    """
    settings = get_settings()
    os.makedirs(settings.upload_dir, exist_ok=True)

    # 保存上传视频
    ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    filename = f"vi_{student_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(settings.upload_dir, filename)
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    # 执行VibraImage分析
    tool = VestibularRecognitionTool()
    result = tool.execute(video_path=save_path)

    if not result.success:
        raise HTTPException(status_code=500, detail=result.error)

    return {
        "success": True,
        "student_id": student_id,
        "video_path": save_path,
        "result": result.data,
    }
