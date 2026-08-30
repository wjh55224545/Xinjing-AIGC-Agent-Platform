"""
虚拟被试教学闭环（Virtual Subject Teaching Loop）
================================================

升级项：主攻创新性「教学新模式」+ 应用效果。

解决痛点：心理实验教学依赖真实被试，但真实被试难获取、隐私敏感、
课堂上无法批量演示。虚拟被试由预设心理剖面驱动，生成完整的
量表作答 + E1-E12 情绪参数 + 情绪时序，**隐藏真值**供学生诊断，
学生提交诊断后系统按评分标准自动批改并给出反馈。

模块：
  1. 剖面库（PROFILES）：预设典型心理剖面（健康/焦虑/抑郁/压力等）
  2. 生成器（generate_virtual_subject）：按剖面生成被试数据，隐藏真值
  3. 批改引擎（grade_diagnosis）：按评分标准对比学生诊断与真值，给分+反馈

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

    # 主导量表的真值等级
    dominant = profile["dominant_scale"]
    true_level = scale_scores[dominant]["level"]

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
            "k_value": round(min(max(1.5 + 3.0 * abs(theta), 0.5), 12.0), 2),
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
