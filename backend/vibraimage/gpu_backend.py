"""
GPU计算后端 — 兼容转发层（已迁移至 backend.gpu 通用组件）
=========================================================

自 v2.9 起，完整的 GPU 适配实现已迁移至 `backend.gpu`（backend/gpu/backend.py），
本模块保留为兼容转发层，避免破坏既有引用。

推荐新代码直接使用:
    from backend.gpu import get_array_module, to_gpu, to_cpu, detect_gpu
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
