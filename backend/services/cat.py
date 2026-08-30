"""
计算机自适应测验（CAT）引擎 — 简化教学版
=========================================

基于项目反应理论（IRT）3PL 模型的演示级实现：

    P(θ) = c + (1 - c) / (1 + exp(-1.702 * a * (θ - b)))

能力估计（EAP）：
    在 θ ∈ [-3, 3] 网格上，以标准正态分布为先验，
    依据已答条目的作答似然计算后验分布，取后验均值作为 θ 估计。

选题策略（最大信息量法）：
    I_i(θ) = [P'_i(θ)]² / [P_i(θ) * (1 - P_i(θ))]
    对每个未答条目计算当前 θ 下的信息量，选择信息量最大的条目。

作答二值化：
    选项分高于量表计分中点视为"认可/阳性"(1)，否则为 0；
    反向条目先反转。此简化用于教学演示，正式测验仍以
    scales.py 的全量表标准计分为准。

说明：本实现用于展示 CAT 自适应选题原理与可行性，
IRT 参数来自题库 JSON 中的初始锚定值，可依据标注数据校正。
"""

from __future__ import annotations
import math

# 3PL 模型常数（IRT 常用缩放因子 D=1.702）
D = 1.702

# 能力网格
THETA_GRID = [round(-3 + i * 0.1, 2) for i in range(61)]  # -3.0 ~ 3.0
PRIOR_WEIGHT = [math.exp(-0.5 * t * t) for t in THETA_GRID]  # 标准正态先验（未归一化）


def _default_max(items: list[dict]) -> int:
    """默认终止题量：总题量的 35%，不少于 5 题、不多于 40 题。"""
    n = len(items)
    return max(5, min(40, math.ceil(n * 0.35)))


# ==================== GRM 分级响应模型（升级新增） ====================

def grm_thresholds(item: dict, n_levels: int = 4) -> list[float]:
    """
    由条目核心难度 b 派生 GRM 阈值（锚定初始值，正式使用需标定）。

    对 m 级量表有 m-1 个阈值 b_1 < ... < b_{m-1}。
    m=4 → [b-0.8, b, b+0.8]；m=5 → [b-1.2, b-0.4, b+0.4, b+1.2]
    """
    irt = item.get("irt") or {}
    b = float(irt.get("b", 0.0))
    m = max(int(n_levels), 3)
    if m == 3:
        spacing = [-0.5, 0.5]
    elif m == 4:
        spacing = [-0.8, 0.0, 0.8]
    else:  # m>=5
        spacing = [-1.2, -0.4, 0.4, 1.2]
    return [round(b + s, 3) for s in spacing[: m - 1]]


def grm_step_probability(theta: float, a: float, b_k: float) -> float:
    """GRM 边界概率 P(X>=k|θ) = 1/(1+exp(-D·a·(θ-b_k)))。"""
    e = math.exp(-D * a * (theta - b_k))
    return 1.0 / (1.0 + e)


def grm_category_probabilities(theta: float, a: float, thresholds: list[float]) -> list[float]:
    """GRM 各选项类别概率 P(X=1), ..., P(X=m)。"""
    m = len(thresholds) + 1
    ps = []
    prev = 1.0  # P(X>=1)=1
    for b_k in thresholds:
        cur = grm_step_probability(theta, a, b_k)
        ps.append(prev - cur)  # P(X=k) = P(X>=k) - P(X>=k+1)
        prev = cur
    ps.append(prev)  # P(X=m) = P(X>=m)
    return ps


