"""
虚拟被试合成数据引擎（Virtual Subject Engine）
===============================================

升级项：服务于「诊断学生心理健康」的核心定位，虚拟被试是**合成数据引擎**，
不是训练学生的教学工具。

用途：
  1. 为诊断算法提供可复现的合成数据源（消融实验、信效度验证、等价性验证）
  2. 在无真实数据时，演示系统对虚拟被试的完整自动诊断流程

模块：
  1. 剖面库（PROFILES）：预设典型心理剖面（健康/焦虑/抑郁/压力等）
  2. 生成器（generate_virtual_subject）：按剖面生成被试数据，隐藏真值
  3. 自动诊断（auto_diagnose）：系统从学生可见数据出发自动诊断，与真值对照
  4. 批改引擎（grade_diagnosis）：按评分标准对比诊断与真值（保留用于算法评估）

⚠️ 所有虚拟被试数据均标记 is_virtual=True，与真实学生数据严格隔离。
"""

from __future__ import annotations
import random
import uuid

from backend.services.synthetic_data import (
    generate_scale_answers, generate_e_params, emotion_from_theta,
)

# 评分等级顺序（用于相邻等级判定）
_LEVEL_ORDER = ["normal", "mild", "moderate", "severe"]
_LEVEL_RANK = {"normal": 0, "mild": 1, "moderate": 2, "severe": 3}
_LEVEL_CN = {"normal": "正常", "mild": "轻度", "moderate": "中度", "severe": "重度"}

# 情绪类别顺序（用于相邻判定）
_EMOTION_ORDER = ["positive", "neutral", "mild_negative", "severe_negative"]
_EMOTION_CN = {
    "positive": "积极/开心", "neutral": "平静/中性",
    "mild_negative": "轻度负性", "severe_negative": "重度负性",
}

# 干预建议关键词库（按症状等级给出应包含的关键要素）
_SUGGESTION_KEYWORDS = {
    "normal": ["保持", "维持", "健康", "锻炼", "作息"],
    "mild": ["放松", "倾诉", "运动", "调节", "关注"],
    "moderate": ["心理咨询", "心理老师", "放松训练", "定期", "评估"],
    "severe": ["转介", "专业机构", "精神科", "危机干预", "陪同", "立即"],
}


# ==================== 剖面库 ====================

