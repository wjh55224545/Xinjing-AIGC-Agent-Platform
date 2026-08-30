"""量表测评结果模型"""
from __future__ import annotations
from sqlalchemy import String, Float, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database import Base


class ScaleResult(Base):
    __tablename__ = "scale_results"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False)
    scale_type: Mapped[str] = mapped_column(String(16), nullable=False)  # SAS/SDS/SCL-90
    raw_score: Mapped[float] = mapped_column(Float, nullable=False)
    standard_score: Mapped[float] = mapped_column(Float, nullable=False)
    level: Mapped[str] = mapped_column(String(16), nullable=False)  # normal/mild/moderate/severe
    dimension_scores: Mapped[str] = mapped_column(String(2048), nullable=False, default="{}")  # JSON string
    answers: Mapped[str] = mapped_column(String(2048), nullable=False, default="[]")  # JSON string
    submitted_at: Mapped[str] = mapped_column(String(32), nullable=False)

    student = relationship("Student", back_populates="scale_results")
