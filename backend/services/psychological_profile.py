"""
个体多维心理画像聚合服务
========================

将多源心理评估数据聚合成一张「个体心理画像」：
  - 量表维度画像（SCL-90 十维度 / SAS / SDS 标准分）
  - 前庭生理参数画像（E1-E12 与常模对照的 Z 分雷达）
  - CAT 自适应测验 θ 轨迹（若存在）
  - 焦虑抑郁风险分级（复用 risk_assessment）
  - 综合画像解读（维度显著性 + 风险信号 + 建议）

设计依据（对应 04 技术方案「个体画像」创新点）：
  - HealthPrism 多模态健康画像（Jiang et al., 2023）论证了多源数据
    聚合可视化的临床可用性
  - Wake et al. (2022)：临床仪表盘应采用维度化组件布局，避免信息过载
  - Holzinger et al. (2013)：星图（radar）可视化用于压力状态呈现

⚠️ 本服务支持两种输入：真实学生（student_id，画像来源为量表/AI情绪
记录）与虚拟被试（profile_id，全合成）。输出带 is_synthetic 标记，
不混淆真实与合成数据。
"""

from __future__ import annotations
import json
from datetime import datetime

from backend.services.scale_stats import pearson_r


def build_student_profile(student_id: int) -> dict:
    """
    聚合一名真实学生的多维心理画像。

    数据来源：数据库中的量表结果 + AI 情绪记录 + 预警记录。
    数据不足的维度以空列表/说明返回，不虚构。
    """
    from backend.database import SessionLocal
    from backend.models.scale_result import ScaleResult
    from backend.models.emotion_record import EmotionRecord
    from backend.models.alert import Alert
    from backend.services.risk_assessment import assess_risk

    db = SessionLocal()
    try:
        scales = db.query(ScaleResult).filter(
            ScaleResult.student_id == student_id
        ).order_by(ScaleResult.submitted_at.desc()).all()

        emotions = db.query(EmotionRecord).filter(
            EmotionRecord.student_id == student_id
        ).order_by(EmotionRecord.recorded_at.desc()).limit(50).all()

        alerts = db.query(Alert).filter(
            Alert.student_id == student_id
        ).order_by(Alert.triggered_at.desc()).all()

        # ---- 量表画像 ----
        scale_snapshot = {}
        for r in scales:
            code = r.scale_type
            if code not in scale_snapshot:  # 只取最近一次
                scale_snapshot[code] = {
                    "standard_score": r.standard_score,
                    "level": r.level,
                    "submitted_at": r.submitted_at,
                    "dimension_scores": json.loads(r.dimension_scores) if r.dimension_scores else {},
                }

        scl_dim = scale_snapshot.get("SCL-90", {}).get("dimension_scores", {})
        sas = scale_snapshot.get("SAS", {}).get("standard_score")
        sds = scale_snapshot.get("SDS", {}).get("standard_score")

        # ---- 风险分级 ----
        risk = assess_risk(sas_score=sas, sds_score=sds)
        risk_cn = {"low": "低风险", "medium": "中风险", "high": "高风险", "extreme": "极高风险"}

        # ---- AI 情绪汇总 ----
        emotion_summary = None
        if emotions:
            avg_score = sum(r.fused_score for r in emotions) / len(emotions)
            neg_ratio = sum(1 for r in emotions if r.fused_emotion in {"悲伤", "焦虑", "愤怒", "恐惧"}) / len(emotions)
            emotion_summary = {
                "avg_score": round(avg_score, 3),
                "negative_ratio": round(neg_ratio, 3),
                "n_records": len(emotions),
            }

        # ---- 预警 ----
        alert_summary = [
            {"severity": a.severity, "risk_level": a.risk_level, "triggered_at": a.triggered_at}
            for a in alerts[:5]
        ]

        return {
            "success": True,
            "data": {
                "student_id": student_id,
                "is_synthetic": False,
                "generated_at": datetime.now().isoformat(),
                "scale_profile": {
                    "available_scales": list(scale_snapshot.keys()),
                    "scl90_dimensions": scl_dim,
                    "sas_standard_score": sas,
                    "sds_standard_score": sds,
                },
                "risk": {
                    "overall_level": risk.overall_level,
                    "overall_level_cn": risk_cn.get(risk.overall_level, risk.overall_level),
                    "overall_score": risk.overall_score,
                    "anxiety": {"level": risk.anxiety_level, "score": risk.anxiety_score},
                    "depression": {"level": risk.depression_level, "score": risk.depression_score},
                    "warning_flags": risk.warning_flags,
                    "recommendations": risk.recommendations,
                },
                "emotion_summary": emotion_summary,
                "alert_history": alert_summary,
                "vestibular_profile": None,  # 学生维度若无 E1-E12 记录则为 None（避免虚构）
                "missing": {
                    "scl90": "SCL-90" not in scale_snapshot,
                    "sas": sas is None,
                    "sds": sds is None,
                },
                "note": "画像基于该学生在系统内的量表与AI情绪记录聚合；缺少的维度不填充，随数据积累自动充实。",
            },
        }
    finally:
        db.close()


