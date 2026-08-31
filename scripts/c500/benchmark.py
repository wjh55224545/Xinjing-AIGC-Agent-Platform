"""
曦云C500 CPU vs GPU 全流水线性能对比基准测试
===========================================

测试VibraImage引擎各计算模块在CPU和GPU上的性能差异，
生成结构化基准数据用于性能演示。

测试项: 帧差分 / FFT / 直方图 / 空间分析 / YOLOv8推理 / 全流水线端到端
每个测试项: 先强制numpy(CPU)跑3次取平均 → 再GPU跑3次取平均
输出: JSON基准数据 + 加速比

用法:
  python scripts/c500/benchmark.py --output data/benchmark_c500.json
"""

from __future__ import annotations
import sys
import os
import json
import time
import argparse
from pathlib import Path

# 确保 backend 在 path 中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import numpy as np

RESULT = {"gpu_vendor": "", "gpu_model": "", "memory_mb": 0, "tests": []}


def benchmark(name: str, cpu_fn, gpu_fn, n_runs: int = 3) -> dict:
    """跑一个测试项的 CPU vs GPU 对比。"""
    print(f"  [{name}] ...", end=" ", flush=True)

    # CPU
    cpu_times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        cpu_fn()
        cpu_times.append((time.perf_counter() - t0) * 1000)

    # GPU (warmup一次)
    os.environ["VIBRAIMAGE_GPU_BACKEND"] = "torch"
    from backend.vibraimage.gpu_backend import reset_array_module, is_gpu_available
    reset_array_module()

    if not is_gpu_available():
        print("GPU不可用，跳过")
        return {"name": name, "cpu_ms": round(np.mean(cpu_times), 2), "gpu_ms": None, "speedup": None}

    gpu_fn()  # warmup
    gpu_times = []
    for _ in range(n_runs):
        t0 = time.perf_counter()
        gpu_fn()
        gpu_times.append((time.perf_counter() - t0) * 1000)

    cpu_avg = np.mean(cpu_times)
    gpu_avg = np.mean(gpu_times)
    speedup = round(cpu_avg / gpu_avg, 2) if gpu_avg > 0 else 0

    print(f"CPU={cpu_avg:.2f}ms | GPU={gpu_avg:.2f}ms | {speedup}x")
    reset_array_module()
    return {"name": name, "cpu_ms": round(cpu_avg, 2), "gpu_ms": round(gpu_avg, 2), "speedup": speedup}


def test_frame_differencing():
    """帧差分：100帧224×224灰度图"""
    frames = np.random.randn(100, 224, 224).astype(np.float32)

    def cpu():
        np.abs(np.diff(frames, axis=0))

    def gpu():
        from backend.vibraimage.gpu_backend import to_gpu, to_cpu
        xp = __import__('torch')
        g = to_gpu(frames)
        r = xp.abs(xp.diff(g, dim=0))
        to_cpu(r)

    return benchmark("帧差分 (100×224×224)", cpu, gpu)


def test_fft():
    """FFT：100点时间序列 × 224×224像素"""
    data = np.random.randn(100, 224, 224).astype(np.float32)

    def cpu():
        np.fft.rfft(data, axis=0)

    def gpu():
        from backend.vibraimage.gpu_backend import to_gpu, to_cpu
        xp = __import__('torch')
        g = to_gpu(data)
        r = xp.fft.rfft(g, dim=0)
        to_cpu(r)

    return benchmark("FFT (100×224×224)", cpu, gpu)


def test_histogram():
    """直方图：224×224个频率数据"""
    freq_map = np.random.uniform(0.1, 10.0, (224, 224)).astype(np.float32)

    def cpu():
        freqs = freq_map.ravel()
        valid = np.isfinite(freqs) & (freqs >= 0.1) & (freqs <= 10.0)
        np.histogram(freqs[valid], bins=100, range=(0.1, 10.0))

    def gpu():
        from backend.vibraimage.gpu_backend import to_gpu, histogram
        freqs = to_gpu(freq_map).ravel()
        # histogram helper handles torch/numpy dispatch
        histogram(freqs, bins=100, range=(0.1, 10.0))

    return benchmark("频率直方图 (224×224)", cpu, gpu)