PROFILES = [
    {
        "id": "healthy_control",
        "name": "健康对照",
        "description": "心理健康的大学生，作息规律，情绪稳定，量表得分正常。",
        "theta": -1.5,
        "dominant_scale": "SAS",
        "teaching_note": "用于演示正常被试的参数特征，作为其他剖面的对照基准。",
    },
    {
        "id": "mild_anxiety",
        "name": "轻度焦虑",
        "description": "近期学业压力较大，偶有紧张、入睡困难，SAS 处于轻度范围。",
        "theta": 0.8,
        "dominant_scale": "SAS",
        "teaching_note": "考察学生能否识别轻度焦虑并给出合理的自我调节建议。",
    },
    {
        "id": "moderate_anxiety",
        "name": "中度焦虑",
        "description": "持续紧张、心慌、注意力下降，SAS 中度，K 值偏高。",
        "theta": 1.5,
        "dominant_scale": "SAS",
        "teaching_note": "考察学生能否识别中度焦虑并建议寻求心理咨询。",
    },
    {
        "id": "depression_tendency",
        "name": "抑郁倾向",
        "description": "情绪低落、兴趣减退、自我评价低，SDS 中度，情绪偏负性。",
        "theta": 1.8,
        "dominant_scale": "SDS",
        "teaching_note": "考察学生能否区分焦虑与抑郁，并识别抑郁倾向的关键特征。",
    },
    {
        "id": "exam_stress",
        "name": "考前压力",
        "description": "期末考试前压力过大，PSS 偏高，情绪紧张但尚未达到临床水平。",
        "theta": 1.0,
        "dominant_scale": "PSS-10",
        "teaching_note": "考察学生能否识别情境性压力并给出时间管理+放松建议。",
    },
    {
        "id": "severe_symptoms",
        "name": "严重症状",
        "description": "多项症状突出，SCL-90 多个维度阳性，情绪严重负性，需立即关注。",
        "theta": 2.5,
        "dominant_scale": "SCL-90",
        "teaching_note": "考察学生能否识别高风险信号并做出转介/危机干预建议。",
    },
    {
        "id": "social_anxiety",
        "name": "社交焦虑",
        "description": "在社交场合中持续紧张、害怕被评价，回避社交活动，SAS 人际敏感维度偏高。",
        "theta": 1.3,
        "dominant_scale": "SCL-90",
        "teaching_note": "考察学生能否识别社交焦虑的情境特异性，并区分于广泛性焦虑。",
    },
    {
        "id": "ocd_tendency",
        "name": "强迫症倾向",
        "description": "反复检查、反复洗手，强迫思维影响学习效率，SCL-90 强迫维度阳性。",
        "theta": 1.6,
        "dominant_scale": "SCL-90",
        "teaching_note": "考察学生能否识别强迫症状的典型特征（反复行为+反强迫痛苦）。",
    },
    {
        "id": "sleep_disorder",
        "name": "睡眠障碍",
        "description": "入睡困难、早醒、睡眠质量差，白天困倦，情绪烦躁，SCL-90 其他维度（睡眠）偏高。",
        "theta": 1.1,
        "dominant_scale": "SCL-90",
        "teaching_note": "考察学生能否识别睡眠问题与情绪问题的双向影响，并给出睡眠卫生建议。",
    },
    {
        "id": "academic_burnout",
        "name": "学习倦怠",
        "description": "对学习失去兴趣、疲惫感、效能感下降，PSS 偏高，情绪麻木，PANAS 正性情绪低。",
        "theta": 1.2,
        "dominant_scale": "PSS-10",
        "teaching_note": "考察学生能否识别学习倦怠的三维度（情绪耗竭/去个性化/低效能感）。",
    },
    {
        "id": "interpersonal_sensitivity",
        "name": "人际敏感",
        "description": "过度在意他人评价、自卑、社交中感到不自在，SCL-90 人际敏感维度偏高。",
        "theta": 1.0,
        "dominant_scale": "SCL-90",
        "teaching_note": "考察学生能否区别人际敏感与社交焦虑，识别自卑认知模式。",
    },
    {
        "id": "panic_tendency",
        "name": "惊恐发作倾向",
        "description": "突发心慌、胸闷、濒死感，发作间期担心再次发作，SAS 重度，K 值波动大。",
        "theta": 2.0,
        "dominant_scale": "SAS",
        "teaching_note": "考察学生能否识别惊恐发作的急性症状特征，并建议医学排查+心理干预。",
    },
    {
        "id": "somatization",
        "name": "躯体化障碍",
        "description": "反复主诉头痛、胃痛、乏力等躯体不适，医学检查无器质性病变，SCL-90 躯体化维度阳性。",
        "theta": 1.4,
        "dominant_scale": "SCL-90",
        "teaching_note": "考察学生能否识别躯体化的心理因素，并建议医学排查+心理评估双轨进行。",
    },
    {
        "id": "low_self_esteem",
        "name": "自卑倾向",
        "description": "自我评价低、过度否定自己、害怕失败，SDS 轻度，PANAS 正性情绪低，情绪偏负性。",
        "theta": 0.9,
        "dominant_scale": "SDS",
        "teaching_note": "考察学生能否识别自卑的认知特征，并给出认知重构+积极反馈建议。",
    },
    {
        "id": "perfectionism",
        "name": "完美主义",
        "description": "对自己要求极高、害怕犯错、过度准备，PSS 偏高，SAS 轻度，情绪紧张但功能尚可。",
        "theta": 0.7,
        "dominant_scale": "PSS-10",
        "teaching_note": "考察学生能否识别适应性完美主义与非适应性完美主义的区别。",
    },
    {
        "id": "emotion_dysregulation",
        "name": "情绪调节困难",
        "description": "情绪波动大、冲动、难以平复，PANAS 正负性情绪均高，K 值波动大，SCL-90 敌对/偏执偏高。",
        "theta": 1.5,
        "dominant_scale": "PANAS",
        "teaching_note": "考察学生能否识别情绪调节困难的特征，并给出情绪调节策略训练建议。",
    },
    {
        "id": "ptsd_tendency",
        "name": "创伤后应激倾向",
        "description": "经历创伤事件后反复闪回、回避相关刺激、过度警觉，SCL-90 焦虑/敌对维度偏高，情绪麻木。",
        "theta": 2.2,
        "dominant_scale": "SCL-90",
        "teaching_note": "考察学生能否识别 PTSD 三大症状群（闯入/回避/高警觉），并建议专业创伤干预。",
    },
    {
        "id": "eating_disorder_tendency",
        "name": "进食障碍倾向",
        "description": "过度关注体重体型、节食或暴食、对身体形象不满，SDS 轻度，PANAS 负性情绪高，女性大学生常见。",
        "theta": 1.3,
        "dominant_scale": "SDS",
        "teaching_note": "考察学生能否识别进食障碍的认知扭曲（身体形象不满），并建议营养+心理双轨干预。",
    },
]


