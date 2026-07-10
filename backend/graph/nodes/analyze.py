from __future__ import annotations
import json
from datetime import date
from backend.database import SessionLocal
from backend.models.student import Student
from backend.models.daily_report import DailyReport
from backend.tools.mental_health import MentalHealthAnalysisTool
from backend.graph.state import OuterLoopState


def analyze_node(state: OuterLoopState) -> dict:
    """
    分析节点 - 执行时序心理健康分析

    增强版功能：
    - 基于LSTM-Transformer混合模型分析7天情绪时序数据
    - 计算12项心理健康指标
    - 输出风险等级及具体建议
    """
    daily_records = state.get("daily_records", {})
    target_date = state["target_date"]
    tool = MentalHealthAnalysisTool()
    db = SessionLocal()
    try:
        analysis_results: dict[int, dict] = {}
        for sid, records in daily_records.items():
            student = db.query(Student).filter(Student.id == sid).first()
            baseline = student.baseline_mood if student else 0.7

            # 执行增强版时序心理健康分析
            result = tool.execute(
                student_id=sid,
                records=records,
                baseline=baseline,
                obs_records=records,  # 包含7天历史数据
                analysis_window_days=7,
            )

            if result.success:
                data = result.data
                analysis_results[sid] = data

                # 保存每日报告
                existing = (
                    db.query(DailyReport)
                    .filter(DailyReport.student_id == sid, DailyReport.report_date == target_date)
                    .first()
                )

                # 提取12项指标
                indicators = data.get("indicators", {})
                lstm_result = data.get("lstm_transformer_analysis", {})

                # 风险等级
                risk_level = data.get("risk_level", "green")
                risk_reason = data.get("risk_reason", "")

                if not existing:
                    db.add(DailyReport(
                        student_id=sid,
                        report_date=target_date,
                        avg_emotion=data.get("avg_emotion", baseline),
                        emotion_variance=data.get("variance", 0.01),
                        trend_direction=data.get("trend", "稳定"),
                        attention_score=data.get("attention_score", 0.3),
                        summary_text=f"{student.name if student else '学生#' + str(sid)} "
                                   f"{target_date} 情绪{data.get('trend', '稳定')}，"
                                   f"风险等级:{risk_level}，综合评分:{data.get('overall_score', 0):.2f}",
                        # 新增字段
                        risk_level=risk_level,
                        risk_reason=risk_reason,
                        overall_score=data.get("overall_score", 0.5),
                        negative_emotion_ratio=data.get("negative_emotion_ratio", 0),
                        positive_emotion_ratio=data.get("positive_emotion_ratio", 0),
                        stability_index=indicators.get("emotional_stability_index", 0.7),
                        entropy=indicators.get("emotion_fluctuation_entropy", 0),
                        recovery_speed=indicators.get("emotion_recovery_speed", 0.5),
                        lstm_prediction=json.dumps(lstm_result.get("prediction", {}), ensure_ascii=False),
                        attention_risk_periods=json.dumps(lstm_result.get("transformer_attention", {}).get("attention_risk_periods", []), ensure_ascii=False),
                    ))
                else:
                    existing.avg_emotion = data.get("avg_emotion", baseline)
                    existing.emotion_variance = data.get("variance", 0.01)
                    existing.trend_direction = data.get("trend", "稳定")
                    existing.attention_score = data.get("attention_score", 0.3)
                    existing.risk_level = risk_level
                    existing.risk_reason = risk_reason
                    existing.overall_score = data.get("overall_score", 0.5)
            else:
                analysis_results[sid] = {"error": result.error}

        db.commit()
        return {"analysis_results": analysis_results}
    except Exception as e:
        db.rollback()
        return {"error": str(e)}
    finally:
        db.close()
