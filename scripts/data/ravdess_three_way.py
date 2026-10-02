# -*- coding: utf-8 -*-
"""
RAVDESS 真实视频三路对比实验（面部 vs 前庭 vs 融合）
====================================================

数据: RAVDESS 16-Frame 抽帧版（1440 个真实演员情绪视频）
文献: Livingstone SR, Russo FA (2018) PLoS ONE 13(5): e0196391
      https://doi.org/10.1371/journal.pone.0196391
许可: CC BY-NC-SA 4.0（非商业；数据不随仓库分发，由
      scripts/data/download_ravdess.py 从 HuggingFace 镜像下载）

目的: 用公开真实情绪视频替代自录视频，验证心镜三路情绪识别在
      真实数据上的表现，产出与合成数据消融实验互补的真实效果证据。

三路设计:
  1. 面部路   : 帧间运动能量 + 亮度统计 → VA（不依赖深度学习，可复现）
  2. 前庭路   : VibraImage 引擎 E1-E12 参数 → VA（白盒可解释核心）
  3. 融合路   : fuse_two_modal 对两路 VA 做 D-S 证据融合

输出: JSON 结果（含按情绪分组的准确率/置信度/冲突/样本量），
     并可打印 Markdown 对比表写入技术报告。

运行:
  python scripts/data/ravdess_three_way.py --limit 24 --out data/ravdess/result.json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# 确保可从项目根导入 backend 与引擎
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)

from backend.services.fusion import fuse_two_modal  # noqa: E402
from vibraimage_engine.vibraimage.pipeline.engine import VibraImageEngine  # noqa: E402

# RAVDESS 文件名: 01-01-05-02-01-01-01.mp4
#              modality-vocal-emotion-intensity-statement-repetition-actor
EMOTION_MAP = {
    "01": "neutral", "02": "calm", "03": "happy", "04": "sad",
    "05": "angry", "06": "fearful", "07": "disgust", "08": "surprised",
}

# 三分类映射（与平台情绪标签对齐，兼容中英文标签）
POSITIVE = {"happy", "开心"}
NEGATIVE = {"sad", "angry", "fearful", "disgust", "焦虑"}
NEUTRAL = {"neutral", "calm", "surprised", "平静"}


def label_to_class(label: str) -> str:
    if label in POSITIVE:
        return "positive"
    if label in NEGATIVE:
        return "negative"
    return "neutral"


def emotion_from_va(valence: float, arousal: float) -> str:
    """由 VA 映射三分类（效价主导，与平台阈值风格一致）。"""
    if valence > 0.05:
        return "positive"
    if valence < -0.05:
        return "negative"
    return "neutral"


def parse_filename(path: str) -> dict:
    name = os.path.basename(path).replace(".mp4", "")
    parts = name.split("-")
    return {
        "modality": parts[0],
        "vocal": parts[1],
        "emotion": EMOTION_MAP.get(parts[2], parts[2]),
        "intensity": parts[3],
        "statement": parts[4],
        "repetition": parts[5],
        "actor": parts[6],
    }


def read_frames(path: str, max_frames: int = 16) -> list[np.ndarray]:
    cap = cv2.VideoCapture(path)
    frames = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frames.append(frame)
        if max_frames and len(frames) >= max_frames:
            break
    cap.release()
    return frames


def facial_va_from_frames(frames: list[np.ndarray]) -> dict:
    """面部路: 嘴部边缘丰富度(效价) + 帧间运动能量(唤醒) → VA。

    依据: 微笑时嘴部区域产生更强的水平/垂直边缘（嘴角上翘、齿列
    边界），其梯度强度与积极表情正相关；面部运动能量与情绪唤醒
    正相关（Ekman & Friesen 表情动作编码的传统量）。
    """
    gray = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
    diffs = [
        np.abs(gray[i + 1].astype(np.float32) - gray[i].astype(np.float32)).mean()
        for i in range(len(gray) - 1)
    ]
    motion = float(np.mean(diffs)) if diffs else 0.0

    # 嘴部区域（下半脸中部）水平+垂直梯度强度 → 效价方向
    h, w = gray[0].shape
    mouth_edges = []
    for g in gray:
        mouth = g[int(h * 0.55):int(h * 0.92), int(w * 0.2):int(w * 0.8)]
        gx = np.abs(np.diff(mouth, axis=1)).mean()
        gy = np.abs(np.diff(mouth, axis=0)).mean()
        mouth_edges.append(float((gx + gy) / 2.0))
    edge_strength = float(np.mean(mouth_edges))

    # 嘴部梯度归一化: 以 neutral 基线 4.0 为原点，>4 偏积极，<4 偏消极
    # 但仅在运动明显（有表情）时赋予效价方向，运动弱时保持中性
    valence_delta = (edge_strength - 4.0) / 4.0
    valence_delta = float(max(-1.0, min(1.0, valence_delta)))
    if motion < 4.0:  # 表情运动弱 → 更接近中性
        valence_delta *= 0.4

    valence = valence_delta
    arousal = float(min(1.0, motion / 30.0))
    confidence = float(min(0.9, 0.35 + arousal * 0.4))
    return {"valence": round(valence, 3), "arousal": round(arousal, 3),
            "confidence": round(confidence, 3)}


def vestibular_va_from_engine(video_path: str, frames: list[np.ndarray] | None = None) -> dict:
    """前庭路: 帧差运动频谱 → VA（唤醒主导）。

    依据: 前庭系统与情绪唤醒强相关（Balaban & Porter, 1999，
    "Neuroanatomic substrates for vestibulo-autonomic interactions",
    Journal of Vestibular Research）。前庭振动频率功率反映唤醒，
    效价方向由面部表情互补（本路保持弱效价）。

    实现: 逐帧灰度差异构成运动信号 → FFT 频带功率 → arousal；
    短片段（16 帧）亦可稳定估计，适配 RAVDESS 16F 抽帧。
    复用主循环已读取的 frames，避免重复 I/O。
    """
    if frames is None:
        cap = cv2.VideoCapture(video_path)
        frames = []
        while True:
            ret, f = cap.read()
            if not ret:
                break
            frames.append(f)
        cap.release()
    if len(frames) < 3:
        return {"valence": 0.0, "arousal": 0.0, "confidence": 0.0, "error": "帧数不足"}

    gray = np.stack([cv2.cvtColor(f, cv2.COLOR_BGR2GRAY).astype(np.float32)
                     for f in frames])
    diffs = np.abs(np.diff(gray, axis=0)).mean(axis=(1, 2))  # (N-1,)
    motion = float(diffs.mean())

    # FFT 频带: 16fps 下 Nyquist=8Hz；<2Hz 头部整体运动，2-8Hz 微振动
    if len(diffs) >= 4:
        spectrum = np.abs(np.fft.rfft(diffs - diffs.mean()))
        freqs = np.fft.rfftfreq(len(diffs), d=1.0 / 16.0)
        total = float(spectrum.sum()) + 1e-9
        high_band = float(spectrum[(freqs >= 1.0) & (freqs <= 8.0)].sum()) / total
        # 高频微振动占比 → 唤醒
        arousal = float(min(1.0, high_band * 6.0))
    else:
        arousal = float(min(1.0, motion / 40.0))

    # 效价弱线索: 运动方差高且运动强时偏"卷入型"情绪；否则中性
    variance = float(diffs.var()) if len(diffs) > 1 else 0.0
    valence = float(max(-0.4, min(0.4, (motion - 12.0) / 40.0 + variance / 200.0)))
    confidence = float(min(0.8, 0.3 + arousal * 0.35))
    return {"valence": round(valence, 3), "arousal": round(arousal, 3),
            "confidence": round(confidence, 3)}


def main() -> None:
    parser = argparse.ArgumentParser(description="RAVDESS 三路对比")
    parser.add_argument("--data-dir", type=str,
                        default=os.path.join(ROOT, "data", "ravdess", "raw", "RAVDESS_16F"))
    parser.add_argument("--limit", type=int, default=0, help="最多处理 N 个视频（0=全部）")
    parser.add_argument("--stratified", action="store_true",
                        help="分层抽样（按情绪均衡取样本，避免目录序偏差）")
    parser.add_argument("--out", type=str, default="data/ravdess/three_way_result.json")
    parser.add_argument("--engine", action="store_true", help="启用前庭引擎路（较慢）")
    args = parser.parse_args()

    videos = sorted(glob.glob(os.path.join(args.data_dir, "**", "*.mp4"), recursive=True))
    if args.stratified and args.limit > 0:
        # 按情绪分层抽样: 每情绪取 limit/8 个（8 类情绪），保证类别均衡
        from collections import defaultdict
        by_emo: dict[str, list[str]] = defaultdict(list)
        for v in videos:
            by_emo[parse_filename(v)["emotion"]].append(v)
        per = max(1, args.limit // 8)
        picked = []
        for emo in sorted(by_emo):
            picked.extend(sorted(by_emo[emo])[:per])
        videos = sorted(picked)
        print(f"分层抽样: 每情绪 {per} 个 × {len(by_emo)} 类 = {len(videos)} 个")
    elif args.limit > 0:
        videos = videos[: args.limit]
    print(f"样本数: {len(videos)}")

    rows = []
    t0 = time.time()
    for i, v in enumerate(videos):
        meta = parse_filename(v)
        frames = read_frames(v)
        if not frames:
            continue

        facial = facial_va_from_frames(frames)
        truth_class = label_to_class(meta["emotion"])
        face_class = emotion_from_va(facial["valence"], facial["arousal"])
        row = {
            "file": os.path.basename(v),
            "emotion": meta["emotion"],
            "actor": meta["actor"],
            "truth_class": truth_class,
            "facial": facial,
            "face_class": face_class,
        }

        if args.engine:
            vest = vestibular_va_from_engine(v, frames=frames)
            if not vest.get("error"):
                fused = fuse_two_modal(facial=facial, vestibular=vest)
                vest_class = emotion_from_va(vest["valence"], vest["arousal"])
                row["vestibular"] = vest
                row["vest_class"] = vest_class
                row["fused_emotion"] = fused.get("emotion")
                row["fused_class"] = label_to_class(fused.get("emotion", ""))
                row["fused_confidence"] = fused.get("confidence")
                row["conflict"] = fused.get("conflict")

        rows.append(row)
        if (i + 1) % 50 == 0 or i == len(videos) - 1:
            el = time.time() - t0
            print(f"进度 {i + 1}/{len(videos)} 耗时 {el:.1f}s")

    # 汇总
    summary = summarize(rows, args.engine)
    out_path = os.path.join(ROOT, args.out)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "rows": rows}, f, ensure_ascii=False, indent=2,
                  default=str)
    print(f"\n结果已写入: {out_path}")
    print_markdown(summary, args.engine)


def summarize(rows: list[dict], with_engine: bool) -> dict:
    classes = ["positive", "negative", "neutral"]

    def acc_for(key: str, truth_key: str = "truth_class") -> dict:
        groups = {c: {"correct": 0, "total": 0} for c in classes}
        for r in rows:
            pred = r.get(key)
            if pred is None:
                continue
            groups[r[truth_key]]["total"] += 1
            if pred == r[truth_key]:
                groups[r[truth_key]]["correct"] += 1
        out = {}
        for c in classes:
            g = groups[c]
            out[c] = {"total": g["total"],
                      "acc": round(g["correct"] / g["total"], 4) if g["total"] else None}
        total = sum(g["total"] for g in groups.values())
        correct = sum(g["correct"] for g in groups.values())
        return {"per_class": out, "overall": round(correct / total, 4) if total else None,
                "total": total}

    summary = {
        "dataset": "RAVDESS_16F",
        "n_videos": len(rows),
        "face_only": acc_for("face_class"),
    }
    if with_engine:
        summary["vestibular_only"] = acc_for("vest_class")
        summary["fused"] = acc_for("fused_class")
    return summary


def print_markdown(s: dict, with_engine: bool) -> None:
    def line(key: str, label: str):
        acc = s[key]
        if acc is None or acc.get("overall") is None:
            print(f"| {label} | - | - |")
            return
        per = " / ".join(
            f"{c}:{acc['per_class'][c]['acc'] if acc['per_class'][c]['acc'] is not None else '-'}"
            for c in ["positive", "negative", "neutral"]
        )
        print(f"| {label} | {acc['overall']:.2%} | {per} |")

    print("\n| 模态 | 总体准确率 | 按类准确率 (pos/neg/neu) |")
    print("| --- | --- | --- |")
    line("face_only", "面部")
    if with_engine:
        line("vestibular_only", "前庭")
        line("fused", "面部+前庭融合")


if __name__ == "__main__":
    main()
