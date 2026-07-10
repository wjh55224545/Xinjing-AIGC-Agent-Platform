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
