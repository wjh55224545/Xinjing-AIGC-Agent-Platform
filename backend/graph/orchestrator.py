from __future__ import annotations
import asyncio
import uuid
from datetime import datetime
from functools import lru_cache
from typing import Any

from backend.database import SessionLocal
from backend.models.student import Student
from backend.graph.inner_loop import build_inner_loop
from backend.graph.outer_loop import build_outer_loop
from backend.graph.state import InnerLoopState, OuterLoopState


class Orchestrator:
    def __init__(self):
        self.inner_loop = build_inner_loop()
        self.outer_loop = build_outer_loop()
        self._queues: dict[str, asyncio.Queue] = {}
        self._results: dict[str, dict] = {}

    def get_queue(self, run_id: str) -> asyncio.Queue:
        if run_id not in self._queues:
            self._queues[run_id] = asyncio.Queue()
        return self._queues[run_id]

    def remove_queue(self, run_id: str):
        self._queues.pop(run_id, None)
        self._results.pop(run_id, None)

    async def _schedule_cleanup(self, run_id: str, delay: int = 60):
        await asyncio.sleep(delay)
        self.remove_queue(run_id)

    async def emit(self, run_id: str, event: str, data: dict[str, Any]):
        queue = self._queues.get(run_id)
        if queue:
            await queue.put({"event": event, **data})

    async def run_inner_loop(
        self, student_id: int, video_path: str,
        trigger_type: str = "manual", run_id: str | None = None,
    ) -> dict:
        run_id = run_id or str(uuid.uuid4())
        initial: InnerLoopState = {
            "student_id": student_id,
            "video_path": video_path,
            "trigger_type": trigger_type,
        }
        await self.emit(run_id, "thought", {
            "content": f"开始{trigger_type}模式情绪采集，学生ID={student_id}，视频={video_path}",
            "timestamp": datetime.now().isoformat(),
        })

        accumulated = dict(initial)
        async for step in self.inner_loop.astream(initial, stream_mode="updates"):
            for node_name, node_output in step.items():
                if node_output:
                    accumulated.update(node_output)
                    safe_output = {k: v for k, v in node_output.items()
                                   if not isinstance(v, (bytes, bytearray))}
                    await self.emit(run_id, "action", {
                        "tool": node_name, "input": {"student_id": student_id},
                        "timestamp": datetime.now().isoformat(),
                    })
                    await self.emit(run_id, "observation", {
                        "tool": node_name, "result": safe_output,
                        "timestamp": datetime.now().isoformat(),
                    })

        result = accumulated
        await self.emit(run_id, "final", {
            "answer": f"情绪采集完成: {result.get('fused_emotion', '未知')} (得分: {result.get('fused_score', 0)})",
            "timestamp": datetime.now().isoformat(),
            "result": {k: v for k, v in result.items() if not isinstance(v, (bytes, bytearray))},
        })
        self._results[run_id] = result
        asyncio.create_task(self._schedule_cleanup(run_id))
        return result

    async def run_outer_loop(self, target_date: str, run_id: str | None = None) -> dict:
        run_id = run_id or str(uuid.uuid4())
        db = SessionLocal()
        try:
            student_ids = [s.id for s in db.query(Student).all()]
        finally:
            db.close()

        initial: OuterLoopState = {
            "target_date": target_date,
            "student_ids": student_ids,
        }
        await self.emit(run_id, "thought", {
            "content": f"开始每日心理健康分析 [{target_date}]，涉及{len(student_ids)}名学生",
            "timestamp": datetime.now().isoformat(),
        })

        accumulated = dict(initial)
        async for step in self.outer_loop.astream(initial, stream_mode="updates"):
            for node_name, node_output in step.items():
                if node_output:
                    accumulated.update(node_output)
                    safe_output = {k: v for k, v in node_output.items()
                                   if not isinstance(v, (bytes, bytearray))}
                    await self.emit(run_id, "action", {
                        "tool": node_name, "input": {"target_date": target_date},
                        "timestamp": datetime.now().isoformat(),
                    })
                    await self.emit(run_id, "observation", {
                        "tool": node_name, "result": safe_output,
                        "timestamp": datetime.now().isoformat(),
                    })

        result = accumulated
        alert_count = len(result.get("alerts_generated", []))
        await self.emit(run_id, "final", {
            "answer": f"每日分析完成: 共{len(student_ids)}名学生，生成{alert_count}条预警",
            "timestamp": datetime.now().isoformat(),
            "result": {k: v for k, v in result.items() if not isinstance(v, (bytes, bytearray))},
        })
        self._results[run_id] = result
        asyncio.create_task(self._schedule_cleanup(run_id))
        return result


@lru_cache
def get_orchestrator() -> Orchestrator:
    return Orchestrator()