def grm_item_information(theta: float, a: float, thresholds: list[float]) -> float:
    """
    GRM 期望 Fisher 信息：I(θ) = Σ_k [∂P(k)/∂θ]² / P(k)。
    其中 ∂P(k)/∂θ = ∂P(≥k)/∂θ - ∂P(≥k+1)/∂θ，
    ∂P(≥k)/∂θ = D·a·P(≥k)·(1-P(≥k))。
    """
    m = len(thresholds) + 1
    # 计算各边界的导数
    step_p = [1.0] + [grm_step_probability(theta, a, b) for b in thresholds] + [0.0]
    step_deriv = []
    for i in range(1, len(step_p) - 1):
        p = step_p[i]
        step_deriv.append(D * a * p * (1 - p))
    step_deriv = [0.0] + step_deriv + [0.0]  # 索引对齐：P(>=1)=1 导数0，P(>=m+1)=0 导数0

    info = 0.0
    for k in range(1, m + 1):
        p_k = step_p[k - 1] - step_p[k]  # P(X=k)
        d_k = step_deriv[k - 1] - step_deriv[k]
        if p_k > 1e-9:
            info += (d_k * d_k) / p_k
    return info


def estimate_theta_grm(items: list[dict], answers: list[dict],
                       reverse_items: list[int], n_levels: int = 4) -> dict:
    """
    GRM 多项似然 EAP 能力估计。

    answers: [{"id":.., "score":..}]（score 为 1-based 选项分）
    """
    answered_map = {a.get("id"): a.get("score", 1) for a in answers}
    post = []
    for i, t in enumerate(THETA_GRID):
        log_like = 0.0
        for item in items:
            qid = item.get("id")
            if qid not in answered_map:
                continue
            score = float(answered_map[qid])
            if qid in reverse_items:
                # 反向题：症状认可在低分侧 → 用 (m+1 - score) 映射
                score = (n_levels + 1) - score
            a = _item_params(item)[0]
            thresholds = grm_thresholds(item, n_levels)
            ps = grm_category_probabilities(t, a, thresholds)
            k = min(max(int(round(score)), 1), n_levels)
            p_k = min(max(ps[k - 1], 1e-9), 1 - 1e-9)
            log_like += math.log(p_k)
        post.append(PRIOR_WEIGHT[i] * math.exp(log_like) if log_like else PRIOR_WEIGHT[i])

    total = sum(post)
    if total <= 0:
        return {"theta": 0.0, "se": 1.0}
    denom = 1.0 / total
    mean = sum(t * w for t, w in zip(THETA_GRID, post)) * denom
    var = sum((t - mean) ** 2 * w for t, w in zip(THETA_GRID, post)) * denom
    return {"theta": round(mean, 3), "se": round(math.sqrt(max(var, 1e-6)), 3)}


# ==================== 选题调度（支持 3PL / GRM） ====================

def next_item(
    all_items: list[dict],
    answered: list[dict],
    reverse_items: list[int],
    theta: float,
    max_items: int | None = None,
    model: str = "grm",
    n_levels: int = 4,
) -> dict:
    """
    自适应选题（支持 3PL 二分模型 / GRM 分级响应模型）。

    model:
      - "3pl"  → 原有二分模型（选项分中点二值化）
      - "grm"  → 分级响应模型，直接建模多级作答（默认，升级项）
    n_levels: 量表的选项等级数（如 4 点量表传 4，5 点量表传 5）

    返回:
    {
      "done": bool, "next": item|None,
      "theta": float, "se": float,
      "answered_count": int, "max_items": int,
      "model": str,
      "score_estimate": dict
    }
    """
    answered_ids = {a.get("id") for a in answered}

    if model == "grm":
        est = estimate_theta_grm(all_items, answered, reverse_items, n_levels) if answered else {"theta": 0.0, "se": 1.0}
    else:
        est = estimate_theta(all_items, answered, reverse_items) if answered else {"theta": 0.0, "se": 1.0}
    theta = est["theta"]

    if max_items is None:
        max_items = max(5, math.ceil(len(all_items) * 0.35))

    candidates = [it for it in all_items if it.get("id") not in answered_ids]

    done = (len(candidates) == 0) or (len(answered) >= max_items) or (est["se"] <= 0.30)

    # 能力分数映射：θ ∈ [-3,3] → [0,100]；θ 越大症状倾向越强
    idx = round((theta + 3) / 6 * 100, 1)
    if theta < -1.0:
        level = "normal"
    elif theta < 0.0:
        level = "mild"
    elif theta < 1.0:
        level = "moderate"
    else:
        level = "severe"

    result = {
        "done": done,
        "next": None,
        "theta": theta,
        "se": est["se"],
        "answered_count": len(answered),
        "max_items": max_items,
        "model": model,
        "score_estimate": {
            "theta_index": idx,
            "level": level,
            "note": "θ>0 表示症状倾向更强；θ<0 表示更健康" + ("（GRM 分级响应模型）" if model == "grm" else "（演示用简化映射）"),
        },
    }

    if not done and candidates:
        best = None
        best_info = -1.0
        for it in candidates:
            a = _item_params(it)[0]
            if model == "grm":
                thresholds = grm_thresholds(it, n_levels)
                info = grm_item_information(theta, a, thresholds)
            else:
                b, c = _item_params(it)[1], _item_params(it)[2]
                info = item_information(theta, a, b, c)
            if info > best_info:
                best_info = info
                best = it
        result["next"] = {"id": best["id"], "text": best["text"]}

    return result



