from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.models.alert import Alert
from backend.schemas.alert import AlertOut, AlertUpdate

router = APIRouter(tags=["预警"])


@router.get("/alerts", response_model=list[AlertOut])
def list_alerts(severity: str | None = None, acknowledged: int | None = None,
                db: Session = Depends(get_db)):
    q = db.query(Alert).order_by(Alert.triggered_at.desc())
    if severity:
        q = q.filter(Alert.severity == severity)
    if acknowledged is not None:
        q = q.filter(Alert.is_acknowledged == acknowledged)
    return q.limit(50).all()


@router.patch("/alerts/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(alert_id: int, update: AlertUpdate = AlertUpdate(),
                      db: Session = Depends(get_db)):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="预警不存在")
    alert.is_acknowledged = update.is_acknowledged
    alert.acknowledged_at = datetime.now().isoformat()
    db.commit()
    db.refresh(alert)
    return alert


@router.get("/reports/daily")
def daily_report(student_id: int, date: str, db: Session = Depends(get_db)):
    from backend.models.daily_report import DailyReport
    report = (
        db.query(DailyReport)
        .filter(DailyReport.student_id == student_id, DailyReport.report_date == date)
        .first()
    )
    if not report:
        return {"found": False, "message": "该日期无分析报告"}
    return {
        "found": True,
        "id": report.id, "student_id": report.student_id, "report_date": report.report_date,
        "avg_emotion": report.avg_emotion, "emotion_variance": report.emotion_variance,
        "trend_direction": report.trend_direction, "attention_score": report.attention_score,
        "summary_text": report.summary_text,
    }
