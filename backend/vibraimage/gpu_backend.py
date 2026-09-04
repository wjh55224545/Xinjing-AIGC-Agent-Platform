"""
GPU计算后端 — 自动探测 + 适配层
================================

探测链:
  1. torch + MUSA (曦云C500, 沐曦PyTorch预装)
  2. torch + CUDA (NVIDIA, 本地开发机)
  3. numpy (CPU兜底, 无需GPU)

环境变量:
  VIBRAIMAGE_GPU_BACKEND=auto|torch|numpy
  VIBRAIMAGE_GPU_BENCHMARK=true   # 开启后记录每次运算CPU vs GPU耗时

用法:
  from backend.vibraimage.gpu_backend import get_array_module, to_gpu, to_cpu
  xp = get_array_module()  # 返回 torch 或 numpy
  result = xp.abs(xp.diff(frames, axis=0))
"""

from __future__ import annotations
import logging
import time
import os
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# 全局状态
_xp_module = None
_gpu_info: dict | None = None
_benchmark_enabled = os.environ.get("VIBRAIMAGE_GPU_BENCHMARK", "").lower() == "true"
_benchmark_records: list[dict] = []


def detect_gpu() -> dict:
    """检测GPU并返回信息。结果会被缓存。"""
    global _gpu_info
    if _gpu_info is not None:
        return _gpu_info

    backend = os.environ.get("VIBRAIMAGE_GPU_BACKEND", "auto").lower()
    info = {"available": False, "backend": "numpy", "device": "cpu",
            "vendor": "N/A", "model": "N/A", "memory_mb": 0}

    if backend in ("auto", "torch"):
        try:
            import torch
            if torch.cuda.is_available():
                info["available"] = True
                info["backend"] = "torch"
                info["device"] = "cuda:0"
                info["model"] = torch.cuda.get_device_name(0)
                info["memory_mb"] = int(torch.cuda.get_device_properties(0).total_memory / 1024 / 1024)
                # 检测是否为MUSA后端（沐曦）
                device_name = info["model"].lower()
                if "metax" in device_name or "musa" in device_name:
                    info["vendor"] = "MetaX (沐曦)"
                else:
                    info["vendor"] = "NVIDIA"
                logger.info(f"GPU检测: {info['vendor']} {info['model']}, {info['memory_mb']}MB")
                _gpu_info = info
                return info
        except ImportError:
            logger.info("torch未安装")

    logger.info("GPU检测: 未检测到GPU，使用CPU(numpy)")
    _gpu_info = info
    return info


def get_array_module():
    """
    返回当前活动的数组模块 (torch 或 numpy)。

    优先使用GPU (torch CUDA/MUSA)，不可用时回退到 numpy。
    """
    global _xp_module
    if _xp_module is not None:
        return _xp_module

    backend = os.environ.get("VIBRAIMAGE_GPU_BACKEND", "auto").lower()
    if backend == "numpy":
        import numpy
        _xp_module = numpy
        return _xp_module

    # auto 或 torch
    try:
        import torch
        if torch.cuda.is_available():
            _xp_module = torch
            return _xp_module
    except ImportError:
        pass

    import numpy
    _xp_module = numpy
    return _xp_module


def reset_array_module():
    """重置缓存的模块（用于测试）。"""
    global _xp_module, _gpu_info
    _xp_module = None
    _gpu_info = None


def is_gpu_available() -> bool:
    """GPU是否可用。"""
    info = detect_gpu()
    return info["available"]


def to_gpu(array):
    """将numpy数组转移到GPU（如果GPU可用），否则返回原数组。"""
    if not is_gpu_available():
        return array
    import torch
    if isinstance(array, torch.Tensor):
        return array.cuda()
    return torch.from_numpy(array).cuda()


def to_cpu(array):
    """将GPU tensor转回numpy数组。"""
    import numpy
    if hasattr(array, 'cpu'):
        return array.cpu().numpy()
    if isinstance(array, numpy.ndarray):
        return array
    return numpy.asarray(array)


def ensure_float32(array):
    """确保数组为float32类型。"""
    xp = get_array_module()
    if xp.__name__ == 'numpy':
        import numpy as np
        if array.dtype == np.uint8:
            return array.astype(np.float32)
        return array
    else:
        import torch
        if isinstance(array, torch.Tensor):
            if array.dtype == torch.uint8:
                return array.float()
            return array
        return array


def histogram(x, bins=100, range=None, weights=None):
    """
    兼容 torch/numpy 的直方图计算。

    torch 的 histc 不支持 weights，所以需要特殊处理：
    - 无 weights: torch.histc (GPU) 或 np.histogram (CPU)
    - 有 weights: 回退 numpy
    """
    xp = get_array_module()
    import numpy as np

    if not is_gpu_available():
        x_np = x if isinstance(x, np.ndarray) else x.cpu().numpy()
        w_np = weights if weights is None or isinstance(weights, np.ndarray) else weights.cpu().numpy()
        return np.histogram(x_np, bins=bins, range=range, weights=w_np)

    # GPU可用，但有weights时需要回退numpy
    if weights is not None:
        x_np = to_cpu(x)
        w_np = to_cpu(weights)
        return np.histogram(x_np, bins=bins, range=range, weights=w_np)

    # 无weights，使用torch.histc
    import torch
    range_min, range_max = range if range else (float(x.min()), float(x.max()))
    hist = torch.histc(to_gpu(x), bins=bins, min=range_min, max=range_max)
    edges = torch.linspace(range_min, range_max, bins + 1)
    return hist, edges


def rfft(x, axis=0):
    """兼容 torch/numpy 的实FFT。"""
    xp = get_array_module()
    if xp.__name__ == 'numpy':
        import numpy as np
        return np.fft.rfft(x, axis=axis)
    else:
        import torch
        # torch.fft.rfft 默认在最后一维，需要调整
        return torch.fft.rfft(x, dim=axis)


def rfftfreq(n, d=1.0):
    """兼容 torch/numpy 的FFT频率轴。GPU可用时返回GPU tensor。"""
    xp = get_array_module()
    if xp.__name__ == 'numpy':
        import numpy as np
        return np.fft.rfftfreq(n, d=d)
    else:
        import torch
        result = torch.fft.rfftfreq(n, d=d)
        # torch.fft.rfftfreq 默认返回CPU tensor，需手动转移到GPU
        if is_gpu_available():
            result = result.cuda()
        return result


@contextmanager
def benchmark_context(label: str):
    """上下文管理器，记录GPU/CPU运算耗时。"""
    if not _benchmark_enabled:
        yield
        return

    t0 = time.perf_counter()
    yield
    elapsed_ms = (time.perf_counter() - t0) * 1000
    backend = "GPU" if is_gpu_available() else "CPU"
    _benchmark_records.append({
        "label": label, "backend": backend, "elapsed_ms": round(elapsed_ms, 3),
    })
    logger.debug(f"[BENCHMARK] {label} ({backend}): {elapsed_ms:.3f}ms")


def get_benchmark_records() -> list[dict]:
    """获取所有基准测试记录。"""
    return list(_benchmark_records)


def clear_benchmark_records():
    """清空基准测试记录。"""
    _benchmark_records.clear()


def get_gpu_info() -> dict:
    """获取GPU信息（供API使用）。"""
    return detect_gpu()
