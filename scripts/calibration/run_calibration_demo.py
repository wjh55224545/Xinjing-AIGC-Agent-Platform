#!/usr/bin/env python3
"""
E1-E12 → 效价/唤醒度 权重校正演示脚本
======================================

用途：演示「用标注数据校正情绪映射权重」的方法流程（对应 04 技术方案 7.2 展望）。
方法：对 N 条标注样本，计算每个 E 参数与标注效价/唤醒度的 Pearson 相关系数，
      以 blend_ratio=0.5 保守混合新旧权重，输出校正后权重（weights_calibrated.yaml）。

⚠️ 数据诚实声明：
  本脚本内置的标注样本为「演示用说明性样本」（基于项目三段真人视频验证
  的已知方向构造），用于验证校正流水线可运行、可复现。
  **正式材料中的"实测校正权重"必须替换为试点/真人标注的真实样本。**

用法：
  python scripts/calibration/run_calibration_demo.py

输出：
  backend/vibraimage/mapping/weights_calibrated.yaml
  并在终端打印新旧权重对比表。
"""

from __future__ import annotations
import sys
import json
import random
from pathlib import Path

# 允许从项目根目录 import backend
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from backend.vibraimage.mapping.calibrate import (
    CalibrationSample,
    pearson_correlation_matrix,
    calibrate_weights,
)
from backend.vibraimage.utils.constants import NORMAL_NORMS


def build_demo_samples(seed: int = 2026, n: int = 12) -> list[CalibrationSample]:
    """
    构造演示用标注样本。

    构造逻辑（与项目已发表的真人视频验证方向一致）：
      - 正性情绪样本（happy/neutral）：happiness/charm/energy 偏高，
        标注效价偏高、唤醒度中等；
      - 负性情绪样本（sad/stress）：depression/stress/tension 偏高，
        标注效价偏低、唤醒度随紧张度变化。
    每个样本在常模基础上叠加确定性偏移 + 小随机扰动，确保样本间差异。
    """
    rng = random.Random(seed)
    samples: list[CalibrationSample] = []

    def sample_from(base: dict, shift: dict, valence: float, arousal: float) -> CalibrationSample:
        e = {}
        for k, v in base.items():
            delta = shift.get(k, 0.0)
            e[k] = round(max(1.0, v + delta + rng.uniform(-2.0, 2.0)), 2)
        return CalibrationSample(e_params=e, K=0.0, valence_label=valence, arousal_label=arousal)

    # 12 条演示样本：8 正性 + 4 负性
    pos_shift = {"happiness": 12.0, "charm": 10.0, "energy": 8.0, "balance": 6.0,
                 "self_regulation": 5.0, "depression": -6.0, "stress": -4.0, "tension": -3.0}
    neg_shift = {"depression": 14.0, "stress": 12.0, "tension": 10.0, "aggression": 6.0,
                 "happiness": -12.0, "charm": -8.0, "energy": -6.0}

    for i in range(8):
        arousal = 0.42 if i % 2 == 0 else 0.55
        samples.append(sample_from(NORMAL_NORMS, pos_shift, 0.78, arousal))
    for i in range(4):
        arousal = 0.70 if i % 2 == 0 else 0.45
        samples.append(sample_from(NORMAL_NORMS, neg_shift, 0.25, arousal))

    return samples


def main() -> int:
    print("=" * 70)
    print("E1-E12 → 效价/唤醒度 权重校正演示（Pearson r 法）")
    print("=" * 70)

    samples = build_demo_samples()
    print(f"\n[1] 演示标注样本：{len(samples)} 条（说明性样本，正式使用须替换为真实标注）")

    # 计算相关矩阵
    corr = pearson_correlation_matrix(samples)
    print("\n[2] 各 E 参数与效价/唤醒度的 Pearson 相关系数：")
    print(f"{'参数':<16}{'→ 效价 r':>12}{'→ 唤醒度 r':>14}")
    for k in ["happiness", "charm", "energy", "balance", "stress", "tension", "depression", "aggression"]:
        if k in corr:
            print(f"{k:<16}{corr[k]['valence']:>12.3f}{corr[k]['arousal']:>14.3f}")

    # 校正权重（保守混合 0.5）
    weights_path = ROOT / "backend" / "vibraimage" / "mapping" / "weights.yaml"
    out_path = ROOT / "backend" / "vibraimage" / "mapping" / "weights_calibrated.yaml"
    new_weights = calibrate_weights(samples, weights_path, out_path, blend_ratio=0.5)
    print(f"\n[3] 校正完成，已写出：{out_path}")

    # 对比新旧权重
    import yaml
    old = yaml.safe_load(open(weights_path, encoding="utf-8"))["weights"]
    print("\n[4] 新旧权重对比（效价）：")
    print(f"{'参数':<16}{'旧':>8}{'新':>8}")
    for k, v in new_weights["valence"].items():
        print(f"{k:<16}{old['valence'].get(k, 0):>8.3f}{v:>8.3f}")

    print("\n[5] 使用提示：")
    print("  - 将 weights_calibrated.yaml 内容合并进 weights.yaml 即完成校正；")
    print("  - 校正方向（happiness 正、depression 负）与项目真人视频验证结论一致；")
    print("  - 正式参赛材料中，请用试点真实标注样本替换 build_demo_samples() 的数据。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