def get_profile(profile_id: str) -> dict | None:
    for p in PROFILES:
        if p["id"] == profile_id:
            return p
    return None


# ==================== 生成器 ====================

def generate_virtual_subject(profile_id: str, seed: int | None = None) -> dict:
    """
    按剖面生成一名虚拟被试。

    返回的「学生可见数据」隐藏真值（量表等级、情绪真值），
    「真值」单独放在 ground_truth 字段（批改时用，不返回给学生）。
    """
    profile = get_profile(profile_id)
    if profile is None:
        raise ValueError(f"未知剖面: {profile_id}")

    rng = random.Random(seed if seed is not None else random.randint(0, 10**9))
    theta = profile["theta"]

    # 生成五套量表作答
    from backend.api.routes.scales import _load_scale, _score_scale
    scales = [_load_scale(c) for c in ["SAS", "SDS", "SCL-90", "PSS-10", "PANAS"]]
    scale_answers = {}
    scale_scores = {}
    for s in scales:
        ans = generate_scale_answers(s, theta, rng)
        scale_answers[s["code"]] = ans
        scale_scores[s["code"]] = _score_scale(s, ans)

    # 生成 E1-E12 参数
    e_params = generate_e_params(theta, rng)
    emotion_label = emotion_from_theta(theta)

    # 真值综合等级：所有量表中等级最严重者（反映综合严重程度）
    dominant = profile["dominant_scale"]
    true_level = max((sc["level"] for sc in scale_scores.values()),
                     key=lambda lv: _LEVEL_RANK.get(lv, 0))

    subject_id = f"VS-{uuid.uuid4().hex[:8].upper()}"

    return {
        "subject_id": subject_id,
        "is_virtual": True,
        "profile_id": profile["id"],
        "profile_name": profile["name"],
        "description": profile["description"],
        "teaching_note": profile["teaching_note"],
        # 学生可见数据（隐藏真值）
        "student_view": {
            "scale_answers": scale_answers,
            "e_params": e_params,
            "k_value": round(min(max(1.5 + 3.0 * max(0.0, theta), 0.5), 12.0), 2),
            "dominant_scale": dominant,
            "note": "请根据以上数据判断该被试的心理状态，并给出干预建议。",
        },
        # 真值（批改用，不返回给学生）
        "ground_truth": {
            "theta": theta,
            "emotion_label": emotion_label,
            "emotion_cn": _EMOTION_CN[emotion_label],
            "dominant_scale": dominant,
            "true_level": true_level,
            "true_level_cn": _LEVEL_CN[true_level],
            "scale_scores": {
                code: {"standard_score": sc["standard_score"], "level": sc["level"]}
                for code, sc in scale_scores.items()
            },
        },
    }


def student_view(subject: dict) -> dict:
    """提取学生可见数据（剥离真值），用于 API 返回给前端。"""
    return {
        "subject_id": subject["subject_id"],
        "is_virtual": True,
        "profile_name": subject["profile_name"],
        "description": subject["description"],
        "teaching_note": subject["teaching_note"],
        **subject["student_view"],
    }


# ==================== 批改引擎 ====================

