from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.api.deps import get_db
from backend.models.student import Student
from backend.models.emotion_record import EmotionRecord
from backend.models.alert import Alert
from backend.schemas.emotion import StudentOut, StudentDetailOut, EmotionRecordOut
from backend.schemas.alert import AlertOut

router = APIRouter(tags=["学生"])


@router.get("/students", response_model=list[StudentOut])
def list_students(db: Session = Depends(get_db)):
    return db.query(Student).all()


@router.get("/students/{student_id}", response_model=StudentDetailOut)
def get_student(student_id: int, db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="学生不存在")

    records = (
        db.query(EmotionRecord)
        .filter(EmotionRecord.student_id == student_id)
        .order_by(EmotionRecord.recorded_at.desc())
        .limit(20)
        .all()
    )
    alerts = (
        db.query(Alert)
        .filter(Alert.student_id == student_id)
        .order_by(Alert.triggered_at.desc())
        .limit(10)
        .all()
    )

    result = StudentDetailOut.model_validate(student)
    result.recent_records = [EmotionRecordOut.model_validate(r) for r in records]
    result.recent_alerts = [AlertOut.model_validate(a) for a in alerts]
    return result


@router.get("/emotions/recent", response_model=list[EmotionRecordOut])
def recent_emotions(student_id: int | None = None, limit: int = 20, db: Session = Depends(get_db)):
    q = db.query(EmotionRecord).order_by(EmotionRecord.recorded_at.desc())
    if student_id:
        q = q.filter(EmotionRecord.student_id == student_id)
    return q.limit(limit).all()


@router.get("/emotions/timeline", response_model=list[EmotionRecordOut])
def emotion_timeline(student_id: int, date: str, db: Session = Depends(get_db)):
    return (
        db.query(EmotionRecord)
        .filter(
            EmotionRecord.student_id == student_id,
            EmotionRecord.recorded_at >= f"{date}T00:00:00",
            EmotionRecord.recorded_at <= f"{date}T23:59:59",
        )
        .order_by(EmotionRecord.recorded_at)
        .all()
    )