def _item_params(item: dict) -> tuple[float, float, float]:
    """从条目取 IRT 参数 (a 区分度, b 难度, c 猜测)；缺省用默认锚定值。"""
    irt = item.get("irt") or {}
    return (
        float(irt.get("a", 1.0)),
        float(irt.get("b", 0.0)),
        float(irt.get("c", 0.1)),
    )


def probability(theta: float, a: float, b: float, c: float) -> float:
    """3PL 作答概率。"""
    e = math.exp(-D * a * (theta - b))
    return c + (1 - c) / (1 + e)


def item_information(theta: float, a: float, b: float, c: float) -> float:
    """Fisher 信息函数 I(θ)。"""
    e = math.exp(-D * a * (theta - b))
    denom = 1 + e
    p_prime = (1 - c) * D * a * e / (denom * denom)
    p = c + (1 - c) / denom
    q = 1 - p
    if p <= 1e-9 or q <= 1e-9:
        return 0.0
    return (p_prime * p_prime) / (p * q)


def _response_value(item: dict, answer_score: float, reverse: bool = False) -> int:
    """把选项分二值化为 0/1（1=认可/阳性）。"""
    score = float(answer_score)
    if reverse:
        score = -score
    # 中点判定：对 4 点量表，≥3 视为阳性；5 点量表，≥4 视为阳性
    return 1 if score >= 0 else 0


def _score_to_binary(item: dict, answer_score: float, reverse_items: list[int]) -> int:
    """依据条目方向与选项分输出二值作答。"""
    qid = item.get("id")
    if qid in reverse_items:
        # 反向题：选项越低越体现症状，做反转处理后按阈值判定
        return 1 if float(answer_score) <= 2 else 0
    return 1 if float(answer_score) >= 3 else 0


def estimate_theta(items: list[dict], answers: list[dict], reverse_items: list[int]) -> dict:
    """
    EAP 能力估计。

    items: 已答条目（含 id/irt）
    answers: [{"id": .., "score": ..}]
    reverse_items: 反向条目 id 列表
    返回 {"theta": float, "se": float}
    """
    answered_map = {a.get("id"): a.get("score", 0) for a in answers}
    post = []
    for i, t in enumerate(THETA_GRID):
        log_like = 0.0
        for item in items:
            qid = item.get("id")
            if qid not in answered_map:
                continue
            x = _score_to_binary(item, answered_map[qid], reverse_items)
            a, b, c = _item_params(item)
            p = probability(t, a, b, c)
            p = min(max(p, 1e-9), 1 - 1e-9)
            log_like += x * math.log(p) + (1 - x) * math.log(1 - p)
        post.append(PRIOR_WEIGHT[i] * math.exp(log_like) if log_like else PRIOR_WEIGHT[i])

    total = sum(post)
    if total <= 0:
        return {"theta": 0.0, "se": 1.0}
    # 归一化并计算后验均值与标准差（SE）
    denom = 1.0 / total
    mean = sum(t * w for t, w in zip(THETA_GRID, post)) * denom
    var = sum((t - mean) ** 2 * w for t, w in zip(THETA_GRID, post)) * denom
    return {"theta": round(mean, 3), "se": round(math.sqrt(max(var, 1e-6)), 3)}
