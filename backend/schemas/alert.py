from __future__ import annotations
from pydantic import BaseModel


class AlertOut(BaseModel):
    id: int
    student_id: int
    severity: str
    alert_reason: str
    feedback_channel: str
    feedback_content: str
    is_acknowledged: int
    triggered_at: str
    acknowledged_at: str | None = None

    model_config = {"from_attributes": True}


class AlertUpdate(BaseModel):
    is_acknowledged: int = 1
