from __future__ import annotations
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.api.deps import get_db
from backend.graph.orchestrator import get_orchestrator
from backend.schemas.emotion import UploadResponse

router = APIRouter(tags=["上传"])


@router.post("/upload/image", response_model=UploadResponse)
async def upload_image(
    file: UploadFile = File(...),
    student_id: int = Form(...),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
    filename = f"{student_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(settings.upload_dir, filename)
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    run_id = str(uuid.uuid4())
    orchestrator = get_orchestrator()
    orchestrator.get_queue(run_id)
    import asyncio
    asyncio.create_task(
        orchestrator.run_inner_loop(
            student_id=student_id, video_path=save_path,
            trigger_type="manual", run_id=run_id,
        )
    )

    return UploadResponse(
        success=True, image_path=save_path, student_id=student_id,
        trigger_type="manual", run_id=run_id,
    )


@router.post("/upload/video", response_model=UploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    student_id: int = Form(...),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    os.makedirs(settings.upload_dir, exist_ok=True)
    ext = os.path.splitext(file.filename or "video.mp4")[1] or ".mp4"
    filename = f"{student_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}{ext}"
    save_path = os.path.join(settings.upload_dir, filename)
    content = await file.read()
    with open(save_path, "wb") as f:
        f.write(content)

    run_id = str(uuid.uuid4())
    orchestrator = get_orchestrator()
    orchestrator.get_queue(run_id)
    import asyncio
    asyncio.create_task(
        orchestrator.run_inner_loop(
            student_id=student_id, video_path=save_path,
            trigger_type="manual", run_id=run_id,
        )
    )

    return UploadResponse(
        success=True, image_path=save_path, student_id=student_id,
        trigger_type="manual", run_id=run_id,
    )
