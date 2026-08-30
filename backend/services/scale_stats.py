"""
量表 × AI 情绪 交叉验证统计检验
================================

为「量表×AI交叉验证」提供可量化的效度证据，对应 04 技术方案
「量表与 AI 情绪数据可交叉校验，为 AI 评估提供标准化效度基准」。

实现指标：
  - Pearson 相关系数 r（量表标准分 vs AI 平均融合分）
  - Cohen's Kappa 一致性（量表风险等级 vs AI 风险等级，二值化）
  - 灵敏度 / 特异度 / 约登指数（量表提示高风险 视为"金标准"）

说明：所有指标均为从真实记录现算，无虚构数据。
"""

from __future__ import annotations
import math


def pearson_r(xs: list[float], ys: list[float]) -> float:
    """Pearson 相关系数。"""
    n = len(xs)
    if n < 3 or n != len(ys):
        return 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 1e-12 or syy <= 1e-12:
        return 0.0
    r = sxy / math.sqrt(sxx * syy)
    return round(min(max(r, -1.0), 1.0), 4)


def cohen_kappa(actual: list[bool], predicted: list[bool]) -> float:
    """Cohen's Kappa（二值一致性）。"""
    n = len(actual)
    if n == 0 or len(predicted) != n:
        return 0.0
    a = b = c = d = 0
    for x, y in zip(actual, predicted):
        if x and y:
            a += 1
        elif x and not y:
            b += 1
        elif not x and y:
            c += 1
        else:
            d += 1
    total = a + b + c + d
    if total == 0:
        return 0.0
    po = (a + d) / total
    pe = ((a + b) * (a + c) + (c + d) * (b + d)) / (total * total)
    if pe == 1.0:
        return 0.0
    kappa = (po - pe) / (1 - pe)
    return round(kappa, 4)


def binary_metrics(actual: list[bool], predicted: list[bool]) -> dict:
    """灵敏度 / 特异度 / 约登指数（actual=量表金标准，predicted=AI 判定）。"""
    tp = fp = fn = tn = 0
    for x, y in zip(actual, predicted):
        if x and y:
            tp += 1
        elif x and not y:
            fn += 1
        elif not x and y:
            fp += 1
        else:
            tn += 1
    sensitivity = tp / (tp + fn) if (tp + fn) else 0.0
    specificity = tn / (tn + fp) if (tn + fp) else 0.0
    youden = sensitivity + specificity - 1
    return {
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "sensitivity": round(sensitivity, 4),
        "specificity": round(specificity, 4),
        "youden_index": round(youden, 4),
        "accuracy": round((tp + tn) / max(tp + fp + fn + tn, 1), 4),
    }


# ==================== 信效度检验（升级新增） ====================

def cronbach_alpha(scores_by_subject: list[list[float]]) -> float:
    """
    Cronbach's α 内部一致性系数。

    scores_by_subject: 每名被试对各条目的得分（n_subjects × n_items）
    α = (k/(k-1)) · (1 - Σσ_i²/σ_total²)，k=条目数
    """
    k = len(scores_by_subject[0]) if scores_by_subject else 0
    n = len(scores_by_subject)
    if k < 2 or n < 2:
        return 0.0
    # 逐条目方差（列方差）
    item_var = []
    for j in range(k):
        vals = [row[j] for row in scores_by_subject]
        m = sum(vals) / n
        item_var.append(sum((v - m) ** 2 for v in vals) / n)
    # 总方差 = 每名被试总分的方差
    row_sums = [sum(row) for row in scores_by_subject]
    m_total = sum(row_sums) / n
    total_var = sum((t - m_total) ** 2 for t in row_sums) / n
    denom = total_var
    if denom <= 1e-12:
        # 条目间完全同质（总方差≈0）时按满分处理
        return 1.0 if sum(item_var) <= 1e-12 else 0.0
    alpha = (k / (k - 1)) * (1 - sum(item_var) / denom)
    return round(min(max(alpha, 0.0), 1.0), 4)


def inter_item_correlation(scores_by_subject: list[list[float]]) -> float:
    """条目间平均相关（内部一致性的补充指标）。"""
    k = len(scores_by_subject[0]) if scores_by_subject else 0
    if k < 2:
        return 0.0
    rs = []
    for i in range(k):
        for j in range(i + 1, k):
            r = pearson_r([row[i] for row in scores_by_subject],
                          [row[j] for row in scores_by_subject])
            rs.append(r)
    return round(sum(rs) / len(rs), 4) if rs else 0.0


def dimension_correlation_matrix(dimension_scores: list[dict]) -> dict:
    """
    结构效度（简化）：量表各维度得分的相关矩阵。

    dimension_scores: 每名被试的 {维度名: 得分} 列表
    返回: {维度A: {维度B: r, ...}, ...}
    """
    if not dimension_scores:
        return {}
    dims = list(dimension_scores[0].keys())
    matrix = {}
    for d1 in dims:
        matrix[d1] = {}
        for d2 in dims:
            xs = [row[d1] for row in dimension_scores]
            ys = [row[d2] for row in dimension_scores]
            matrix[d1][d2] = pearson_r(xs, ys)
    return matrix


def reliability_bundle(scores_by_subject: list[list[float]]) -> dict:
    """汇总内部一致性指标（供 /api/scales/validation/summary 使用）。"""
    return {
        "cronbach_alpha": cronbach_alpha(scores_by_subject),
        "inter_item_correlation": inter_item_correlation(scores_by_subject),
        "n_subjects": len(scores_by_subject),
        "n_items": len(scores_by_subject[0]) if scores_by_subject else 0,
    }

