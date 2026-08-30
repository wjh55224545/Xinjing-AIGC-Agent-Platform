"""
焦虑抑郁风险分级筛查服务
========================

升级项：主攻临床心理学应用（焦虑抑郁风险评估）。

基于心理量表数据综合评估焦虑/抑郁风险，输出风险等级（低/中/高/极高）
+ 各维度评分 + 分级干预建议。

评估维度（纯量表数据，不依赖硬件信号）：
  1. 焦虑维度：SAS / GAD-7
  2. 抑郁维度：SDS / PHQ-9（含第9题自杀意念筛查）

风险分级：
  - 低风险：各量表均正常
  - 中风险：单一量表轻度，或多量表临界
  - 高风险：量表达到中度，或多量表轻度
  - 极高风险：量表达到重度，或含自杀意念阳性

文献依据：
  - SAS: Zung (1971). A rating instrument for anxiety disorders. Psychosomatics.
  - SDS: Zung (1965). A self-rating depression scale. Arch Gen Psychiatry.
  - PHQ-9: Kroenke, Spitzer & Williams (2001). J Gen Intern Med.
  - GAD-7: Spitzer et al. (2006). Arch Intern Med.
  - 风险分级参考：NICE 指南（CG113 焦虑、CG90 抑郁）
"""

from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class RiskAssessment:
    """风险评估结果。"""
    overall_level: str = "low"                    # 综合风险等级
    overall_score: float = 0.0                    # 综合风险分（0-100）
    anxiety_level: str = "normal"                 # 焦虑等级
    anxiety_score: float = 0.0                    # 焦虑分（0-100）
    depression_level: str = "normal"              # 抑郁等级
    depression_score: float = 0.0                 # 抑郁分（0-100）
    suicide_risk: bool = False                     # 自杀风险（PHQ-9 第9题）
    dimensions: dict = field(default_factory=dict)  # 各维度详情
    recommendations: list = field(default_factory=list)  # 干预建议
    warning_flags: list = field(default_factory=list)    # 警示标记


# 量表得分归一化（0-100，越高风险越大）
def _normalize_scale(score: float, cutoff_normal: float, cutoff_severe: float) -> float:
    """将量表原始分归一化到 0-100 风险分。"""
    if score <= cutoff_normal:
        return round(score / cutoff_normal * 30, 1)
    elif score <= cutoff_severe:
        return round(30 + (score - cutoff_normal) / (cutoff_severe - cutoff_normal) * 40, 1)
    else:
        return round(min(70 + (score - cutoff_severe) / cutoff_severe * 30, 100), 1)


def _level_from_score(score: float) -> str:
    if score < 30:
        return "normal"
    elif score < 50:
        return "mild"
    elif score < 70:
        return "moderate"
    else:
        return "severe"


