from __future__ import annotations
import os
import uuid
import json
import logging
from datetime import date, datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.database import SessionLocal
from backend.models.student import Student

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()

SCHEDULER_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(SCHEDULER_LOG_DIR, exist_ok=True)
SCHEDULER_LOG_PATH = os.path.join(SCHEDULER_LOG_DIR, "scheduler.log")


def _log_scheduler_run(job_type: str, result: dict) -> None:
    """记录调度器执行结果。"""
    try:
        entry = {
            "timestamp": datetime.now().isoformat(),
            "job_type": job_type,
            "success": "error" not in result,
            "summary": str(result.get("error", "")) if "error" in result else (
                f"完成" if job_type == "inner" else
                f"分析{len(result.get('all_results', []))}名学生"
            ),
        }
        with open(SCHEDULER_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


async def trigger_inner_loop_job():
    from backend.graph.orchestrator import get_orchestrator
    db = SessionLocal()
    try:
        students = db.query(Student).all()
    finally:
        db.close()

    if not students:
        logger.info("调度: 无学生数据，跳过内环")
        _log_scheduler_run("inner", {"error": "无学生"})
        return

    orchestrator = get_orchestrator()
    run_id = str(uuid.uuid4())
    _ = orchestrator.get_queue(run_id)
    for s in students:
        await orchestrator.run_inner_loop(
            student_id=s.id,
            video_path="",
            trigger_type="scheduled",
            run_id=run_id,
        )
    logger.info(f"调度: 内环完成，{len(students)}名学生")
    _log_scheduler_run("inner", {"student_count": len(students)})


async def trigger_outer_loop_job():
    from backend.graph.orchestrator import get_orchestrator
    orchestrator = get_orchestrator()
    run_id = str(uuid.uuid4())
    _ = orchestrator.get_queue(run_id)
    result = await orchestrator.run_outer_loop(
        target_date=str(date.today()),
        run_id=run_id,
    )
    logger.info(f"调度: 外环完成")
    _log_scheduler_run("outer", result)


def start_scheduler():
    scheduler.add_job(trigger_inner_loop_job, "interval", minutes=15, id="inner_loop",
                      replace_existing=True)
    scheduler.add_job(trigger_outer_loop_job, "cron", hour=22, minute=0, id="outer_loop",
                      replace_existing=True)
    if not scheduler.running:
        scheduler.start()
