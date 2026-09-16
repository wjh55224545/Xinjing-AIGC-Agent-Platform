"""
AIGC 报告多轮追问服务
=====================

把治疗性评估（Therapeutic Assessment）的协作反馈原则工程化：
报告生成后，读者可就任一结论追问，AI 基于该生指标数据与证据链解释，
而非泛泛复述。

依据：
  - Finn & Tonsager (1997). Information-gathering and therapeutic models of
    assessment: complementary paradigms. Psychological Assessment.（评估反馈是
    协作过程而非单向告知）
  - Poston & Hanson (2010). Meta-analysis of psychological assessment as a
    therapeutic intervention. Psychological Assessment.（元分析：个性化协作
    反馈整体效应 d=0.423，治疗过程变量 d=1.117）
  - Kluger & DeNisi (1996). The effects of feedback interventions on performance.
    Psychological Bulletin.（反馈干预理论 FIT：任务级反馈优于自我级反馈——
    追问回答应落在具体指标与行为建议上）
"""

from __future__ import annotations
import json
import re
from backend.aigc.llm_client import llm_generate

# 指标中文名映射（用于解释）
_METRIC_CN = {
    "overall_score": "综合评分",
    "emotional_stability_index": "情绪稳定性指数",
    "positive_emotion_ratio": "积极情绪占比",
    "negative_emotion_ratio": "负面情绪占比",
    "trend": "情绪趋势",
    "emotion_recovery_speed": "情绪恢复速度",
    "stress_accumulation_index": "压力累积指数",
    "emotion_fluctuation_entropy": "情绪波动熵",
    "emotion_abrupt_change_count": "情绪突变次数",
}


def _extract_evidence(analysis: dict) -> list:
    """从分析结果中提取可引用的数据点（证据链）。"""
    indicators = analysis.get("indicators", {})
    evidence = []
    for key, cn in _METRIC_CN.items():
        if key in indicators and indicators[key] is not None:
            val = indicators[key]
            if isinstance(val, float):
                val = round(val, 3)
            evidence.append({"metric": cn, "value": val})
    if "risk_level" in analysis:
        risk_cn = {"green": "绿色·低风险", "yellow": "黄色·中等风险", "red": "红色·高风险"}.get(
            analysis["risk_level"], analysis["risk_level"])
        evidence.append({"metric": "风险等级", "value": risk_cn})
    if "overall_score" in analysis:
        evidence.append({"metric": "综合评分", "value": round(analysis["overall_score"], 3)})
    return evidence


