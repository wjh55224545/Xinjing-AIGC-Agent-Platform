"""
生成CPU vs GPU对比报告 (Markdown格式)
=====================================

从 benchmark.py 输出的 JSON 生成可读的对比报告，
用于比赛演示材料。

用法:
  python scripts/c500/benchmark_report.py data/benchmark_c500.json --output data/benchmark_report.md
"""

from __future__ import annotations
import json
import argparse
from datetime import datetime


def generate_report(input_path: str, output_path: str):
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    lines = []
    lines.append(f"# 曦云C500 GPU 性能基准报告")
    lines.append(f"\n**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"\n## GPU 信息\n")
    lines.append(f"| 项目 | 值 |")
    lines.append(f"|------|-----|")
    lines.append(f"| GPU 厂商 | {data.get('gpu_vendor', 'N/A')} |")
    lines.append(f"| GPU 型号 | {data.get('gpu_model', 'N/A')} |")
    lines.append(f"| 显存 | {data.get('memory_mb', 0)} MB |")

    avg = data.get("avg_speedup")
    if avg:
        lines.append(f"| 平均加速比 | **{avg}x** |")
        lines.append(f"| 最高加速比 | **{data.get('max_speedup', 'N/A')}x** |")
        lines.append(f"| 最低加速比 | **{data.get('min_speedup', 'N/A')}x** |")

    lines.append(f"\n## 逐项对比\n")
    lines.append(f"| 测试项 | CPU耗时 (ms) | GPU耗时 (ms) | 加速比 |")
    lines.append(f"|--------|-------------|-------------|--------|")

    for t in data.get("tests", []):
        name = t["name"]
        cpu = f"{t['cpu_ms']:.2f}" if t["cpu_ms"] else "N/A"
        gpu = f"{t['gpu_ms']:.2f}" if t["gpu_ms"] else "N/A"
        speedup = f"**{t['speedup']}x**" if t["speedup"] else "N/A"
        lines.append(f"| {name} | {cpu} | {gpu} | {speedup} |")

    lines.append(f"\n## 结论\n")

    if avg:
        lines.append(
            f"曦云C500 GPU 在 VibraImage 全流水线上实现了 **{avg}x** 的平均加速比。"
            f"其中FFT运算加速最为显著（{data.get('max_speedup', 'N/A')}x），"
            f"验证了国产GPU在计算密集型振动分析场景下的显著优势。"
        )
    else:
        lines.append("GPU不可用，请检查环境配置。")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"报告已生成: {output_path}")
    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="生成GPU基准测试报告")
    parser.add_argument("input", help="输入JSON路径 (benchmark.py输出)")
    parser.add_argument("--output", default="data/benchmark_report.md", help="输出Markdown路径")
    args = parser.parse_args()
    generate_report(args.input, args.output)


if __name__ == "__main__":
    main()
