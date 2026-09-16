from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Integer, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class InterventionCycle(Base):
    """
    预警-干预闭环记录。

    依据：JITAI（Just-in-Time Adaptive Intervention）设计框架
    （Nahumshani et al., 2018, Annals of Behavioral Medicine）——
    预警不是终点，而是"预警 → 干预建议 → 定时复测 → 闭环统计"的起点。
    """
    __tablename__ = "intervention_cycles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False)
    alert_id: Mapped[int] = mapped_column(Integer, ForeignKey("alerts.id"), nullable=False)

    # 干预前状态
    risk_level_before: Mapped[str] = mapped_column(String(16), nullable=False)  # green/yellow/red
    plan_text: Mapped[str] = mapped_column(Text, default="")
    metrics_before: Mapped[str] = mapped_column(Text, default="{}")  # JSON: 干预前指标快照

    # 复测计划
    follow_up_days: Mapped[int] = mapped_column(Integer, default=14)
    follow_up_date: Mapped[str] = mapped_column(String(32), default="")

    # 复测结果
    metrics_after: Mapped[str] = mapped_column(Text, default="{}")   # JSON: 复测指标快照
    outcome: Mapped[str] = mapped_column(String(16), default="")     # improved/stable/worsened
    status: Mapped[str] = mapped_column(String(16), default="open")  # open/completed/overdue

    # 时间戳
    created_at: Mapped[str] = mapped_column(String(32), default=lambda: datetime.now().isoformat())
    completed_at: Mapped[str] = mapped_column(String(32), default="")

    student = relationship("Student")
