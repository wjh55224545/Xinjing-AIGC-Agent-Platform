"""
预警-干预闭环统计测试（方案二）
================================

依据：JITAI 即时自适应干预（Nahumshani et al., 2018; Bidargaddi et al., 2020;
Marciniak et al., 2020）。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base
import backend.models  # noqa: F401  注册全部模型（含 Student/Alert 关系）
from backend.services import intervention_cycle as svc


@pytest.fixture()
def db():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


class TestInterventionCycle:
    def test_create_cycle(self, db):
        """创建闭环：状态 open、复测日期 = 今天+14天"""
        cycle = svc.create_cycle(
            db, student_id=1, alert_id=1, risk_level_before="yellow",
            plan_text="建议正念练习", metrics_before={"overall_score": 0.55},
        )
        assert cycle.id > 0
        assert cycle.status == "open"
        assert cycle.risk_level_before == "yellow"
        assert cycle.follow_up_days == 14
        assert cycle.follow_up_date > cycle.created_at[:10]

    def test_complete_cycle_improved(self, db):
        """复测后评分上升 ≥0.05 → improved"""
        cycle = svc.create_cycle(
            db, student_id=1, alert_id=1, risk_level_before="yellow",
            metrics_before={"overall_score": 0.55},
        )
        done = svc.complete_cycle(
            db, cycle.id, metrics_after={"overall_score": 0.66, "risk_level": "green"},
        )
        assert done is not None
        assert done.outcome == "improved"
        assert done.status == "completed"
        assert done.completed_at != ""

    def test_complete_cycle_worsened(self, db):
        """复测后评分下降 → worsened"""
        cycle = svc.create_cycle(
            db, student_id=2, alert_id=2, risk_level_before="green",
            metrics_before={"overall_score": 0.75},
        )
        done = svc.complete_cycle(db, cycle.id, metrics_after={"overall_score": 0.60})
        assert done.outcome == "worsened"

    def test_complete_cycle_stable(self, db):
        """复测后评分基本不变 → stable"""
        cycle = svc.create_cycle(
            db, student_id=3, alert_id=3, risk_level_before="yellow",
            metrics_before={"overall_score": 0.55},
        )
        done = svc.complete_cycle(db, cycle.id, metrics_after={"overall_score": 0.57})
        assert done.outcome == "stable"

    def test_check_overdue(self, db):
        """复测日期早于今天且未完成 → 标记 overdue"""
        cycle = svc.create_cycle(
            db, student_id=4, alert_id=4, risk_level_before="yellow",
            metrics_before={"overall_score": 0.5},
        )
        cycle.follow_up_date = "2020-01-01"  # 手动制造逾期
        db.commit()
        overdue = svc.check_overdue(db)
        assert any(c.id == cycle.id for c in overdue)
        db.refresh(cycle)
        assert cycle.status == "overdue"

    def test_statistics_aggregation(self, db):
        """闭环统计：总数/完成/好转率/前后均值/风险迁移"""
        c1 = svc.create_cycle(db, 1, 1, "yellow", metrics_before={"overall_score": 0.5})
        svc.complete_cycle(db, c1.id, metrics_after={"overall_score": 0.65, "risk_level": "green"})
        c2 = svc.create_cycle(db, 2, 2, "yellow", metrics_before={"overall_score": 0.5})
        svc.complete_cycle(db, c2.id, metrics_after={"overall_score": 0.52, "risk_level": "yellow"})

        stats = svc.get_cycle_statistics(db)
        assert stats["total_cycles"] == 2
        assert stats["completed_cycles"] == 2
        assert stats["outcome_distribution"]["improved"] == 1
        assert stats["outcome_distribution"]["stable"] == 1
        assert stats["improved_rate"] == 50.0
        assert stats["avg_score_before"] == 0.5
        assert stats["avg_score_after"] == 0.585
        assert "yellow→green" in stats["risk_transition_matrix"]
        assert "yellow→yellow" in stats["risk_transition_matrix"]

    def test_statistics_empty(self, db):
        """无闭环时统计为空结构"""
        stats = svc.get_cycle_statistics(db)
        assert stats["total_cycles"] == 0
        assert stats["improved_rate"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