def _template_answer(question: str, analysis: dict, evidence: list) -> str:
    """LLM 不可用时的模板解释：从指标中定位相关数据点，按证据链组织回答。"""
    q = question or ""
    indicators = analysis.get("indicators", {})
    risk_level = analysis.get("risk_level", "green")
    risk_cn = {"green": "绿色·低风险", "yellow": "黄色·中等风险", "red": "红色·高风险"}.get(risk_level, risk_level)

    def fmt(name: str, default="—"):
        v = indicators.get(name, default)
        return f"{v}" if v != default else default

    # 常见问题定向解释
    if any(k in q for k in ("风险", "为什么", "等级")):
        reasons = []
        if risk_level == "red":
            reasons.append(f"综合评分 {analysis.get('overall_score', '—')} 偏低，且负面情绪占比 {fmt('negative_emotion_ratio')}、稳定性 {fmt('emotional_stability_index')} 等指标提示需要重视")
        elif risk_level == "yellow":
            reasons.append(f"综合评分 {analysis.get('overall_score', '—')} 处于关注区间，或负面情绪占比 {fmt('negative_emotion_ratio')} 偏高")
        else:
            reasons.append(f"各指标（评分 {analysis.get('overall_score', '—')}、积极占比 {fmt('positive_emotion_ratio')}、稳定性 {fmt('emotional_stability_index')}）均在正常范围")
        return (
            f"当前风险等级判定为【{risk_cn}】。判定依据：{reasons[0]}。"
            f"风险等级由综合评分、情绪构成与稳定性共同决定，并非单一指标；"
            f"如需进一步确认，可结合量表测评结果交叉验证。"
        )

    if any(k in q for k in ("积极", "占比")):
        return (
            f"积极情绪占比当前为 {fmt('positive_emotion_ratio')}，负面情绪占比 {fmt('negative_emotion_ratio')}。"
            f"该占比按当日情绪记录中积极/负面情绪的条数占比计算；"
            f"占比低说明积极体验偏少，建议参照报告建议增加能带来愉悦感的活动，"
            f"并在 1–2 周后复测观察变化。"
        )

    if any(k in q for k in ("稳定", "波动")):
        return (
            f"情绪稳定性指数当前为 {fmt('emotional_stability_index')}（0–1，越高越稳定），"
            f"情绪波动熵为 {fmt('emotion_fluctuation_entropy')}。"
            f"稳定性由评分离散程度计算而来；波动偏大时建议关注作息与压力源，"
            f"必要时结合放松训练。"
        )

    if any(k in q for k in ("恢复", "压力")):
        return (
            f"情绪恢复速度当前为 {fmt('emotion_recovery_speed')}，压力累积指数 {fmt('stress_accumulation_index')}。"
            f"恢复速度反映负面情绪后回到平稳水平的快慢，压力累积反映负面情绪的持续堆积程度；"
            f"两者偏弱/偏高时，深呼吸、正念等放松训练有助于改善，建议持续观察。"
        )

    # 兜底：列出全部证据链
    lines = "；".join(f"{e['metric']}={e['value']}" for e in evidence) or "暂无可用指标"
    return (
        f"关于「{question}」：以下是指标证据链（{lines}）。"
        f"报告结论均基于上述数据得出；如需对某个指标做进一步解释，"
        f"可以直接追问该指标名称，我会给出具体计算口径与建议。"
    )


def answer_followup(
    report_text: str,
    question: str,
    analysis: dict | None = None,
    history: list | None = None,
) -> dict:
    """
    回答对报告结论的追问。

    - 优先 LLM：注入报告文本 + 指标证据链 + 追问历史，要求基于数据回答；
    - LLM 不可用：模板解释（按问题关键词定位指标，输出证据链式回答）。
    """
    analysis = analysis or {}
    evidence = _extract_evidence(analysis)
    history = history or []

    evidence_str = "；".join(f"{e['metric']}={e['value']}" for e in evidence) or "无"
    risk_level = analysis.get("risk_level", "green")
    risk_cn = {"green": "绿色·低风险", "yellow": "黄色·中等风险", "red": "红色·高风险"}.get(risk_level, risk_level)

    # ---- 优先 LLM ----
    system_prompt = (
        "你是一位专业的心理评估报告解释助手。你的任务是回答读者对已生成的心理评估报告的追问。"
        "回答必须基于提供的指标证据链与报告原文，逐条引用具体数据说明结论依据，"
        "不得编造数据，不得泛泛而谈。措辞专业、温暖、有建设性，全中文回答。"
    )
    history_text = ""
    for h in history[-4:]:
        role = "读者" if h.get("role") == "user" else "助手"
        history_text += f"{role}：{h.get('content', '')}\n"

    user_prompt = f"""## 报告原文（节选）
{report_text[:2000]}

## 指标证据链
{evidence_str}

## 风险等级
{risk_cn}

## 追问历史
{history_text or '（无）'}

## 读者追问
{question}

请基于上述指标数据回答追问：先给出直接结论，再引用 2-3 个具体指标说明依据，最后给 1 条可操作建议。"""

    llm_answer = llm_generate(system_prompt, user_prompt, temperature=0.4, max_tokens=1024)
    if llm_answer:
        return {
            "answer": llm_answer,
            "evidence": evidence,
            "generated_by": "心镜·AIGC智能体 (moark.com Qwen3-8B)",
        }

    # ---- 模板降级 ----
    return {
        "answer": _template_answer(question, analysis, evidence),
        "evidence": evidence,
        "generated_by": "心镜·AIGC智能体 (模板解释)",
    }
