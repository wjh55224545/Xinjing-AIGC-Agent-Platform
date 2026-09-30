"""
通用 GPU 计算后端组件（可复用）— 自动探测 + 适配层

一个与业务解耦的国产算力适配组件，自动探测 MUSA (沐曦) / CUDA / CPU，
提供统一的数组模块、数据传输、直方图/FFT 兼容运算与基准测试接口。

用法:
  from backend.gpu import detect_gpu, get_array_module, to_gpu, to_cpu
  info = detect_gpu()                # {"available": True, "vendor": "MetaX", ...}
  xp = get_array_module()            # torch 或 numpy
  result = to_gpu(x)                 # 转移到 GPU
"""

from __future__ import annotations

from backend.gpu.backend import (
    detect_gpu,
    get_array_module,
    reset_array_module,
    is_gpu_available,
    to_gpu,
    to_cpu,
    ensure_float32,
    histogram,
    rfft,
    rfftfreq,
    benchmark_context,
    get_benchmark_records,
    clear_benchmark_records,
    get_gpu_info,
)

__all__ = [
    "detect_gpu",
    "get_array_module",
    "reset_array_module",
    "is_gpu_available",
    "to_gpu",
    "to_cpu",
    "ensure_float32",
    "histogram",
    "rfft",
    "rfftfreq",
    "benchmark_context",
    "get_benchmark_records",
    "clear_benchmark_records",
    "get_gpu_info",
]


def get_gpu_status() -> dict:
    """
    获取GPU运行状态快照（供健康检查API使用）。

    Returns:
        dict: {"available": bool, "backend": str, "device": str,
               "vendor": str, "model": str, "memory_mb": int}
    """
    info = detect_gpu()
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
