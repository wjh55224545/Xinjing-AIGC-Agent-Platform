"""
预警-干预闭环 API
=================

端点：
  - POST   /api/intervention/cycles          为已有预警创建干预闭环
  - POST   /api/intervention/cycles/{id}/complete   复测完成，记录后测指标
  - GET    /api/intervention/cycles/statistics       闭环统计总览
  - GET    /api/intervention/cycles           闭环列表
  - POST   /api/intervention/cycles/check-overdue    检查并标记逾期闭环
"""

from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.models.intervention_cycle import InterventionCycle
from backend.services import intervention_cycle as cycle_svc

router = APIRouter(prefix="/intervention", tags=["预警-干预闭环"])


class CycleCreateRequest(BaseModel):
    student_id: int = Field(..., description="学生ID")
    alert_id: int = Field(..., description="预警ID")
    risk_level_before: str = Field("yellow", description="干预前风险等级 green/yellow/red")
    plan_text: str = Field("", description="干预建议文本")
    metrics_before: dict | None = Field(None, description="干预前指标快照")
    follow_up_days: int = Field(14, ge=7, le=90, description="复测间隔天数")


class CycleCompleteRequest(BaseModel):
    metrics_after: dict | None = Field(None, description="复测指标快照")


@router.post("/cycles", summary="创建干预闭环")
def create_cycle(req: CycleCreateRequest, db: Session = Depends(get_db)):
    cycle = cycle_svc.create_cycle(
        db, student_id=req.student_id, alert_id=req.alert_id,
        risk_level_before=req.risk_level_before, plan_text=req.plan_text,
        metrics_before=req.metrics_before, follow_up_days=req.follow_up_days,
    )
    return {
        "success": True,
        "data": {
            "id": cycle.id, "student_id": cycle.student_id, "alert_id": cycle.alert_id,
            "risk_level_before": cycle.risk_level_before,
            "follow_up_date": cycle.follow_up_date, "status": cycle.status,
        },
    }


@router.post("/cycles/{cycle_id}/complete", summary="复测完成并记录后测")
def complete_cycle(cycle_id: int, req: CycleCompleteRequest, db: Session = Depends(get_db)):
    cycle = cycle_svc.complete_cycle(db, cycle_id, metrics_after=req.metrics_after)
    if not cycle:
        raise HTTPException(status_code=404, detail="闭环不存在")
    return {
        "success": True,
        "data": {
            "id": cycle.id, "outcome": cycle.outcome, "status": cycle.status,
            "completed_at": cycle.completed_at,
        },
    }


@router.get("/cycles/statistics", summary="干预闭环统计总览")
def cycle_statistics(db: Session = Depends(get_db)):
    return {"success": True, "data": cycle_svc.get_cycle_statistics(db)}


@router.get("/cycles", summary="干预闭环列表")
def list_cycles(status: str | None = None, db: Session = Depends(get_db)):
    q = db.query(InterventionCycle).order_by(InterventionCycle.created_at.desc())
    if status:
        q = q.filter(InterventionCycle.status == status)
    cycles = q.limit(100).all()
    return {
        "success": True,
        "data": [
            {
                "id": c.id, "student_id": c.student_id, "alert_id": c.alert_id,
                "risk_level_before": c.risk_level_before, "outcome": c.outcome,
                "status": c.status, "follow_up_date": c.follow_up_date,
                "created_at": c.created_at, "completed_at": c.completed_at,
            }
            for c in cycles
        ],
    }


@router.post("/cycles/check-overdue", summary="检查并标记逾期闭环")
def check_overdue(db: Session = Depends(get_db)):
    overdue = cycle_svc.check_overdue(db)
    return {
        "success": True,
        "data": {"overdue_count": len(overdue),
                 "overdue_ids": [c.id for c in overdue]},
    }
