"""
三模态情绪融合引擎（Dempster-Shafer 证据理论，含不确定性焦点 Ω）
================================================================

升级背景：原系统 `emotion_recognition.py` 使用**固定权重**（面部0.6 + 前庭0.4）
的线性加权融合，无置信度输出、无法表达"证据冲突"。

本模块提供基于 **Dempster-Shafer 证据理论** 的多模态融合：
  - 焦点元素：{正性(P), 负性(N), 中性(Neutral), 未知(Ω)}
  - 每个模态根据自身情绪类别、效价、置信度生成基本概率分配（BPA/mass）
  - **置信度折扣**：低置信模态的 mass 大量流向 Ω（未知），融合时被稀释，
    避免低质量证据污染结论 —— 这是 D-S 相对固定权重加权的关键优势
  - 融合规则：Dempster 合成规则，输出合成 mass、冲突系数、不确定性、
    最终判定与置信度；主导焦点分歧时标记 requires_review

三类输入（均可缺省，缺省的模态不参与合成）：
  - facial:     {valence, arousal, confidence, emotion}
  - vestibular: {valence, arousal, confidence, emotion}
  - scale:      {theta, confidence}  量表/CAT 能力估计（θ>0 症状倾向更强）
"""

from __future__ import annotations

_FOCUS = ("positive", "negative", "neutral")   # 具体焦点
_ALL = ("positive", "negative", "neutral", "unknown")  # 含未知焦点


def _complete(m: dict) -> dict:
    """把（可能缺 unknown 的）mass 补全为 4 焦点、和为 1。"""
    mm = {k: max(0.0, float(m.get(k, 0.0))) for k in _FOCUS}
    total = sum(mm.values())
    if total <= 1e-9:
        return {k: 1 / 4 for k in _ALL}
    unknown = max(0.0, 1.0 - total)
    mm["unknown"] = unknown
    return mm


def _va_to_masses(valence: float, arousal: float, confidence: float) -> dict:
    """
    由效价-唤醒度生成 mass（含未知焦点 Ω）。

    先按 VA 象限给出三类证据强度，再做**置信度折扣**：
      m(具体焦点) = confidence · base；m(Ω) = 1 - confidence
    置信度越低，证据越不确定（mass 流向 Ω），融合时影响越小。
    """
    v = max(min(float(valence), 1.0), -1.0)
    a = max(min(float(arousal), 1.0), -1.0)
    conf = max(min(float(confidence), 1.0), 0.05)

    if v >= 0.15 and a >= -0.2:
        base = {"positive": 0.8, "negative": 0.1, "neutral": 0.1}
    elif v <= -0.15:
        base = {"positive": 0.1, "negative": 0.8, "neutral": 0.1}
    else:
        # 中性带：valence 居中且 arousal 低 → 更偏中性
        base = {"positive": 0.2, "negative": 0.2, "neutral": 0.6}

    masses = {k: base[k] * conf for k in _FOCUS}
    masses["unknown"] = round(max(0.0, 1.0 - conf), 4)
    return masses


def _scale_to_masses(theta: float, confidence: float) -> dict:
    """由量表/CAT 能力估计生成 mass（含 Ω，置信度折扣）。"""
    t = max(min(float(theta), 3.0), -3.0)
    conf = max(min(float(confidence), 1.0), 0.3)
    if t >= 0.5:
        base = {"positive": 0.1, "negative": 0.85, "neutral": 0.05}
    elif t <= -0.5:
        base = {"positive": 0.85, "negative": 0.1, "neutral": 0.05}
    else:
        base = {"positive": 0.3, "negative": 0.3, "neutral": 0.4}

    masses = {k: base[k] * conf for k in _FOCUS}
    masses["unknown"] = round(max(0.0, 1.0 - conf), 4)
    return masses


def dempster_combine(m1: dict, m2: dict) -> tuple[dict, float]:
    """
    Dempster 合成规则（两个证据源，含 Ω 焦点）。

    返回: (合成 mass, 冲突系数 K)
    K = Σ_{A∩B=∅} m1(A)m2(B)，仅具体焦点间异类相交产生冲突；
    unknown 与其他焦点相交 = 对方（不冲突）。
    """
    a1, a2 = _complete(m1), _complete(m2)
    combined = {k: 0.0 for k in _ALL}
    k = 0.0
    for x in _ALL:
        for y in _ALL:
            prod = a1[x] * a2[y]
            if prod <= 0:
                continue
            if x == y:
                combined[x] += prod
            elif x == "unknown":
                combined[y] += prod
            elif y == "unknown":
                combined[x] += prod
            else:
                k += prod  # 两个不同具体焦点的相交 = 空集 → 冲突
    denom = 1 - k
    if denom <= 1e-9:
        # 完全冲突 → 按证据平均（mass 归一）并标记 K≈1
        out = {}
        for z in _ALL:
            out[z] = (a1[z] + a2[z]) / 2
        return _normalize_all(out), round(k, 4)
    return _normalize_all({z: v / denom for z, v in combined.items()}), round(k, 4)


