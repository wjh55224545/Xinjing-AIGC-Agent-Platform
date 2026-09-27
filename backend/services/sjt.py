"""
情境判断测验（SJT）计分服务
===========================

SJT（Situational Judgment Test）以真实校园压力情境呈现，测量个体
在压力情境下的**应对倾向**（行为倾向型作答指令：选"最可能做"而非
"最应该做"）。本模块提供：

  - 题库加载（data/scales/SJT.json）
  - 作答计分（按维度聚合 0-100 分）
  - 风险等级判定（低/中/高关注）
  - 维度画像与个性化建议

测量学依据（对应 04 技术方案"情境判断测验"创新点）：
  - Weekley & Jones (1999)：提出 SJT 结构，与工作绩效相关 r≈.19
  - McDaniel et al. (2003)：区分"知识型（最有效）"与"行为倾向型
    （最可能）"作答指令，行为倾向型更贴近真实应对行为
  - Webster et al. (2020)：SJT 与绩效标准元分析 pooled r=0.32
  - Harenbrock et al. (2023)：SJT 重测信度元分析 pooled r=0.698
  - Kasten & Freund (2014)：SJT 内部一致性偏低属构念异质所致，
    效标效度仍可接受，故本测验采用"维度分+总分"双通道呈现

⚠️ 本测验用于评估应对倾向与风险信号识别，非临床诊断工具；
作答结果标记 is_synthetic 与否取决于输入来源。
"""

from __future__ import annotations
import json
import os
from typing import Any

_SJT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "scales", "SJT.json")

# 维度分 → 风险等级（分越高应对越积极）
_DIM_LEVEL = [
    ("high", 80, "应对积极"),
    ("medium", 60, "应对一般"),
    ("low", 0, "应对不足"),
]
# 总分级距（分越高越健康）
_TOTAL_LEVEL = [
    ("healthy", 80, "应对资源充足"),
    ("moderate", 60, "应对资源一般"),
    ("concern", 0, "需重点关注"),
]

_DIMENSION_NOTES = {
    "exam_anxiety": "考试焦虑应对：反映面对考试压力时的调节策略是否积极。",
    "academic_stress": "学业压力管理：反映多任务压力下的计划性与主动性。",
    "peer_conflict": "同伴冲突处理：反映冲突情境下的沟通与合作倾向。",
    "social_avoidance": "社交回避倾向：反映社交情境下的回避程度（分越低越回避）。",
    "emotion_regulation": "情绪调节能力：反映负性情绪后的重构与消化能力。",
    "help_seeking": "求助意愿：反映对专业/同伴支持的开放程度。",
}


def _load_bank() -> dict:
    with open(_SJT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def public_questions() -> dict:
    """返回前端可渲染的题目（不含选项分值，避免泄露计分）。"""
    bank = _load_bank()
    return {
        "code": bank["code"],
        "name": bank["name"],
        "description": bank["description"],
        "source": bank["source"],
        "instruction": bank["instruction"],
        "dimensions": bank["dimensions"],
        "questions_count": bank["questions_count"],
        "questions": [
            {
                "id": q["id"],
                "scenario": q["scenario"],
                "dimension": q["dimension"],
                "options": [o["label"] for o in q["options"]],
            }
            for q in bank["questions"]
        ],
    }


def score_sjt(answers: list[dict[str, Any]]) -> dict:
    """
    对 SJT 作答计分。

    answers: [{"id": 1, "choice": 0}, ...]  choice 为选项下标（0 起）。
    返回维度分、总分、等级、画像与建议。
    """
    bank = _load_bank()
    by_id = {q["id"]: q for q in bank["questions"]}
    dims = bank["dimensions"]

    dim_sums: dict[str, int] = {d: 0 for d in dims}
    dim_max: dict[str, int] = {d: 0 for d in dims}
    dim_counts: dict[str, int] = {d: 0 for d in dims}
    total = 0
    total_max = 0
    answered = 0

    for ans in answers:
        q = by_id.get(int(ans.get("id", 0)))
        if q is None:
            continue
        choice = int(ans.get("choice", -1))
        if choice < 0 or choice >= len(q["options"]):
            continue
        opt = q["options"][choice]
        score = int(opt.get("score", 0))
        dim = q["dimension"]
        dim_sums[dim] += score
        dim_max[dim] += 3
        dim_counts[dim] += 1
        total += score
        total_max += 3
        answered += 1

    n_total = bank["questions_count"]
    if answered == 0:
        return {"success": False, "detail": "无有效作答，请至少回答一题"}

    dim_scores = {}
    dim_levels = {}
    for d in dims:
        score_100 = round(dim_sums[d] / dim_max[d] * 100, 1) if dim_max[d] else 0.0
        dim_scores[d] = score_100
        for lvl, thr, label in _DIM_LEVEL:
            if score_100 >= thr:
                dim_levels[d] = {"level": lvl, "label": label, "score": score_100}
                break

    total_100 = round(total / total_max * 100, 1) if total_max else 0.0
    for lvl, thr, label in _TOTAL_LEVEL:
        if total_100 >= thr:
            total_level = {"level": lvl, "label": label, "score": total_100}
            break

    # 低分维度（风险信号）
    risk_dims = [d for d in dims if dim_levels[d]["level"] == "low"]
    watch_dims = [d for d in dims if dim_levels[d]["level"] == "medium"]

    return {
        "success": True,
        "data": {
            "is_synthetic": None,  # 由调用方标注（真实学生 / 虚拟被试）
            "answered_count": answered,
            "total_score": total_100,
            "total_level": total_level,
            "dimension_scores": dim_scores,
            "dimension_levels": dim_levels,
            "dimension_notes": {d: _DIMENSION_NOTES.get(d, "") for d in dims},
            "risk_signals": {
                "low_dims": [dims[d] for d in risk_dims],
                "watch_dims": [dims[d] for d in watch_dims],
            },
            "recommendations": _build_recommendations(risk_dims, watch_dims, dims),
            "method_note": (
                "计分依据：Weekley & Jones (1999) 行为倾向型 SJT 范式；"
                "Webster et al. (2020) 元分析 pooled r=0.32；"
                "Harenbrock et al. (2023) 重测信度 pooled r=0.698。"
                "本测验用于评估应对倾向，辅助风险信号识别，非临床诊断。"
            ),
        },
    }


def _build_recommendations(risk_dims: list[str], watch_dims: list[str], dims: dict) -> list[str]:
    recs = []
    if risk_dims:
        recs.append("以下维度应对不足，建议重点关注：" + "、".join(dims[d] for d in risk_dims) +
                    "；可结合量表结果与班主任/心理老师沟通。")
    if watch_dims:
        recs.append("以下维度应对一般，建议持续观察：" + "、".join(dims[d] for d in watch_dims) + "。")
    if not risk_dims and not watch_dims:
        recs.append("各维度应对倾向均较积极，保持现有调节策略即可。")
    recs.append("建议结合 SAS/SDS 量表与 AI 情绪监测结果进行多源交叉验证。")
    return recs
