from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Float, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    class_name: Mapped[str] = mapped_column(String(128), default="")
    student_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    baseline_mood: Mapped[float] = mapped_column(Float, default=0.7)
    created_at: Mapped[str] = mapped_column(String(32), default=lambda: datetime.now().isoformat())

    # 扩展字段（可选）
    school: Mapped[str] = mapped_column(String(256), default="")
    grade: Mapped[str] = mapped_column(String(32), default="")
    teacher_name: Mapped[str] = mapped_column(String(64), default="")  # 班主任
    parent_phone: Mapped[str] = mapped_column(String(32), default="")  # 家长电话（加密存储）
    is_active: Mapped[int] = mapped_column(Integer, default=1)

    # 关系
    emotion_records = relationship("EmotionRecord", back_populates="student", cascade="all, delete-orphan")
    daily_reports = relationship("DailyReport", back_populates="student", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="student", cascade="all, delete-orphan")