def _normalize_all(m: dict) -> dict:
    """4 焦点归一化到和为 1。"""
    total = sum(m.get(k, 0.0) for k in _ALL)
    if total <= 1e-9:
        return {k: 1 / 4 for k in _ALL}
    return {k: m.get(k, 0.0) / total for k in _ALL}


def combine_masses(masses: list[dict]) -> dict:
    """顺序合成多个证据源的 mass。"""
    if not masses:
        return {k: 1 / 4 for k in _ALL}
    result = masses[0]
    for m in masses[1:]:
        result, _ = dempster_combine(result, m)
    return _normalize_all(result)


def _emotion_from_masses(m: dict) -> str:
    """由合成 mass 判定情绪类别（排除 Ω，取具体焦点中最大者）。"""
    label = max(_FOCUS, key=lambda k: m.get(k, 0.0))
    return {"positive": "开心", "negative": "焦虑", "neutral": "平静"}[label]


def _score_from_masses(m: dict) -> float:
    """由 mass 映射到 0-1 得分（正性贡献正向，负性贡献反向）。"""
    return round(min(max(0.15 + 0.7 * m.get("positive", 0) - 0.7 * m.get("negative", 0), 0.0), 1.0), 3)


def fuse_three_modal(
    facial: dict | None = None,
    vestibular: dict | None = None,
    scale: dict | None = None,
) -> dict:
    """
    三模态 D-S 融合入口。

    facial/vestibular: {valence, arousal, confidence}
    scale: {theta, confidence}
    返回: {emotion, score, confidence, uncertainty, conflict, requires_review,
           top_labels, n_modalities, evidence, model}
    """
    masses = []
    evidence = {}
    if facial:
        fm = _va_to_masses(facial.get("valence", 0), facial.get("arousal", 0),
                           facial.get("confidence", 0.6))
        masses.append(fm)
        evidence["facial_mass"] = {k: round(v, 4) for k, v in fm.items()}
    if vestibular:
        vm = _va_to_masses(vestibular.get("valence", 0), vestibular.get("arousal", 0),
                           vestibular.get("confidence", 0.6))
        masses.append(vm)
        evidence["vestibular_mass"] = {k: round(v, 4) for k, v in vm.items()}
    if scale:
        sm = _scale_to_masses(scale.get("theta", 0), scale.get("confidence", 0.6))
        masses.append(sm)
        evidence["scale_mass"] = {k: round(v, 4) for k, v in sm.items()}

    fused = combine_masses(masses)
    evidence["fused_mass"] = {k: round(v, 4) for k, v in fused.items()}

    # 冲突系数：两两冲突的均值（信息输出用）
    conflicts = []
    for i in range(len(masses)):
        for j in range(i + 1, len(masses)):
            _, k = dempster_combine(masses[i], masses[j])
            conflicts.append(k)
    conflict = round(sum(conflicts) / len(conflicts), 4) if conflicts else 0.0

    # 不确定性 = fused 中 Ω 的 mass；置信度 = 1 - 不确定性
    uncertainty = round(fused.get("unknown", 0.0), 3)
    confidence = round(max(0.0, min(1.0 - uncertainty, 1.0)), 3)

    # 复核判定：各模态**主导焦点**是否分歧（比冲突系数更稳健）
    top_labels = []
    for m in masses:
        top_labels.append(max(_FOCUS, key=lambda k: m.get(k, 0.0)))
    requires_review = len(set(top_labels)) > 1

    # conflict-aware 决策：分歧时**仅当某模态置信度显著领先**（≥0.15）才采纳
    # 其判定兜底；否则仍用 D-S 融合结果（多证据汇聚已利用多数模态）。
    decision = {"emotion": _emotion_from_masses(fused), "confidence": confidence}
    if requires_review and masses:
        confs = [1.0 - m.get("unknown", 0.0) for m in masses]
        sorted_conf = sorted(confs, reverse=True)
        if len(sorted_conf) >= 2 and (sorted_conf[0] - sorted_conf[1]) >= 0.15:
            best_idx = confs.index(sorted_conf[0])
            best = masses[best_idx]
            best_label = max(_FOCUS, key=lambda k: best.get(k, 0.0))
            decision = {
                "emotion": {"positive": "开心", "negative": "焦虑", "neutral": "平静"}[best_label],
                "confidence": round(1.0 - best.get("unknown", 0.0), 3),
                "source": "best-evidence-fallback",
            }

    return {
        "model": "ds-3modal",
        "emotion": decision["emotion"],
        "score": _score_from_masses(fused),
        "confidence": decision["confidence"],
        "uncertainty": uncertainty,
        "conflict": conflict,
        "requires_review": requires_review,
        "top_labels": top_labels,
        "decision_source": decision.get("source", "ds-fusion"),
        "n_modalities": len(masses),
        "evidence": evidence,
    }


def fuse_two_modal(facial: dict | None = None,
                   vestibular: dict | None = None) -> dict:
    """双模态 D-S 融合（兼容原"面部+前庭"，但改为证据融合）。"""
    result = fuse_three_modal(facial=facial, vestibular=vestibular, scale=None)
    result["model"] = "ds-2modal"
    return result