def test_spatial():
    """空间分析：224行×每行112列左右"""
    freq_map = np.random.uniform(0.1, 10.0, (224, 224)).astype(np.float32)
    amp_map = np.random.randn(224, 224).astype(np.float32)

    def cpu():
        H, W = freq_map.shape
        mid = W // 2
        for i in range(H):
            left_valid = freq_map[i, :mid] > 0
            right_valid = freq_map[i, mid:] > 0
            if left_valid.any():
                _ = np.mean(amp_map[i, :mid][left_valid])
            if right_valid.any():
                _ = np.mean(amp_map[i, mid:][right_valid])

    def gpu():
        from backend.vibraimage.gpu_backend import to_gpu, to_cpu
        xp = __import__('torch')
        f_gpu = to_gpu(freq_map)
        a_gpu = to_gpu(amp_map)
        H, W = f_gpu.shape
        mid = W // 2
        for i in range(H):
            lv = f_gpu[i, :mid] > 0
            rv = f_gpu[i, mid:] > 0
            if lv.any():
                _ = xp.mean(a_gpu[i, :mid][lv])
            if rv.any():
                _ = xp.mean(a_gpu[i, mid:][rv])
        to_cpu(f_gpu)

    return benchmark("空间分析 (224行)", cpu, gpu)


def test_yolo_inference():
    """YOLOv8推理：10帧640×480"""
    try:
        from ultralytics import YOLO
    except ImportError:
        print("  [YOLOv8推理] ultralytics未安装，跳过")
        return None

    model_path = "data/yolov8n.pt"
    if not os.path.exists(model_path):
        alt_paths = ["yolov8n.pt", os.path.expanduser("~/.cache/torch/hub/ultralytics/yolov8n.pt")]
        found = False
        for p in alt_paths:
            if os.path.exists(p):
                model_path = p
                found = True
                break
        if not found:
            print("  [YOLOv8推理] yolov8n.pt未找到，跳过")
            return None

    frames = np.random.randint(0, 255, (10, 640, 480, 3), dtype=np.uint8)

    def cpu():
        m = YOLO(model_path)
        for i in range(10):
            m(frames[i], verbose=False, device="cpu")

    def gpu():
        m = YOLO(model_path)
        for i in range(10):
            m(frames[i], verbose=False, device="cuda")

    # warmup
    _ = YOLO(model_path)(frames[0], verbose=False, device="cpu")
    if __import__('torch').cuda.is_available():
        _ = YOLO(model_path)(frames[0], verbose=False, device="cuda")

    return benchmark("YOLOv8推理 (10帧)", cpu, gpu, n_runs=2)


