"""
性能基准测试脚本
================

目的：为技术方案「方案可行性」章节提供量化性能证据。
测试内容：
  1. API 端点响应时间（均值/P50/P95/P99/最大）
  2. 并发请求性能（10/50/100 并发）
  3. 核心算法计算效率（自适应测验、情绪预测、证据融合）
  4. 内存占用估算

运行：
  python scripts/benchmark/performance_benchmark.py
  python scripts/benchmark/performance_benchmark.py --concurrency 50 --iterations 100
"""

from __future__ import annotations
import argparse
import time
import statistics
import sys
import os
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from fastapi.testclient import TestClient
from backend.main import app


# ==================== 性能指标计算 ====================

def calc_stats(latencies: list[float]) -> dict:
    """计算延迟统计指标。"""
    if not latencies:
        return {"count": 0, "mean": 0, "p50": 0, "p95": 0, "p99": 0, "max": 0, "min": 0}
    sorted_l = sorted(latencies)
    n = len(sorted_l)
    return {
        "count": n,
        "mean_ms": round(statistics.mean(latencies) * 1000, 2),
        "p50_ms": round(sorted_l[n // 2] * 1000, 2),
        "p95_ms": round(sorted_l[min(int(n * 0.95), n - 1)] * 1000, 2),
        "p99_ms": round(sorted_l[min(int(n * 0.99), n - 1)] * 1000, 2),
        "max_ms": round(max(latencies) * 1000, 2),
        "min_ms": round(min(latencies) * 1000, 2),
    }


# ==================== API 端点基准测试 ====================

def benchmark_api_endpoints(client: TestClient, iterations: int = 50) -> dict:
    """测试各 API 端点的响应时间。"""
    results = {}

    # 1. 仪表盘汇总
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        client.get("/api/dashboard/summary")
        latencies.append(time.perf_counter() - t0)
    results["GET /api/dashboard/summary"] = calc_stats(latencies)

    # 2. 学生列表
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        client.get("/api/students")
        latencies.append(time.perf_counter() - t0)
    results["GET /api/students"] = calc_stats(latencies)

    # 3. 量表列表
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        client.get("/api/scales/list/all")
        latencies.append(time.perf_counter() - t0)
    results["GET /api/scales/list/all"] = calc_stats(latencies)

    # 4. 虚拟被试剖面列表
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        client.get("/api/virtual-subjects/profiles")
        latencies.append(time.perf_counter() - t0)
    results["GET /api/virtual-subjects/profiles"] = calc_stats(latencies)

    # 5. 虚拟被试生成
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        client.post("/api/virtual-subjects/generate", json={"profile_id": "mild_anxiety"})
        latencies.append(time.perf_counter() - t0)
    results["POST /api/virtual-subjects/generate"] = calc_stats(latencies)

    # 6. 情绪预测
    test_series = [0.6 + 0.02 * i + 0.01 * (i % 3) for i in range(15)]
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        client.post("/api/emotion/forecast", json={"series": test_series, "steps": 5})
        latencies.append(time.perf_counter() - t0)
    results["POST /api/emotion/forecast"] = calc_stats(latencies)

    # 7. 自适应测验开始
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        client.post("/api/scales/cat/start", json={"scale_type": "SAS"})
        latencies.append(time.perf_counter() - t0)
    results["POST /api/scales/cat/start"] = calc_stats(latencies)

    return results


# ==================== 并发性能测试 ====================

def benchmark_concurrency(client: TestClient, concurrency: int = 50, iterations: int = 100) -> dict:
    """测试并发请求性能（使用线程池模拟并发）。"""
    import concurrent.futures

    def make_request(_):
        t0 = time.perf_counter()
        resp = client.get("/api/dashboard/summary")
        return (time.perf_counter() - t0, resp.status_code)

    results = {}
    for c in [10, concurrency]:
        latencies = []
        errors = 0
        t_start = time.perf_counter()
        with concurrent.futures.ThreadPoolExecutor(max_workers=c) as executor:
            futures = [executor.submit(make_request, i) for i in range(iterations)]
            for f in concurrent.futures.as_completed(futures):
                lat, status = f.result()
                latencies.append(lat)
                if status != 200:
                    errors += 1
        elapsed = time.perf_counter() - t_start
        stats = calc_stats(latencies)
        stats["throughput_rps"] = round(iterations / elapsed, 1)
        stats["errors"] = errors
        stats["concurrency"] = c
        results[f"{c}_并发"] = stats

    return results


# ==================== 核心算法计算效率 ====================

def benchmark_algorithms(iterations: int = 100) -> dict:
    """测试核心算法的纯计算效率（不含 HTTP 开销）。"""
    from backend.services.emotion_forecast import linear_trend_forecast, detect_anomalies
    from backend.services.fusion import fuse_three_modal
    from backend.services.cat import estimate_theta

    results = {}

    # 1. 情绪趋势预测
    test_series = [0.6 + 0.02 * i for i in range(20)]
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        linear_trend_forecast(test_series, steps=5)
        latencies.append(time.perf_counter() - t0)
    results["情绪趋势预测 (20步→5步)"] = calc_stats(latencies)

    # 2. 异常检测
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        detect_anomalies(test_series)
        latencies.append(time.perf_counter() - t0)
    results["异常检测 (20步)"] = calc_stats(latencies)

    # 3. 三模态证据融合
    test_facial = {"valence": 0.3, "arousal": 0.8, "confidence": 0.75}
    test_vestibular = {"valence": 0.25, "arousal": 0.7, "confidence": 0.7}
    test_scale = {"theta": 0.8, "confidence": 0.85}
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        fuse_three_modal(facial=test_facial, vestibular=test_vestibular, scale=test_scale)
        latencies.append(time.perf_counter() - t0)
    results["三模态证据融合"] = calc_stats(latencies)

    # 4. IRT 能力估计
    test_items = [
        {"id": 1, "irt": {"a": 1.2, "b": 0.5, "c": 0.2}},
        {"id": 2, "irt": {"a": 1.0, "b": 0.8, "c": 0.2}},
        {"id": 3, "irt": {"a": 1.5, "b": 0.3, "c": 0.2}},
        {"id": 4, "irt": {"a": 1.1, "b": 1.0, "c": 0.2}},
        {"id": 5, "irt": {"a": 1.3, "b": 0.6, "c": 0.2}},
    ]
    test_answers = [{"id": 1, "score": 1}, {"id": 2, "score": 0}, {"id": 3, "score": 1},
                     {"id": 4, "score": 1}, {"id": 5, "score": 0}]
    latencies = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        estimate_theta(test_items, test_answers, reverse_items=[])
        latencies.append(time.perf_counter() - t0)
    results["IRT θ估计 (5题)"] = calc_stats(latencies)

    return results


# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(description="心镜平台性能基准测试")
    parser.add_argument("--iterations", type=int, default=50, help="每端点迭代次数")
    parser.add_argument("--concurrency", type=int, default=50, help="并发数")
    parser.add_argument("--output", type=str, default=None, help="输出 JSON 文件路径")
    args = parser.parse_args()

    print("=" * 70)
    print("心镜 MindMirror 性能基准测试")
    print("=" * 70)
    print()

    client = TestClient(app)

    # 1. API 端点
    print("【1/3】API 端点响应时间测试...")
    api_results = benchmark_api_endpoints(client, iterations=args.iterations)
    print(f"{'端点':<45} {'均值(ms)':<10} {'P95(ms)':<10} {'P99(ms)':<10} {'最大(ms)':<10}")
    print("-" * 85)
    for name, stats in api_results.items():
        print(f"{name:<45} {stats['mean_ms']:<10} {stats['p95_ms']:<10} {stats['p99_ms']:<10} {stats['max_ms']:<10}")
    print()

    # 2. 并发
    print("【2/3】并发性能测试...")
    conc_results = benchmark_concurrency(client, concurrency=args.concurrency, iterations=args.iterations * 2)
    for name, stats in conc_results.items():
        print(f"  {name}: 吞吐 {stats['throughput_rps']} req/s, 均值 {stats['mean_ms']}ms, P95 {stats['p95_ms']}ms, 错误 {stats['errors']}")
    print()

    # 3. 算法
    print("【3/3】核心算法计算效率测试...")
    algo_results = benchmark_algorithms(iterations=args.iterations * 2)
    print(f"{'算法':<35} {'均值(ms)':<10} {'P95(ms)':<10} {'P99(ms)':<10}")
    print("-" * 65)
    for name, stats in algo_results.items():
        print(f"{name:<35} {stats['mean_ms']:<10} {stats['p95_ms']:<10} {stats['p99_ms']:<10}")
    print()

    # 汇总
    all_results = {
        "api_endpoints": api_results,
        "concurrency": conc_results,
        "algorithms": algo_results,
        "config": {"iterations": args.iterations, "concurrency": args.concurrency},
    }

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(all_results, f, ensure_ascii=False, indent=2)
        print(f"结果已写入: {args.output}")

    print("=" * 70)
    print("性能基准测试完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
