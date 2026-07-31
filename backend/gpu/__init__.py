"""
GPU 信息模块 — 提供GPU检测、状态查询API端点。

用法:
  from backend.gpu import detect_gpu, get_gpu_status
  info = detect_gpu()  # {"available": True, "vendor": "MetaX", ...}
"""

from __future__ import annotations
from backend.vibraimage.gpu_backend import detect_gpu as _vib_gpu_detect, is_gpu_available


def detect_gpu() -> dict:
    """检测GPU并返回完整信息。"""
    return _vib_gpu_detect()


def get_gpu_status() -> dict:
    """
    获取GPU运行状态快照（供健康检查API使用）。

    Returns:
        dict: {"available": bool, "backend": str, "device": str,
               "vendor": str, "model": str, "memory_mb": int}
    """
    info = _vib_gpu_detect()
    return {
        "available": info["available"],
        "backend": info["backend"],
        "device": info["device"],
        "vendor": info["vendor"],
        "model": info["model"],
        "memory_mb": info["memory_mb"],
    }


def register_gpu_routes(app):
    """
    注册GPU状态API端点到FastAPI应用。

    GET /api/gpu/status → GPU健康检查
    """
    from fastapi import APIRouter
    router = APIRouter(prefix="/api/gpu", tags=["GPU算力"])

    @router.get("/status", summary="GPU算力状态")
    async def gpu_status():
        """返回当前GPU状态：是否可用、后端类型、厂商型号。"""
        return {
            "success": True,
            "data": get_gpu_status(),
        }

    app.include_router(router)
