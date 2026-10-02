# -*- coding: utf-8 -*-
"""
通用 GPU 适配组件测试（backend.gpu）
====================================

覆盖: GPU 探测 / 数组模块选择 / 数据传输 / 兼容运算 / 基准上下文。

说明: 测试在无 GPU 环境下亦应通过（自动降级 numpy 路径）。
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestDetectGpu:
    """GPU 探测"""

    def test_detect_returns_expected_structure(self):
        """detect_gpu 返回完整结构。"""
        from backend.gpu import detect_gpu

        info = detect_gpu()
        for key in ("available", "backend", "device", "vendor", "model", "memory_mb"):
            assert key in info, f"缺少字段 {key}"

    def test_detect_force_numpy_backend(self, monkeypatch):
        """强制 numpy 后端时返回 CPU 信息。"""
        monkeypatch.setenv("VIBRAIMAGE_GPU_BACKEND", "numpy")
        from backend.gpu import reset_array_module, detect_gpu

        reset_array_module()
        info = detect_gpu()
        assert info["backend"] == "numpy"
        assert info["device"] == "cpu"

    def test_detect_is_cached(self, monkeypatch):
        """探测结果被缓存，重复调用不重新检测。"""
        from backend.gpu import reset_array_module, detect_gpu

        reset_array_module()
        info1 = detect_gpu()
        info2 = detect_gpu()
        assert info1 is info2


class TestArrayModule:
    """数组模块选择"""

    def test_force_numpy(self, monkeypatch):
        """VIBRAIMAGE_GPU_BACKEND=numpy 时 get_array_module 返回 numpy。"""
        monkeypatch.setenv("VIBRAIMAGE_GPU_BACKEND", "numpy")
        from backend.gpu import reset_array_module, get_array_module

        reset_array_module()
        mod = get_array_module()
        assert mod.__name__ == "numpy"

    def test_reset_clears_cache(self, monkeypatch):
        """reset_array_module 清除缓存。"""
        monkeypatch.setenv("VIBRAIMAGE_GPU_BACKEND", "numpy")
        from backend.gpu import reset_array_module, get_array_module

        reset_array_module()
        get_array_module()
        reset_array_module()
        # 不抛异常即通过
        assert get_array_module().__name__ == "numpy"


class TestDataTransfer:
    """数据传输（CPU 路径）"""

    def test_to_cpu_numpy_identity(self):
        """numpy 数组 to_cpu 原样返回。"""
        from backend.gpu import to_cpu

        arr = np.arange(10, dtype=np.float32)
        out = to_cpu(arr)
        assert isinstance(out, np.ndarray)
        assert out is arr

    def test_ensure_float32_uint8(self):
        """uint8 数组 ensure_float32 转为 float32。"""
        from backend.gpu import ensure_float32

        arr = np.zeros((4, 4), dtype=np.uint8)
        out = ensure_float32(arr)
        assert out.dtype == np.float32

    def test_ensure_float32_keeps_float(self):
        """float32 数组 ensure_float32 保持不变。"""
        from backend.gpu import ensure_float32

        arr = np.zeros((4, 4), dtype=np.float32)
        out = ensure_float32(arr)
        assert out.dtype == np.float32


class TestCompatibleOps:
    """兼容运算（CPU 路径与 numpy 对齐）"""

    def test_histogram_matches_numpy(self):
        """histogram 结果与 np.histogram 一致（无权重）。"""
        from backend.gpu import histogram

        rng = np.random.default_rng(42)
        x = rng.normal(size=1000)
        hist_out, edges_out = histogram(x, bins=20)
        hist_np, edges_np = np.histogram(x, bins=20)
        np.testing.assert_allclose(hist_out, hist_np)
        np.testing.assert_allclose(edges_out, edges_np)

    def test_histogram_with_weights(self):
        """带权重的 histogram 与 numpy 一致。"""
        from backend.gpu import histogram

        rng = np.random.default_rng(7)
        x = rng.normal(size=500)
        w = rng.uniform(0, 1, size=500)
        hist_out, _ = histogram(x, bins=10, weights=w)
        hist_np, _ = np.histogram(x, bins=10, weights=w)
        np.testing.assert_allclose(hist_out, hist_np)

    def test_rfft_matches_numpy(self):
        """rfft 结果与 np.fft.rfft 一致。"""
        from backend.gpu import rfft

        rng = np.random.default_rng(11)
        x = rng.normal(size=(64, 32))
        out = rfft(x, axis=0)
        ref = np.fft.rfft(x, axis=0)
        np.testing.assert_allclose(np.abs(out), np.abs(ref), rtol=1e-5)

    def test_rfftfreq_matches_numpy(self):
        """rfftfreq 结果与 np.fft.rfftfreq 一致。"""
        from backend.gpu import rfftfreq

        out = rfftfreq(64, d=1.0 / 30.0)
        ref = np.fft.rfftfreq(64, d=1.0 / 30.0)
        np.testing.assert_allclose(out, ref)


class TestBenchmark:
    """基准上下文"""

    def test_benchmark_disabled_by_default(self):
        """未开启基准时 benchmark_context 不记录。"""
        from backend.gpu import clear_benchmark_records, get_benchmark_records, benchmark_context

        clear_benchmark_records()
        with benchmark_context("op"):
            pass
        assert get_benchmark_records() == []

    def test_benchmark_enabled_records(self, monkeypatch):
        """开启基准后 benchmark_context 记录耗时条目。"""
        monkeypatch.setenv("VIBRAIMAGE_GPU_BENCHMARK", "true")
        import importlib
        import backend.gpu.backend as gb
        importlib.reload(gb)

        gb.clear_benchmark_records()
        with gb.benchmark_context("test_op"):
            pass
        records = gb.get_benchmark_records()
        assert len(records) == 1
        assert records[0]["label"] == "test_op"
        assert records[0]["backend"] in ("GPU", "CPU")
        assert records[0]["elapsed_ms"] >= 0


class TestApiStatus:
    """API 状态快照"""

    def test_get_gpu_status(self):
        """get_gpu_status 返回健康检查字段。"""
        from backend.gpu import get_gpu_status

        status = get_gpu_status()
        for key in ("available", "backend", "device", "vendor", "model", "memory_mb"):
            assert key in status

    def test_is_gpu_available_returns_bool(self):
        """is_gpu_available 返回布尔值。"""
        from backend.gpu import is_gpu_available

        assert isinstance(is_gpu_available(), bool)