def test_end_to_end():
    """端到端：完整VibraImage流水线（帧差分→FFT→直方图→空间分析→频谱）"""
    frames = np.random.randn(100, 224, 224).astype(np.float32)

    def cpu():
        # 帧差分
        diff = np.abs(np.diff(frames, axis=0))
        # FFT
        fft_r = np.abs(np.fft.rfft(diff, axis=0))
        freqs_f = np.fft.rfftfreq(diff.shape[0], d=1/30.0)
        # 主导频率 & 振幅
        freq_mask = (freqs_f >= 0.1) & (freqs_f <= 10.0)
        valid_fft = fft_r[freq_mask]
        dominant_idx = np.argmax(valid_fft, axis=0)
        freq_map = freqs_f[freq_mask][dominant_idx]
        amp_map = valid_fft[dominant_idx, np.arange(224)[:, None], np.arange(224)]
        # 直方图
        freqs_flat = freq_map.ravel()
        valid = np.isfinite(freqs_flat) & (freqs_flat >= 0.1) & (freqs_flat <= 10.0)
        np.histogram(freqs_flat[valid], bins=100, range=(0.1, 10.0))
        # 空间分析
        H, W = freq_map.shape
        mid = W // 2
        for i in range(H):
            lv = freq_map[i, :mid] > 0
            if lv.any():
                _ = np.mean(amp_map[i, :mid][lv])

    def gpu():
        from backend.vibraimage.gpu_backend import to_gpu, to_cpu, histogram
        xp = __import__('torch')
        device = 'cuda'
        g = to_gpu(frames)
        # 帧差分
        diff = xp.abs(xp.diff(g, dim=0))
        # FFT
        fft_r = xp.abs(xp.fft.rfft(diff, dim=0))
        freqs_f = xp.fft.rfftfreq(diff.shape[0], d=1/30.0, device=device)
        # 主导频率 & 振幅（全部在同一GPU设备上索引）
        freq_mask = (freqs_f >= 0.1) & (freqs_f <= 10.0)
        valid_fft = fft_r[freq_mask]
        dominant_idx = xp.argmax(valid_fft, dim=0)
        idx_h = xp.arange(224, device=device)[:, None]
        idx_w = xp.arange(224, device=device)
        freq_map = freqs_f[freq_mask][dominant_idx]
        amp_map = valid_fft[dominant_idx, idx_h, idx_w]
        # 直方图
        histogram(freq_map.ravel(), bins=100, range=(0.1, 10.0))
        # 空间分析（转CPU，逐行Python循环不适合GPU）
        freq_map_cpu = to_cpu(freq_map)
        amp_map_cpu = to_cpu(amp_map)
        H, W = freq_map_cpu.shape
        mid = W // 2
        for i in range(H):
            lv = freq_map_cpu[i, :mid] > 0
            if lv.any():
                _ = np.mean(amp_map_cpu[i, :mid][lv])
        to_cpu(diff)

    return benchmark("全流水线端到端", cpu, gpu)


def main():
    parser = argparse.ArgumentParser(description="曦云C500 CPU vs GPU 性能对比")
    parser.add_argument("--output", default="data/benchmark_c500.json", help="输出JSON路径")
    parser.add_argument("--n_runs", type=int, default=3, help="每个测试重复次数")
    args = parser.parse_args()

    print("=" * 60)
    print("  曦云C500 CPU vs GPU 性能基准测试")
    print("=" * 60)

    # GPU 信息
    from backend.vibraimage.gpu_backend import detect_gpu, reset_array_module
    reset_array_module()
    gpu_info = detect_gpu()
    RESULT["gpu_vendor"] = gpu_info["vendor"]
    RESULT["gpu_model"] = gpu_info["model"]
    RESULT["memory_mb"] = gpu_info["memory_mb"]
    print(f"\nGPU: {gpu_info['vendor']} {gpu_info['model']} ({gpu_info['memory_mb']}MB)")
    print(f"后端: {gpu_info['backend']} | 设备: {gpu_info['device']}\n")

    # 测试
    tests = [
        test_frame_differencing,
        test_fft,
        test_histogram,
        test_spatial,
        test_yolo_inference,
        test_end_to_end,
    ]

    for test_fn in tests:
        try:
            result = test_fn()
            if result:
                RESULT["tests"].append(result)
        except Exception as e:
            print(f"  错误: {e}")

    # 汇总
    gpu_tests = [t for t in RESULT["tests"] if t["speedup"] is not None]
    print(f"\n{'=' * 60}")
    if gpu_tests:
        avg_speedup = round(np.mean([t["speedup"] for t in gpu_tests]), 2)
        min_speedup = round(min(t["speedup"] for t in gpu_tests), 2)
        max_speedup = round(max(t["speedup"] for t in gpu_tests), 2)
        print(f"加速比: 平均={avg_speedup}x | 范围=[{min_speedup}x, {max_speedup}x]")
        RESULT["avg_speedup"] = avg_speedup
        RESULT["min_speedup"] = min_speedup
        RESULT["max_speedup"] = max_speedup
    else:
        print("GPU不可用，无法计算加速比")
        RESULT["avg_speedup"] = None

    # 保存
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(RESULT, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {args.output}")
    return RESULT


if __name__ == "__main__":
    main()
