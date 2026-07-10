"""
智能体管理 API 路由
====================

提供多智能体系统信息查询和手动触发的REST API。
展示国产算力平台上的多Agent协作架构。
"""

from __future__ import annotations
import uuid
import logging
from datetime import date
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks

from backend.database import SessionLocal
from backend.models.student import Student

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["多智能体系统"])


@router.get("/info", summary="获取多智能体系统信息")
async def get_agents_info():
    """返回所有智能体的详细信息，展示多Agent协作架构"""
    try:
        from backend.agents.orchestrator_agent import OrchestratorAgent
        orch = OrchestratorAgent(streaming=False)
        return {"success": True, "data": orch.get_agent_info()}
    except Exception as e:
        logger.error(f"获取智能体信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/platform", summary="获取国产算力平台信息")
async def get_platform_info():
    """返回当前使用的国产算力平台信息"""
    try:
        from backend.llm.platform_adapter import PlatformAdapter
        platforms = PlatformAdapter.list_platforms()
        # 当前平台
        from backend.config import get_settings
        settings = get_settings()
        current = settings.ai_platform

        return {
            "success": True,
            "data": {
                "current_platform": current,
                "available_platforms": platforms,
                "domestic_gpu": "沐曦 MetaX GPU (via Gitee.AI)",
                "supports": [
                    "OpenAI兼容API",
                    "LangChain集成",
                    "流式推理(SSE)",
                    "多模型切换",
                    "自动Fallback",
                ],
            },
        }
    except Exception as e:
        logger.error(f"获取平台信息失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger/inner", summary="手动触发内环情绪采集")
async def trigger_inner_loop(background_tasks: BackgroundTasks):
    """手动触发一次全班情绪采集（感知智能体）"""
    try:
        from backend.agents.orchestrator_agent import OrchestratorAgent

        db = SessionLocal()
        try:
            students = db.query(Student).all()
        finally:
            db.close()

        if not students:
            return {"success": False, "message": "没有学生数据"}

        orch = OrchestratorAgent(streaming=True)
        run_id = str(uuid.uuid4())

        # 后台执行
        async def run():
            for s in students:
                await orch.run_inner_loop(
                    student_id=s.id,
                    video_path="",
                    trigger_type="manual",
                    run_id=run_id,
                )

        background_tasks.add_task(run)

        return {
            "success": True,
            "message": f"已触发 {len(students)} 名学生的情绪采集",
            "run_id": run_id,
            "students_count": len(students),
        }
    except Exception as e:
        logger.error(f"触发内环失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger/outer", summary="手动触发每日心理健康分析")
async def trigger_outer_loop(background_tasks: BackgroundTasks):
    """手动触发一次每日心理健康分析（分析→报告→预警 多Agent协作）"""
    try:
        from backend.agents.orchestrator_agent import OrchestratorAgent

        db = SessionLocal()
        try:
            students = db.query(Student).all()
            student_ids = [s.id for s in students]
            student_names = {s.id: s.name for s in students}
        finally:
            db.close()

        if not students:
            return {"success": False, "message": "没有学生数据"}

        orch = OrchestratorAgent(streaming=True)
        run_id = str(uuid.uuid4())
        target_date = str(date.today())

        async def run():
            await orch.run_outer_loop(
                target_date=target_date,
                student_ids=student_ids,
                student_names=student_names,
                run_id=run_id,
            )

        background_tasks.add_task(run)

        return {
            "success": True,
            "message": f"已触发每日分析: {target_date}, {len(students)} 名学生",
            "run_id": run_id,
            "target_date": target_date,
            "students_count": len(students),
            "workflow": "分析智能体 → AIGC报告智能体 → 预警智能体",
        }
    except Exception as e:
        logger.error(f"触发外环失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stream/{run_id}", summary="SSE流式端点")
async def stream_agent_events(run_id: str):
    """SSE流式端点——实时观看多智能体协作过程"""
    from fastapi.responses import StreamingResponse
    from backend.agents.orchestrator_agent import OrchestratorAgent

    orch = OrchestratorAgent()
    queue = orch.get_queue(run_id)

    async def event_generator():
        import asyncio
        import json
        while True:
            try:
                event_data = await asyncio.wait_for(queue.get(), timeout=30)
                yield f"event: {event_data.get('event', 'message')}\n"
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"
            except asyncio.TimeoutError:
                yield "event: heartbeat\ndata: {}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