def grade_diagnosis(subject: dict, student_answer: dict) -> dict:
    """
    按评分标准自动批改学生诊断。

    student_answer: {
        "level_judgment": "normal|mild|moderate|severe",  # 量表等级判断
        "emotion_judgment": "positive|neutral|mild_negative|severe_negative",  # 情绪判断
        "suggestion": "学生写的干预建议文本",
    }

    返回: {total, breakdown, feedback, correct_answer}
    """
    truth = subject["ground_truth"]
    breakdown = {}
    feedback = []

    # 1. 量表等级判断（40 分）
    stu_level = (student_answer.get("level_judgment") or "").lower()
    true_level = truth["true_level"]
    level_score = _score_level(stu_level, true_level, max_score=40)
    breakdown["量表等级判断"] = level_score
    if level_score == 40:
        feedback.append(f"✅ 量表等级判断正确：{_LEVEL_CN[true_level]}")
    elif level_score > 0:
        feedback.append(f"⚠️ 量表等级判断接近：你判断「{_LEVEL_CN.get(stu_level, stu_level)}」，"
                        f"正确为「{_LEVEL_CN[true_level]}」（相邻等级，部分得分）")
    else:
        feedback.append(f"❌ 量表等级判断错误：你判断「{_LEVEL_CN.get(stu_level, stu_level)}」，"
                        f"正确为「{_LEVEL_CN[true_level]}」")

    # 2. 情绪状态判断（30 分）
    stu_emo = (student_answer.get("emotion_judgment") or "").lower()
    true_emo = truth["emotion_label"]
    emo_score = _score_emotion(stu_emo, true_emo, max_score=30)
    breakdown["情绪状态判断"] = emo_score
    if emo_score == 30:
        feedback.append(f"✅ 情绪状态判断正确：{_EMOTION_CN[true_emo]}")
    elif emo_score > 0:
        feedback.append(f"⚠️ 情绪判断接近：你判断「{_EMOTION_CN.get(stu_emo, stu_emo)}」，"
                        f"正确为「{_EMOTION_CN[true_emo]}」")
    else:
        feedback.append(f"❌ 情绪判断错误：你判断「{_EMOTION_CN.get(stu_emo, stu_emo)}」，"
                        f"正确为「{_EMOTION_CN[true_emo]}」")

    # 3. 干预建议合理性（30 分，关键词匹配）
    suggestion = (student_answer.get("suggestion") or "").strip()
    sug_score, matched, missing = _score_suggestion(suggestion, true_level, max_score=30)
    breakdown["干预建议合理性"] = sug_score
    if sug_score == 30:
        feedback.append(f"✅ 干预建议合理，包含关键要素：{', '.join(matched)}")
    elif sug_score > 0:
        feedback.append(f"⚠️ 干预建议部分合理（已包含：{', '.join(matched) or '无'}）；"
                        f"建议补充：{', '.join(missing) or '无'}")
    else:
        feedback.append(f"❌ 干预建议缺少关键要素；针对「{_LEVEL_CN[true_level]}」应包含："
                        f"{', '.join(missing)}")

    total = sum(breakdown.values())
    grade = "优秀" if total >= 85 else "良好" if total >= 70 else "及格" if total >= 60 else "需加强"

    return {
        "subject_id": subject["subject_id"],
        "profile_name": subject["profile_name"],
        "total": total,
        "grade": grade,
        "breakdown": breakdown,
        "feedback": feedback,
        "correct_answer": {
            "量表等级": f"{_LEVEL_CN[true_level]}（{truth['dominant_scale']} 标准分 {truth['scale_scores'][truth['dominant_scale']]['standard_score']}）",
            "情绪状态": _EMOTION_CN[true_emo],
            "建议要点": _SUGGESTION_KEYWORDS[true_level],
        },
    }


def _score_level(stu: str, true: str, max_score: int) -> int:
    """等级评分：完全对满分，相邻等级一半，错 0。"""
    if stu not in _LEVEL_ORDER or true not in _LEVEL_ORDER:
        return 0
    if stu == true:
        return max_score
    if abs(_LEVEL_ORDER.index(stu) - _LEVEL_ORDER.index(true)) == 1:
        return max_score // 2
    return 0


def _score_emotion(stu: str, true: str, max_score: int) -> int:
    """情绪评分：完全对满分，相邻类别一半，错 0。"""
    if stu not in _EMOTION_ORDER or true not in _EMOTION_ORDER:
        return 0
    if stu == true:
        return max_score
    if abs(_EMOTION_ORDER.index(stu) - _EMOTION_ORDER.index(true)) == 1:
        return max_score // 2
    return 0


def _score_suggestion(text: str, true_level: str, max_score: int) -> tuple[int, list[str], list[str]]:
    """建议评分：按关键词匹配，命中越多分越高。"""
    keywords = _SUGGESTION_KEYWORDS.get(true_level, [])
    matched = [kw for kw in keywords if kw in text]
    missing = [kw for kw in keywords if kw not in text]
    if not keywords:
        return max_score, [], []
    ratio = len(matched) / len(keywords)
    score = int(round(max_score * ratio))
    return score, matched, missing


# ==================== 自动诊断 ====================

_LEVEL_RANK = {"normal": 0, "mild": 1, "moderate": 2, "severe": 3}
_EMOTION_RANK = {"positive": 0, "neutral": 1, "mild_negative": 2, "severe_negative": 3}

_NEGATIVE_E_KEYS = ["aggression", "stress", "tension", "suspicious",
                    "inhibition", "neuroticism", "depression"]
