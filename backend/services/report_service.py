from __future__ import annotations
from datetime import date
from sqlalchemy.orm import Session
from backend.models.student import Student
from backend.models.daily_report import DailyReport
from backend.tools.mental_health import MentalHealthAnalysisTool


class ReportService:
    def __init__(self, db: Session):
        self.db = db
        self.analysis_tool = MentalHealthAnalysisTool()

    def generate_daily_reports(self, target_date: str | None = None) -> list[dict]:
        target_date = target_date or str(date.today())
        students = self.db.query(Student).all()
        results = []

        from backend.models.emotion_record import EmotionRecord
        for student in students:
            records = (
                self.db.query(EmotionRecord)
                .filter(
                    EmotionRecord.student_id == student.id,
                    EmotionRecord.recorded_at >= f"{target_date}T00:00:00",
                    EmotionRecord.recorded_at <= f"{target_date}T23:59:59",
                )
                .all()
            )
            records_data = [{"fused_score": r.fused_score, "fused_emotion": r.fused_emotion} for r in records]

            result = self.analysis_tool.execute(
                student_id=student.id, records=records_data, baseline=student.baseline_mood,
            )
            if not result.success:
                continue

            report = (
                self.db.query(DailyReport)
                .filter(DailyReport.student_id == student.id, DailyReport.report_date == target_date)
                .first()
            )
            if not report:
                report = DailyReport(student_id=student.id, report_date=target_date)
                self.db.add(report)

            report.avg_emotion = result.data["avg_emotion"]
            report.emotion_variance = result.data["variance"]
            report.trend_direction = result.data["trend"]
            report.attention_score = result.data["attention_score"]
            report.summary_text = (
                f"{student.name} {target_date} 情绪{result.data['trend']}，关注度{result.data['attention_score']}"
            )
            results.append({"student_id": student.id, "report_id": report.id, **result.data})

        self.db.commit()
        return results
