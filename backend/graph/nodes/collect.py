from __future__ import annotations
import os
from backend.graph.state import InnerLoopState
from backend.config import get_settings


def collect_node(state: InnerLoopState) -> dict:
    video_path = state.get("video_path", "")
    trigger_type = state.get("trigger_type", "scheduled")
    settings = get_settings()

    if trigger_type == "scheduled":
        student_id = state["student_id"]
        from datetime import datetime
        ts = datetime.now().strftime("%H%M")
        default_path = os.path.join(settings.camera_dir, f"student_{student_id}_{ts}.mp4")
        if video_path:
            pass
        else:
            video_path = default_path

    if not video_path:
        return {"error": "缺少视频路径，无法采集数据"}

    return {"video_path": video_path, "trigger_type": trigger_type}
