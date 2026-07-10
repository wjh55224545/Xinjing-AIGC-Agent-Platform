from __future__ import annotations
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.api.deps import get_db
from backend.models.student import Student
from backend.models.emotion_record import EmotionRecord
from backend.models.alert import Alert
from backend.schemas.report import DashboardSummary

router = APIRouter(tags=["仪表盘"])


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(db: Session = Depends(get_db)):
    today = str(date.today())
    total_students = db.query(func.count(Student.id)).scalar() or 0

    today_avg = (
        db.query(func.avg(EmotionRecord.fused_score))
        .filter(EmotionRecord.recorded_at >= f"{today}T00:00:00")
        .scalar()
    ) or 0.0

    alert_counts = {"green": 0, "yellow": 0, "red": 0}
    alerts = db.query(Alert).filter(Alert.is_acknowledged == 0).all()
    for a in alerts:
        alert_counts[a.severity] = alert_counts.get(a.severity, 0) + 1
    active_alerts = sum(alert_counts.values())

    recent_records = (
        db.query(EmotionRecord)
        .order_by(EmotionRecord.recorded_at.desc())
        .limit(10)
        .all()
    )
    recent = [
        {"id": r.id, "student_id": r.student_id, "fused_emotion": r.fused_emotion,
         "fused_score": r.fused_score, "recorded_at": r.recorded_at}
        for r in recent_records
    ]

    trend = (
        db.query(
            func.substr(EmotionRecord.recorded_at, 1, 10).label("day"),
            func.avg(EmotionRecord.fused_score).label("avg_score"),
        )
        .group_by("day")
        .order_by("day")
        .limit(7)
        .all()
    )
    trend_data = [{"date": t.day, "avg_score": round(t.avg_score or 0, 2)} for t in trend]

    return DashboardSummary(
        total_students=total_students,
        today_avg_emotion=round(today_avg, 2),
        active_alerts=active_alerts,
        green_count=alert_counts["green"],
        yellow_count=alert_counts["yellow"],
        red_count=alert_counts["red"],
        recent_records=recent,
        trend_data=trend_data,
    )
