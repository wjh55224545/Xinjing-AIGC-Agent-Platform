from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Float, Integer, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class DailyReport(Base):
    __tablename__ = "daily_reports"
    __table_args__ = (UniqueConstraint("student_id", "report_date"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False)
    report_date: Mapped[str] = mapped_column(String(16), nullable=False)

    # 基础情绪统计
    avg_emotion: Mapped[float] = mapped_column(Float, nullable=False)
    emotion_variance: Mapped[float] = mapped_column(Float, nullable=False)
    trend_direction: Mapped[str] = mapped_column(String(16), nullable=False)
    attention_score: Mapped[float] = mapped_column(Float, default=0.0)

    # 风险评估
    risk_level: Mapped[str] = mapped_column(String(16), default="green")  # green/yellow/red
    risk_reason: Mapped[str] = mapped_column(String(512), default="")
    overall_score: Mapped[float] = mapped_column(Float, default=0.5)  # 综合心理健康评分

    # 情绪分布
    negative_emotion_ratio: Mapped[float] = mapped_column(Float, default=0.0)
    positive_emotion_ratio: Mapped[float] = mapped_column(Float, default=0.5)

    # 12项指标（部分关键指标）
    stability_index: Mapped[float] = mapped_column(Float, default=0.7)  # 情绪稳定性指数
    entropy: Mapped[float] = mapped_column(Float, default=0.5)  # 情绪波动熵值
    recovery_speed: Mapped[float] = mapped_column(Float, default=0.5)  # 情绪恢复速度

    # LSTM-Transformer分析结果（JSON格式）
    lstm_prediction: Mapped[str] = mapped_column(String(1024), default="{}")
    attention_risk_periods: Mapped[str] = mapped_column(String(1024), default="[]")

    # 汇总文本
    summary_text: Mapped[str] = mapped_column(String(1024), default="")
    created_at: Mapped[str] = mapped_column(String(32), default=lambda: datetime.now().isoformat())

    student = relationship("Student", back_populates="daily_reports")
