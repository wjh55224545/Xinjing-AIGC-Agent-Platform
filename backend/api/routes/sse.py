from __future__ import annotations
import json
import uuid
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.graph.orchestrator import get_orchestrator

router = APIRouter(tags=["流式"])


@router.get("/agent/stream/{run_id}")
async def stream_agent(run_id: str, request: Request):
    orchestrator = get_orchestrator()
    queue = orchestrator.get_queue(run_id)

    async def generate():
        while True:
            if await request.is_disconnected():
                break
            try:
                data = await queue.get()
                event_type = data.pop("event", "message")
                payload = json.dumps(data, ensure_ascii=False)
                yield f"event: {event_type}\ndata: {payload}\n\n"
                if event_type == "final":
                    break
            except Exception:
                break

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/agent/trigger/inner")
async def trigger_inner():
    from backend.database import SessionLocal
    from backend.models.student import Student
    db = SessionLocal()
    try:
        students = db.query(Student).all()
    finally:
        db.close()

    run_id = str(uuid.uuid4())
    orchestrator = get_orchestrator()
    _ = orchestrator.get_queue(run_id)
    import asyncio
    for s in students:
        asyncio.create_task(
            orchestrator.run_inner_loop(
                student_id=s.id, video_path="",
                trigger_type="scheduled", run_id=run_id,
            )
        )

    return {"success": True, "run_id": run_id, "message": f"已触发{len(students)}名学生的内环采集",
            "records_created": 0}


@router.post("/agent/trigger/outer")
async def trigger_outer():
    from datetime import date
    run_id = str(uuid.uuid4())
    orchestrator = get_orchestrator()
    _ = orchestrator.get_queue(run_id)
    import asyncio
    asyncio.create_task(
        orchestrator.run_outer_loop(target_date=str(date.today()), run_id=run_id)
    )

    return {"success": True, "run_id": run_id, "message": f"已触发{date.today()}外环分析",
            "records_created": 0}
