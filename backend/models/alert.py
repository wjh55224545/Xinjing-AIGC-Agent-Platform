from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, ForeignKey, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False)
    severity: Mapped[str] = mapped_column(String(8), nullable=False)  # green/yellow/red
    alert_reason: Mapped[str] = mapped_column(String(512), nullable=False)

    # 预警详情
    risk_level: Mapped[str] = mapped_column(String(16), nullable=False)
    risk_reason: Mapped[str] = mapped_column(String(512), default="")
    overall_score: Mapped[float] = mapped_column(Float, default=0.5)

    # 反馈信息
    feedback_channel: Mapped[str] = mapped_column(String(256), nullable=False)
    feedback_content: Mapped[str] = mapped_column(String(1024), nullable=False)
    sent_channels: Mapped[str] = mapped_column(String(512), default="")  # JSON格式存储发送的渠道列表

    # 紧急工单（红色预警）
    work_order_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    work_order_status: Mapped[str] = mapped_column(String(32), default="pending")
    due_time: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    # 确认状态
    is_acknowledged: Mapped[int] = mapped_column(Integer, default=0)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    acknowledged_at: Mapped[Optional[str]] = mapped_column(String(32), default=None, nullable=True)

    # 时间戳
    triggered_at: Mapped[str] = mapped_column(String(32), default=lambda: datetime.now().isoformat())
    created_at: Mapped[str] = mapped_column(String(32), default=lambda: datetime.now().isoformat())

    student = relationship("Student", back_populates="alerts")