def build_virtual_profile(profile_id: str, seed: int | None = None) -> dict:
    """
    为一名虚拟被试生成完整多维心理画像（全合成数据）。

    包含：量表画像（SCL-90 十维 + SAS/SDS）、E1-E12 前庭参数 Z 分、
    风险分级、应对倾向画像（SJT 合成作答）。
    """
    import random

    from backend.services.virtual_subject import (
        PROFILES, get_profile, generate_virtual_subject, auto_diagnose,
    )
    from backend.services.synthetic_data import generate_e_params
    from backend.api.routes.scales import _load_scale, _score_scale
    from backend.vibraimage.utils.constants import (
        NORMAL_NORMS, NORMAL_SDS, PARAM_NAMES_ZH, ALL_EMOTION_PARAMS,
        NEGATIVE_EMOTIONS, POSITIVE_EMOTIONS, PHYSIOLOGICAL_EMOTIONS,
    )
    from backend.services.sjt import _load_bank, score_sjt

    profile = get_profile(profile_id)
    if profile is None:
        return {"success": False, "detail": f"未知剖面: {profile_id}"}

    subject = generate_virtual_subject(profile_id, seed=seed)
    rng = random.Random(seed if seed is not None else 42)

    # ---- 量表画像 ----
    scales = [_load_scale(c) for c in ["SAS", "SDS", "SCL-90", "PSS-10", "PANAS"]]
    scale_profiles = {}
    for s in scales:
        ans = subject["student_view"]["scale_answers"][s["code"]]
        scoring = _score_scale(s, ans)
        scale_profiles[s["code"]] = {
            "standard_score": scoring["standard_score"],
            "level": scoring["level"],
            "dimension_scores": scoring.get("dimension_scores", {}),
        }
    scl_dim = scale_profiles.get("SCL-90", {}).get("dimension_scores", {})

    # ---- 风险分级 ----
    from backend.services.risk_assessment import assess_risk
    risk = assess_risk(
        sas_score=scale_profiles.get("SAS", {}).get("standard_score"),
        sds_score=scale_profiles.get("SDS", {}).get("standard_score"),
    )
    risk_cn = {"low": "低风险", "medium": "中风险", "high": "高风险", "extreme": "极高风险"}

    # ---- E1-E12 前庭 Z 分画像 ----
    e_params = subject["student_view"]["e_params"]
    vestib = []
    for p in ALL_EMOTION_PARAMS:
        mean = NORMAL_NORMS.get(p)
        sd = NORMAL_SDS.get(p)
        val = e_params.get(p)
        z = (val - mean) / sd if (val is not None and mean is not None and sd) else 0.0
        group = (
            "negative" if p in NEGATIVE_EMOTIONS
            else "positive" if p in POSITIVE_EMOTIONS
            else "physiological"
        )
        vestib.append({
            "key": p, "name_zh": PARAM_NAMES_ZH.get(p, p),
            "value": val, "norm_mean": mean, "norm_sd": sd,
            "z_score": round(z, 2), "group": group,
        })
    k_value = subject["student_view"]["k_value"]

    # ---- SJT 应对倾向画像（合成作答） ----
    bank = _load_bank()
    sjt_answers = []
    theta = profile["theta"]
    for q in bank["questions"]:
        p_good = 1.0 / (1.0 + 2.71828 ** (1.2 * theta))
        scores = [o["score"] for o in q["options"]]
        max_s = max(scores)
        weights = []
        for s in scores:
            w = p_good * (s / max_s) + (1 - p_good) * (1 - s / max_s)
            weights.append(max(w, 1e-3))
        sjt_answers.append({"id": q["id"], "choice": rng.choices(range(len(q["options"])), weights=weights, k=1)[0]})
    sjt_result = score_sjt(sjt_answers)
    sjt_data = sjt_result.get("data", {}) if sjt_result.get("success") else None

    # ---- 自动诊断对照 ----
    diag = auto_diagnose(subject)
    comparison = diag.get("comparison", {})

    return {
        "success": True,
        "data": {
            "subject_id": subject["subject_id"],
            "profile_id": profile_id,
            "profile_name": profile["name"],
            "profile_description": profile["description"],
            "is_synthetic": True,
            "generated_at": datetime.now().isoformat(),
            "theta": theta,
            "scale_profile": {
                "scl90_dimensions": scl_dim,
                "sas_standard_score": scale_profiles.get("SAS", {}).get("standard_score"),
                "sds_standard_score": scale_profiles.get("SDS", {}).get("standard_score"),
                "pss10_standard_score": scale_profiles.get("PSS-10", {}).get("standard_score"),
                "panas_standard_score": scale_profiles.get("PANAS", {}).get("standard_score"),
                "detail": scale_profiles,
            },
            "vestibular_profile": {
                "params": vestib,
                "k_value": k_value,
                "k_interpretation": _k_interpret(k_value),
                "source": "VCE.pdf (Minkin, 2020) Table 6-18 常模对照",
            },
            "risk": {
                "overall_level": risk.overall_level,
                "overall_level_cn": risk_cn.get(risk.overall_level, risk.overall_level),
                "overall_score": risk.overall_score,
                "anxiety": {"level": risk.anxiety_level, "score": risk.anxiety_score},
                "depression": {"level": risk.depression_level, "score": risk.depression_score},
                "warning_flags": risk.warning_flags,
                "recommendations": risk.recommendations,
            },
            "sjt_profile": sjt_data,
            "diagnosis_consistency": {
                "scale_level_match": comparison.get("scale_level_match"),
                "true_level_cn": comparison.get("true_level_cn"),
                "pred_level_cn": comparison.get("scale_level_cn"),
                "emotion_match": comparison.get("emotion_match"),
            },
            "note": "全合成数据（is_synthetic=True），用于画像组件演示与算法验证，不冒充真实样本。",
        },
    }


def _k_interpret(k: float | None) -> str:
    from backend.vibraimage.utils.constants import K_INTERPRETATION
    if k is None:
        return "无K值数据"
    for (lo, hi), text in K_INTERPRETATION.items():
        if lo <= abs(k) < hi:
            return text
    return "K值超出解释区间"
