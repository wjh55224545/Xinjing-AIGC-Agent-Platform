"""
预警-干预闭环统计服务
====================

依据（JITAI 即时自适应干预）：
  - Nahumshani et al. (2018). Just-in-time adaptive interventions (JITAIs) in
    mobile health: key components and design principles. Annals of Behavioral Medicine.
  - Bidargaddi et al. (2020). Designing m-health interventions for precision
    mental health support. Translational Psychiatry.
  - Marciniak et al. (2020). Standalone smartphone CBT-based ecological momentary
    interventions to increase mental health: narrative review. JMIR mHealth and uHealth.

闭环定义：预警触发 → 记录干预前指标 → 生成干预建议 → 设定复测日期 →
复测记录干预后指标 → 统计干预前后变化（均值变化 / 风险等级迁移 / 好转率）。
"""

from __future__ import annotations
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.models.intervention_cycle import InterventionCycle

# 复测间隔（天）：依据 NICE CG113/CG90 对轻中度焦虑抑郁建议 2-4 周复评，
# 本项目取中间值 14 天作为默认复测间隔。
DEFAULT_FOLLOW_UP_DAYS = 14

OUTCOME_THRESHOLD = 0.05  # 综合评分变化超过 ±0.05 记为 好转/加重


def _now_str() -> str:
    return datetime.now().isoformat()


def _date_plus_days(days: int) -> str:
    return (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")


def create_cycle(
    db: Session,
    student_id: int,
    alert_id: int,
    risk_level_before: str,
    plan_text: str = "",
    metrics_before: dict | None = None,
    follow_up_days: int = DEFAULT_FOLLOW_UP_DAYS,
) -> InterventionCycle:
    """预警触发时创建干预闭环。"""
    cycle = InterventionCycle(
        student_id=student_id,
        alert_id=alert_id,
        risk_level_before=risk_level_before,
        plan_text=plan_text,
        metrics_before=json.dumps(metrics_before or {}, ensure_ascii=False),
        follow_up_days=follow_up_days,
        follow_up_date=_date_plus_days(follow_up_days),
        status="open",
        created_at=_now_str(),
    )
    db.add(cycle)
    db.commit()
    db.refresh(cycle)
    return cycle


def complete_cycle(
    db: Session,
    cycle_id: int,
    metrics_after: dict | None = None,
) -> InterventionCycle | None:
    """复测完成后记录干预后指标，并判定结局（improved/stable/worsened）。"""
    cycle = db.query(InterventionCycle).filter(InterventionCycle.id == cycle_id).first()
    if not cycle:
        return None

    after = metrics_after or {}
    before = json.loads(cycle.metrics_before or "{}")

    # 结局判定：优先用综合评分变化，其次负面情绪占比
    outcome = ""
    b_score = before.get("overall_score")
    a_score = after.get("overall_score")
    if b_score is not None and a_score is not None:
        delta = a_score - b_score
        outcome = "improved" if delta >= OUTCOME_THRESHOLD else (
            "worsened" if delta <= -OUTCOME_THRESHOLD else "stable")
    else:
        b_neg = before.get("negative_emotion_ratio")
        a_neg = after.get("negative_emotion_ratio")
        if b_neg is not None and a_neg is not None:
            delta = b_neg - a_neg
            outcome = "improved" if delta >= OUTCOME_THRESHOLD else (
                "worsened" if delta <= -OUTCOME_THRESHOLD else "stable")
    if not outcome:
        outcome = "stable"

    cycle.metrics_after = json.dumps(after, ensure_ascii=False)
    cycle.outcome = outcome
    cycle.status = "completed"
    cycle.completed_at = _now_str()
    db.commit()
    db.refresh(cycle)
    return cycle


def check_overdue(db: Session) -> list[InterventionCycle]:
    """将超过复测日期仍未完成的闭环标记为 overdue，并返回列表。"""
    today = datetime.now().strftime("%Y-%m-%d")
    cycles = (
        db.query(InterventionCycle)
        .filter(InterventionCycle.status == "open")
        .filter(InterventionCycle.follow_up_date < today)
        .all()
    )
    for c in cycles:
        c.status = "overdue"
    db.commit()
    return cycles


def get_cycle_statistics(db: Session) -> dict:
    """
    干预闭环统计总览：
      - 闭环总数 / 完成数 / 逾期数
      - 结局分布（好转/稳定/加重）与好转率
      - 干预前 vs 干预后综合评分均值
      - 风险等级迁移矩阵（before → after）
    """
    cycles = db.query(InterventionCycle).all()
    total = len(cycles)
    if total == 0:
        return {
            "total_cycles": 0, "completed_cycles": 0, "overdue_cycles": 0,
            "outcome_distribution": {}, "improved_rate": 0.0,
            "avg_score_before": None, "avg_score_after": None,
            "risk_transition_matrix": {}, "sample_size": 0,
        }

    completed = [c for c in cycles if c.status == "completed"]
    overdue = [c for c in cycles if c.status == "overdue"]

    outcome_dist = {"improved": 0, "stable": 0, "worsened": 0}
    for c in completed:
        outcome_dist[c.outcome] = outcome_dist.get(c.outcome, 0) + 1
    improved_rate = round(outcome_dist["improved"] / len(completed) * 100, 1) if completed else 0.0

    # 干预前后综合评分均值（仅取有前后数据的闭环）
    scores_before, scores_after = [], []
    for c in completed:
        b = json.loads(c.metrics_before or "{}").get("overall_score")
        a = json.loads(c.metrics_after or "{}").get("overall_score")
        if b is not None and a is not None:
            scores_before.append(b)
            scores_after.append(a)
    avg_before = round(sum(scores_before) / len(scores_before), 3) if scores_before else None
    avg_after = round(sum(scores_after) / len(scores_after), 3) if scores_after else None

    # 风险等级迁移矩阵（before risk -> after risk 计数）
    transition = {}
    for c in completed:
        after_risk = "completed"
        b = json.loads(c.metrics_before or "{}")
        a = json.loads(c.metrics_after or "{}")
        b_level = b.get("risk_level", c.risk_level_before)
        a_level = a.get("risk_level", "")
        key = f"{b_level}→{a_level}"
        transition[key] = transition.get(key, 0) + 1

    return {
        "total_cycles": total,
        "completed_cycles": len(completed),
        "overdue_cycles": len(overdue),
        "outcome_distribution": outcome_dist,
        "improved_rate": improved_rate,
        "avg_score_before": avg_before,
        "avg_score_after": avg_after,
        "score_delta": round(avg_after - avg_before, 3) if (avg_before is not None and avg_after is not None) else None,
        "risk_transition_matrix": transition,
        "sample_size": len(completed),
    }
