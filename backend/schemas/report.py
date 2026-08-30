from __future__ import annotations
from pydantic import BaseModel


class DailyReportOut(BaseModel):
    id: int
    student_id: int
    report_date: str
    avg_emotion: float
    emotion_variance: float
    trend_direction: str
    attention_score: float
    summary_text: str
    created_at: str

    model_config = {"from_attributes": True}


class DashboardSummary(BaseModel):
    total_students: int
    today_avg_emotion: float
    active_alerts: int
    green_count: int
    yellow_count: int
    red_count: int
    recent_records: list = []
    trend_data: list = []
