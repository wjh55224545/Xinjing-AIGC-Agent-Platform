from __future__ import annotations
import uuid
from datetime import date
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.database import SessionLocal
from backend.models.student import Student

scheduler = AsyncIOScheduler()


async def trigger_inner_loop_job():
    from backend.graph.orchestrator import get_orchestrator
    db = SessionLocal()
    try:
        students = db.query(Student).all()
    finally:
        db.close()

    if not students:
        return

    orchestrator = get_orchestrator()
    run_id = str(uuid.uuid4())
    _ = orchestrator.get_queue(run_id)
    for s in students:
        await orchestrator.run_inner_loop(
            student_id=s.id,
            video_path="",  # 空路径，让collect_node按时间戳生成
            trigger_type="scheduled",
            run_id=run_id,
        )


async def trigger_outer_loop_job():
    from backend.graph.orchestrator import get_orchestrator
    orchestrator = get_orchestrator()
    run_id = str(uuid.uuid4())
    _ = orchestrator.get_queue(run_id)
    await orchestrator.run_outer_loop(
        target_date=str(date.today()),
        run_id=run_id,
    )


def start_scheduler():
    scheduler.add_job(trigger_inner_loop_job, "interval", minutes=15, id="inner_loop",
                      replace_existing=True)
    scheduler.add_job(trigger_outer_loop_job, "cron", hour=22, minute=0, id="outer_loop",
                      replace_existing=True)
    if not scheduler.running:
        scheduler.start()
