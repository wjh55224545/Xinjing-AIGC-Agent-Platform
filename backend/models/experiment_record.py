from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Float, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.database import Base


class ExperimentRecord(Base):
    """
    经典心理学实验记录（用于群体对照分析）。

    记录每次实验的关键指标，支持按班级聚合形成群体画像，
    与全校基准对照（个体诊断 + 群体画像，对齐大学生心理健康
    筛查文献：Ebert et al. 2019, Depression and Anxiety）。
    """
    __tablename__ = "experiment_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("students.id"), nullable=True)
    class_name: Mapped[str] = mapped_column(String(128), default="")
    experiment_type: Mapped[str] = mapped_column(String(16), nullable=False)  # stroop/flanker/gonogo/iat

    # 核心指标（各范式统一字段：数值越大含义见 detail.interpretation）
    key_metric: Mapped[float] = mapped_column(Float, default=0.0)
    accuracy: Mapped[float] = mapped_column(Float, default=0.0)

    detail: Mapped[str] = mapped_column(Text, default="{}")  # JSON 详情（含 interpretation）

    created_at: Mapped[str] = mapped_column(String(32), default=lambda: datetime.now().isoformat())

    student = relationship("Student")