def assess_risk(
    sas_score: float | None = None,
    sds_score: float | None = None,
    phq9_score: float | None = None,
    phq9_q9: int | None = None,       # PHQ-9 第9题（自杀意念，0-3）
    gad7_score: float | None = None,
) -> RiskAssessment:
    """
    综合焦虑抑郁风险分级筛查（纯量表数据）。

    所有参数均为可选，至少提供一个量表得分即可进行评估。
    提供的量表越多，评估越准确。
    """
    result = RiskAssessment()

    # 1. 焦虑维度
    anxiety_scores = []
    if sas_score is not None:
        s = _normalize_scale(sas_score, 49, 70)
        anxiety_scores.append(s)
        result.dimensions["SAS"] = {"raw": sas_score, "risk_score": s,
                                      "level": _level_from_score(s)}
    if gad7_score is not None:
        s = _normalize_scale(gad7_score, 4, 15)
        anxiety_scores.append(s)
        result.dimensions["GAD-7"] = {"raw": gad7_score, "risk_score": s,
                                        "level": _level_from_score(s)}
    if anxiety_scores:
        result.anxiety_score = round(sum(anxiety_scores) / len(anxiety_scores), 1)
        result.anxiety_level = _level_from_score(result.anxiety_score)

    # 2. 抑郁维度
    depression_scores = []
    if sds_score is not None:
        s = _normalize_scale(sds_score, 52, 72)
        depression_scores.append(s)
        result.dimensions["SDS"] = {"raw": sds_score, "risk_score": s,
                                      "level": _level_from_score(s)}
    if phq9_score is not None:
        s = _normalize_scale(phq9_score, 4, 15)
        depression_scores.append(s)
        result.dimensions["PHQ-9"] = {"raw": phq9_score, "risk_score": s,
                                        "level": _level_from_score(s)}
    if depression_scores:
        result.depression_score = round(sum(depression_scores) / len(depression_scores), 1)
        result.depression_level = _level_from_score(result.depression_score)

    # 3. 自杀风险（PHQ-9 第9题，临床金标准筛查项）
    if phq9_q9 is not None and phq9_q9 >= 1:
        result.suicide_risk = True
        result.warning_flags.append(
            f"PHQ-9 第9题（自杀意念）得分={phq9_q9}，阳性（≥1），"
            "需立即评估自杀风险（文献：PHQ-9 第9题阳性预测自杀行为的似然比=5.4）"
        )

    # 4. 综合风险分（最高分权重0.5 + 平均分权重0.5）
    all_scores = []
    if anxiety_scores:
        all_scores.append(result.anxiety_score)
    if depression_scores:
        all_scores.append(result.depression_score)

    if all_scores:
        result.overall_score = round(
            max(all_scores) * 0.5 + sum(all_scores) / len(all_scores) * 0.5, 1
        )

    # 5. 综合风险等级判定
    if result.suicide_risk or result.overall_score >= 75:
        result.overall_level = "extreme"
    elif result.overall_score >= 55:
        result.overall_level = "high"
    elif result.overall_score >= 35:
        result.overall_level = "medium"
    else:
        result.overall_level = "low"

    # 6. 分级干预建议
    _generate_recommendations(result)

    return result


def _generate_recommendations(result: RiskAssessment) -> None:
    """根据风险等级生成干预建议（参考 NICE 指南 CG113/CG90）。"""
    level_cn = {
        "low": "低风险", "medium": "中风险",
        "high": "高风险", "extreme": "极高风险",
    }
    result.recommendations.append(
        f"综合风险等级：{level_cn.get(result.overall_level, result.overall_level)}"
        f"（综合分 {result.overall_score}/100）"
    )

    if result.overall_level == "low":
        result.recommendations.append("保持健康生活方式：规律作息、适度运动、社交活动")
        result.recommendations.append("建议每学期进行一次心理状态自评，关注情绪变化")
    elif result.overall_level == "medium":
        result.recommendations.append("建议关注情绪状态，记录情绪日记，识别压力源")
        result.recommendations.append("推荐放松训练：深呼吸、正念冥想、渐进式肌肉放松")
        result.recommendations.append("建议寻求学校心理咨询中心支持，进行1-2次咨询评估")
        result.recommendations.append("2-4周后复评，观察症状变化趋势")
    elif result.overall_level == "high":
        result.recommendations.append("建议尽快预约学校心理咨询中心或精神科门诊进行专业评估")
        result.recommendations.append("在专业指导下进行心理干预（认知行为疗法CBT等，NICE推荐一线疗法）")
        result.recommendations.append("建议告知信任的家人或朋友，获得社会支持")
        result.recommendations.append("避免独处，保持规律作息，避免酒精和咖啡因")
        result.recommendations.append("1-2周内复评，密切关注症状变化")
    elif result.overall_level == "extreme":
        result.recommendations.append("立即寻求专业帮助：精神科急诊或心理危机干预热线")
        result.recommendations.append("确保24小时有人陪伴，移除危险物品")
        result.recommendations.append("立即通知家属/辅导员/心理咨询中心")
        result.recommendations.append("在专业评估前不要独处，不要做重大决定")

    # 维度-specific 建议
    if result.anxiety_level in ["moderate", "severe"]:
        result.recommendations.append("焦虑症状明显：推荐焦虑管理训练（暴露疗法、放松训练，NICE CG113推荐）")
    if result.depression_level in ["moderate", "severe"]:
        result.recommendations.append("抑郁症状明显：推荐行为激活（增加愉快活动）、认知重构（NICE CG90推荐）")