_POSITIVE_E_KEYS = ["balance", "charm", "energy", "self_regulation", "happiness"]


def auto_diagnose(subject: dict) -> dict:
    """
    系统自动诊断：从「学生可见数据」（量表作答 + E1-E12 参数 + K 值）出发，
    模拟诊断算法给出结论，并与真值对照，验证诊断算法的准确性。

    返回结构化诊断报告：
      - scale_diagnosis: 各量表计分结果（标准分 + 等级）+ 综合量表等级
      - emotion_diagnosis: 基于前庭参数的情绪状态判定
      - risk_diagnosis: 焦虑抑郁风险分级（复用 risk_assessment 服务）
      - comparison: 与真值逐项对照（量表等级/情绪/是否一致）
    """
    view = subject["student_view"]
    truth = subject["ground_truth"]

    # 1. 量表维度诊断：对五套量表作答重新计分
    from backend.api.routes.scales import _load_scale, _score_scale
    scales = [_load_scale(c) for c in ["SAS", "SDS", "SCL-90", "PSS-10", "PANAS"]]
    scale_results = {}
    for s in scales:
        code = s["code"]
        scoring = _score_scale(s, view["scale_answers"][code])
        scale_results[code] = {
            "raw_score": scoring["raw_score"],
            "standard_score": scoring["standard_score"],
            "level": scoring["level"],
        }
    # 综合量表等级：取所有量表中等级最严重者
    overall_level = max(
        scale_results.values(), key=lambda v: _LEVEL_RANK[v["level"]]
    )["level"]

    # 2. 情绪维度诊断：基于 E1-E12 前庭参数（负性 vs 正性均值）
    #    阈值与 emotion_from_theta 的 θ 分段对齐（θ=1.0/0.3/-0.3 对应边界）
    e = view["e_params"]
    neg_avg = sum(e.get(k, 0) for k in _NEGATIVE_E_KEYS) / len(_NEGATIVE_E_KEYS)
    pos_avg = sum(e.get(k, 0) for k in _POSITIVE_E_KEYS) / len(_POSITIVE_E_KEYS)
    if neg_avg >= 40:
        emotion_diag = "severe_negative"
    elif neg_avg >= 33:
        emotion_diag = "mild_negative"
    elif neg_avg <= 29 and pos_avg >= 50:
        emotion_diag = "positive"
    else:
        emotion_diag = "neutral"

    # 3. 焦虑抑郁风险分级：复用 risk_assessment 服务
    from backend.services.risk_assessment import assess_risk
    risk = assess_risk(
        sas_score=scale_results.get("SAS", {}).get("standard_score"),
        sds_score=scale_results.get("SDS", {}).get("standard_score"),
    )
    risk_level_cn = {"low": "低风险", "medium": "中风险", "high": "高风险", "extreme": "极高风险"}

    # 4. 与真值逐项对照
    comparison = {
        "scale_level_match": overall_level == truth["true_level"],
        "scale_level": overall_level,
        "scale_level_cn": _LEVEL_CN[overall_level],
        "true_level_cn": _LEVEL_CN[truth["true_level"]],
        "emotion_match": emotion_diag == truth["emotion_label"],
        "emotion": emotion_diag,
        "emotion_cn": _EMOTION_CN[emotion_diag],
        "true_emotion_cn": _EMOTION_CN[truth["emotion_label"]],
    }

    return {
        "subject_id": subject["subject_id"],
        "profile_name": subject["profile_name"],
        "profile_id": subject["profile_id"],
        "scale_diagnosis": {
            "detail": scale_results,
            "overall_level": overall_level,
            "overall_level_cn": _LEVEL_CN[overall_level],
        },
        "emotion_diagnosis": {
            "emotion": emotion_diag,
            "emotion_cn": _EMOTION_CN[emotion_diag],
            "neg_avg": round(neg_avg, 2),
            "pos_avg": round(pos_avg, 2),
            "k_value": view.get("k_value", 0),
        },
        "risk_diagnosis": {
            "level": risk.overall_level,
            "level_cn": risk_level_cn.get(risk.overall_level, risk.overall_level),
            "score": risk.overall_score,
            "anxiety": {"level": risk.anxiety_level, "score": risk.anxiety_score},
            "depression": {"level": risk.depression_level, "score": risk.depression_score},
            "recommendations": risk.recommendations,
            "warning_flags": risk.warning_flags,
        },
        "comparison": comparison,
    }
