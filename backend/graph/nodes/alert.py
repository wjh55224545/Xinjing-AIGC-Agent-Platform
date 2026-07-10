from __future__ import annotations
import json
from datetime import datetime, timedelta
from backend.database import SessionLocal
from backend.models.student import Student
from backend.models.alert import Alert
from backend.graph.state import OuterLoopState


def alert_node(state: OuterLoopState) -> dict:
    """
    预警节点 - 根据分析结果生成分级预警

    增强版功能：
    - 根据12项指标综合判定风险等级
    - 支持红色预警自动创建紧急干预工单
    - 详细的预警原因和建议
    """
    analysis_results = state.get("analysis_results", {})
    db = SessionLocal()
    alerts_generated: list[dict] = []
    try:
        for sid, result in analysis_results.items():
            if "error" in result:
                continue

            # 获取风险等级和评分
            risk_level = result.get("risk_level", "green")
            overall_score = result.get("overall_score", 0.5)
            risk_reason = result.get("risk_reason", "")
            attention_score = result.get("attention_score", 0.3)

            # 风险因素
            risk_factors = result.get("risk_factors", [])
            risk_factors_text = "；".join(risk_factors) if risk_factors else ""

            # 建议
            suggestions = result.get("suggestions", [])
            suggestion_texts = []
            for s in suggestions[:2]:
                if isinstance(s, dict):
                    suggestion_texts.append(s.get("content", ""))
                else:
                    suggestion_texts.append(str(s))
            suggestion_text = "；".join(suggestion_texts)

            # 情绪分布
            emotion_dist = result.get("emotion_distribution", {})
            emotion_text = ", ".join([f"{k}:{v}" for k, v in emotion_dist.items()])

            # 指标摘要
            indicators = result.get("indicators", {})

            # 获取学生信息
            student = db.query(Student).filter(Student.id == sid).first()
            student_name = student.name if student else f"学生#{sid}"

            # 渠道映射
            channel_map = {
                "green": ["看板", "APP"],
                "yellow": ["看板", "APP", "微信(班主任)"],
                "red": ["看板", "APP", "微信(班主任)", "微信(家长)", "短信", "邮件", "紧急电话"],
            }
            channels = channel_map.get(risk_level, channel_map["green"])
            channels_text = ",".join(channels)

            # 预警内容
            severity_emoji = {"green": "✅", "yellow": "⚠️", "red": "🚨"}
            emoji = severity_emoji.get(risk_level, "ℹ️")

            if risk_level == "red":
                content = (
                    f"{emoji} 【紧急预警】{student_name}：综合评分{overall_score:.2f}，"
                    f"风险因素：{risk_factors_text}。"
                    f"建议：{suggestion_text}"
                )
            elif risk_level == "yellow":
                content = (
                    f"{emoji} 【关注】{student_name}：综合评分{overall_score:.2f}，"
                    f"情绪{risk_reason}。"
                    f"建议：{suggestion_text}"
                )
            else:
                content = (
                    f"{emoji} 【正常】{student_name}：今日情绪状态稳定，"
                    f"综合评分{overall_score:.2f}，继续保持良好状态。"
                )

            # 创建预警记录
            alert = Alert(
                student_id=sid,
                severity=risk_level,
                alert_reason=risk_factors_text or risk_reason,
                risk_level=risk_level,
                risk_reason=risk_reason,
                overall_score=overall_score,
                feedback_channel=channels_text,
                feedback_content=content,
                sent_channels=json.dumps(channels),
                triggered_at=datetime.now().isoformat(),
            )

            # 红色预警设置工单截止时间
            if risk_level == "red":
                alert.work_order_status = "pending"
                alert.due_time = (datetime.now() + timedelta(hours=24)).isoformat()

            db.add(alert)
            db.flush()

            alerts_generated.append({
                "alert_id": alert.id,
                "student_id": sid,
                "severity": risk_level,
                "risk_level": risk_level,
                "risk_reason": risk_reason,
                "overall_score": overall_score,
                "student_name": student_name,
                "reason": risk_factors_text or risk_reason,
                "content": content,
                "channels": channels,
                "work_order_required": risk_level == "red",
            })

        db.commit()
        return {"alerts_generated": alerts_generated}
    except Exception as e:
        db.rollback()
        return {"error": str(e), "alerts_generated": alerts_generated}
    finally:
        db.close()
