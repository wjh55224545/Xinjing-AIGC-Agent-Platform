from __future__ import annotations
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models.alert import Alert
from backend.tools.feedback import MultiChannelFeedbackTool


class AlertService:
    def __init__(self, db: Session):
        self.db = db
        self.feedback_tool = MultiChannelFeedbackTool()

    def triage_and_alert(self, analysis_results: dict[int, dict], student_map: dict[int, str]) -> list[dict]:
        alerts = []
        for sid, result in analysis_results.items():
            if "error" in result:
                continue
            score = result.get("attention_score", 0.0)
            severity = "green" if score < 0.3 else ("yellow" if score < 0.7 else "red")
            student_name = student_map.get(sid, f"学生#{sid}")
            reason = "情绪状态正常" if severity == "green" else f"情绪波动异常，关注度{score}"
            channels = {"green": "看板", "yellow": "看板,微信", "red": "看板,微信,邮件,短信"}[severity]
            content = f"[{severity.upper()}] {student_name}: {reason}"

            alert = Alert(
                student_id=sid, severity=severity, alert_reason=reason,
                feedback_channel=channels, feedback_content=content,
                triggered_at=datetime.now().isoformat(),
            )
            self.db.add(alert)
            self.db.flush()

            fb_result = self.feedback_tool.execute(
                alert_id=alert.id, severity=severity, student_name=student_name, content=content,
            )
            alerts.append({"alert_id": alert.id, "student_id": sid, "severity": severity,
                           "feedback": fb_result.data if fb_result.success else {}})

        self.db.commit()
        return alerts
