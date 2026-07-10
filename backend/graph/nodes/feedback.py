from __future__ import annotations
from backend.database import SessionLocal
from backend.models.student import Student
from backend.tools.feedback import MultiChannelFeedbackTool
from backend.graph.state import OuterLoopState


def feedback_node(state: OuterLoopState) -> dict:
    """
    反馈节点 - 执行多渠道预警通知

    增强版功能：
    - 根据风险等级动态选择反馈渠道
    - 绿色→APP；黄色→APP+班主任；红色→APP+班主任+心理教师+家长
    - 红色状态触发紧急干预工单
    """
    alerts_generated = state.get("alerts_generated", [])
    analysis_results = state.get("analysis_results", {})
    tool = MultiChannelFeedbackTool()
    feedback_sent: dict[int, dict] = {}

    db = SessionLocal()
    try:
        for alert in alerts_generated:
            student_id = alert.get("student_id")
            severity = alert.get("severity", "green")

            # 获取学生详细信息
            student = db.query(Student).filter(Student.id == student_id).first() if student_id else None

            # 构建学生信息
            student_info = {
                "student_id": student_id,
                "student_code": student.student_code if student else "unknown",
                "name": student.name if student else alert.get("student_name", "未知"),
                "class_name": student.class_name if student else "",
                "school": getattr(student, 'school', ''),
                "baseline_mood": student.baseline_mood if student else 0.7,
            }

            # 获取分析结果
            analysis = analysis_results.get(student_id, {})

            # 执行多渠道反馈
            result = tool.execute(
                alert_id=alert.get("alert_id", 0),
                severity=severity,
                student_name=student_info["name"],
                content=alert.get("content", ""),
                student_info=student_info,
                analysis_result=analysis,
            )

            feedback_sent[alert.get("alert_id", 0)] = result.data if result.success else {"error": result.error}

        return {"feedback_sent": feedback_sent}
    finally:
        db.close()
