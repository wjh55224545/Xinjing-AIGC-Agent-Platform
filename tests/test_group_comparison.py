"""
经典实验群体对照测试（方案三）
================================

依据：Ebert et al. (2019, Depression and Anxiety) 大学生心理风险筛查分层可行；
Han et al. (2022, Frontiers in Genetics) 多因素预警画像。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
import backend.models  # noqa: F401  注册全部模型（含 Student 关系）
from backend.services.group_comparison import record_experiment, compare_group


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestGroupComparison:
    def test_record_experiment(self, db):
        """实验记录入库"""
        rec = record_experiment(
            db, student_id=1, class_name="高一(1)班", experiment_type="stroop",
            key_metric=45.0, accuracy=95.0, detail={"interpretation": "显著"},
        )
        assert rec.id > 0
        assert rec.experiment_type == "stroop"
        assert rec.key_metric == 45.0

    def test_compare_group_class_vs_school(self, db):
        """班级 vs 全校：均值/差值/画像解释"""
        # 一班 2 人（效应量 40/50），二班 1 人（效应量 100）
        record_experiment(db, 1, "高一(1)班", "stroop", 40.0, 95.0, {})
        record_experiment(db, 2, "高一(1)班", "stroop", 50.0, 93.0, {})
        record_experiment(db, 3, "高一(2)班", "stroop", 100.0, 90.0, {})

        result = compare_group(db, "高一(1)班", "stroop")
        assert result["class_stats"]["n"] == 2
        assert result["class_stats"]["mean"] == 45.0
        assert result["school_stats"]["n"] == 3
        assert result["school_stats"]["mean"] == pytest.approx(63.333, abs=0.01)
        assert result["delta"] == pytest.approx(-18.333, abs=0.01)
        assert "Stroop" in result["interpretation"]
        assert result["metric_name"] == "Stroop 效应量 (ms)"

    def test_compare_group_sample_warning(self, db):
        """样本不足提示"""
        record_experiment(db, 1, "高三(9)班", "flanker", 30.0, 90.0, {})
        result = compare_group(db, "高三(9)班", "flanker")
        assert "样本量不足" in result["sample_warning"]

    def test_compare_group_no_data(self, db):
        """无记录时的兜底"""
        result = compare_group(db, "未知班", "iat")
        assert result["class_stats"]["n"] == 0
        assert result["class_stats"]["mean"] is None
        assert result["interpretation"] == "数据不足，暂无法生成群体画像解释。"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
