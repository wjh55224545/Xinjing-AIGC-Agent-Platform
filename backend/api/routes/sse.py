"""
SSE 流式推送路由

统一 SSE 流式端点，复用 Agent 路由中的触发端点。
"""

from __future__ import annotations
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.graph.orchestrator import get_orchestrator

router = APIRouter(tags=["SSE流式"])


@router.get("/sse/stream/{run_id}")
async def stream_agent(run_id: str, request: Request):
    """SSE 流式端点——订阅智能体协作事件流。触发操作请使用 /api/agents/trigger/*"""
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
