"""
AIGC API 路由
=============

提供AIGC内容生成相关的REST API端点。
包括心理报告生成、干预方案生成、家校沟通函生成等。
"""

from __future__ import annotations
import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/aigc", tags=["AIGC内容生成"])


# ---- 请求模型 ----
class DailyReportRequest(BaseModel):
    student_name: str = Field(..., description="学生姓名")
    date: str = Field(default="", description="报告日期 (YYYY-MM-DD)")
    emotion_data: dict = Field(default_factory=dict, description="当日情绪数据")
    analysis_result: dict = Field(default_factory=dict, description="心理健康分析结果")


class InterventionPlanRequest(BaseModel):
    student_name: str = Field(..., description="学生姓名")
    risk_level: str = Field(default="green", description="风险等级: green/yellow/red")
    risk_factors: list = Field(default_factory=list, description="风险因素列表")
    indicators: dict = Field(default_factory=dict, description="心理健康指标")


class ParentLetterRequest(BaseModel):
    student_name: str = Field(..., description="学生姓名")
    class_name: str = Field(default="", description="班级")
    emotion_summary: str = Field(default="", description="情绪概况")
    risk_level: str = Field(default="green", description="风险等级")
    suggestions: list = Field(default_factory=list, description="建议列表")
    teacher_name: str = Field(default="", description="班主任姓名")


class GrowthNarrativeRequest(BaseModel):
    student_name: str = Field(..., description="学生姓名")
    period_days: int = Field(default=30, ge=7, le=365, description="时间跨度(天)")
    historical_data: dict = Field(default_factory=dict, description="历史情绪数据")


class ExperimentReportRequest(BaseModel):
    student_name: str = Field(default="", description="被试姓名")
    date: str = Field(default="", description="报告日期 (YYYY-MM-DD)")
    e_params: dict = Field(default_factory=dict, description="E1-E12 前庭振动参数")
    k_value: float | None = Field(default=None, description="K 值")
    scale_data: dict = Field(default_factory=dict, description="量表数据 {SAS: {standard_score, level}}")
    experiment_title: str = Field(default="基于前庭振动技术（VibraImage）的情绪测量实验", description="实验标题")
    teacher_name: str = Field(default="", description="指导教师")


# ---- 辅助函数：从数据库自动聚合情绪数据 ----
def _auto_fetch_emotion_data(student_id: int, date: str = "") -> dict:
    """从数据库自动拉取学生情绪数据，计算指标，无需手动填写 JSON。"""
    from datetime import date as date_type, datetime
    from backend.database import SessionLocal
    from backend.models.emotion_record import EmotionRecord
    from backend.models.student import Student

    today = date or str(date_type.today())

    db = SessionLocal()
    try:
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            return {"error": f"学生 {student_id} 不存在"}

        # 拉取当天情绪记录
        records = db.query(EmotionRecord).filter(
            EmotionRecord.student_id == student_id,
            EmotionRecord.recorded_at >= f"{today}T00:00:00",
            EmotionRecord.recorded_at <= f"{today}T23:59:59",
        ).all()

        if not records:
            # 今天没记录，拉最近的
            records = db.query(EmotionRecord).filter(
                EmotionRecord.student_id == student_id,
            ).order_by(EmotionRecord.recorded_at.desc()).limit(10).all()

        if not records:
            return {"error": f"学生 {student.name} 暂无情绪记录，请先上传视频进行分析"}

        # 聚合指标
        scores = [r.fused_score for r in records]
        avg_score = sum(scores) / len(scores)
        emotions = [r.fused_emotion for r in records]
        most_common = max(set(emotions), key=emotions.count)
        facial_emotions = [r.facial_emotion for r in records]

        # 正/负性情绪占比
        positive_emotions = {"开心", "平静", "中性"}
        negative_emotions = {"悲伤", "焦虑", "愤怒", "恐惧", "厌恶"}
        pos = sum(1 for e in emotions if e in positive_emotions)
        neg = sum(1 for e in emotions if e in negative_emotions)

        # 情绪方差
        variance = sum((s - avg_score)**2 for s in scores) / len(scores) if len(scores) > 1 else 0.01

        # 趋势计算
        if len(scores) >= 2:
            trend_slope = sum((i - (len(scores)-1)/2) * (s - avg_score) for i, s in enumerate(scores)) / \
                          sum((i - (len(scores)-1)/2)**2 for i in range(len(scores)))
            trend = "改善中" if trend_slope > 0.02 else ("下降中" if trend_slope < -0.02 else "稳定")
        else:
            trend = "稳定"
            trend_slope = 0

        # 平均效价/唤醒度
        avg_valence = sum(r.fused_valence for r in records if r.fused_valence is not None) / len(records)
        avg_arousal = sum(r.fused_arousal for r in records if r.fused_arousal is not None) / len(records)

        emotion_data = {
            "fused_emotion": most_common,
            "fused_score": round(avg_score, 3),
            "fused_valence": round(avg_valence, 3),
            "fused_arousal": round(avg_arousal, 3),
        }

        indicators = {
            "emotional_stability_index": round(max(0, 1 - __import__('math').sqrt(variance) * 2), 3),
            "positive_emotion_ratio": round(pos / len(records), 2),
            "negative_emotion_ratio": round(neg / len(records), 2),
            "trend": trend,
            "trend_slope": round(trend_slope, 4),
            "emotion_fluctuation_entropy": round(min(1.0, variance * 10), 3),
            "stress_accumulation_index": round(neg / len(records) * 1.2, 3),
            "emotion_recovery_speed": round(pos / max(neg + pos, 1), 3),
            "overall_mental_health_score": round(avg_score, 3),
        }

        # 风险因素
        risk_factors = []
        if avg_score < 0.4: risk_factors.append("综合评分偏低")
        if neg / len(records) > 0.4: risk_factors.append("负面情绪占比偏高")
        if variance > 0.05: risk_factors.append("情绪波动偏大")
        if trend == "下降中": risk_factors.append("情绪呈下降趋势")

        risk_level = "red" if avg_score < 0.4 else ("yellow" if avg_score < 0.7 else "green")

        # 查找最新量表数据用于交叉验证
        from backend.models.scale_result import ScaleResult
        scale_records = db.query(ScaleResult).filter(
            ScaleResult.student_id == student_id
        ).order_by(ScaleResult.submitted_at.desc()).limit(5).all()
        scale_ref = {}
        for sr in scale_records:
            scale_ref[sr.scale_type] = {
                "standard_score": sr.standard_score,
                "level": sr.level,
                "cutoff_label": "正常" if sr.level == "normal" else (
                    "轻度" if sr.level == "mild" else ("中度" if sr.level == "moderate" else "偏重"))
            }

        return {
            "student_name": student.name,
            "scale_reference": scale_ref,  # 量表交叉验证数据
            "emotion_data": emotion_data,
            "analysis_result": {
                "overall_score": round(avg_score, 3),
                "risk_level": risk_level,
                "indicators": indicators,
                "risk_factors": risk_factors,
                "suggestions": [],
                "llm_prediction": {"trend_prediction": trend, "next_day_emotion": round(avg_score + trend_slope, 3)},
            },
            "record_count": len(records),
        }
    finally:
        db.close()


# ---- API 端点 ----
@router.post("/report/daily", summary="生成心理评估日报")
async def generate_daily_report(req: DailyReportRequest):
    """基于当日情绪数据生成结构化的心理评估日报"""
    try:
        from backend.aigc.report_generator import ReportGenerator
        gen = ReportGenerator()
        result = gen.generate(
            student_name=req.student_name,
            date=req.date,
            emotion_data=req.emotion_data,
            analysis_result=req.analysis_result,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"生成日报失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report/daily/auto", summary="自动生成心理评估日报（从DB拉数据）")
async def auto_generate_daily_report(
    student_id: int = Query(..., description="学生ID"),
    date: str = Query("", description="报告日期"),
):
    """基于数据库已有情绪记录自动生成日报，无需手动填写JSON。"""
    auto_data = _auto_fetch_emotion_data(student_id, date)
    if "error" in auto_data:
        raise HTTPException(status_code=404, detail=auto_data["error"])

    try:
        from backend.aigc.report_generator import ReportGenerator
        gen = ReportGenerator()
        result = gen.generate(
            student_name=auto_data["student_name"],
            date=date or str(__import__('datetime').date.today()),
            emotion_data=auto_data["emotion_data"],
            analysis_result=auto_data["analysis_result"],
        )
        return {
            "success": True,
            "data": {**result, "auto_fetched": True, "record_count": auto_data["record_count"]},
        }
    except Exception as e:
        logger.error(f"自动生成日报失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report/weekly", summary="生成周度趋势分析")
async def generate_weekly_report(
    student_name: str = Query(..., description="学生姓名"),
    start_date: str = Query(..., description="开始日期"),
    end_date: str = Query(..., description="结束日期"),
):
    """生成周度情绪趋势分析报告"""
    try:
        from backend.aigc.report_generator import ReportGenerator
        gen = ReportGenerator()
        result = gen.generate_weekly_trend(
            student_name=student_name,
            start_date=start_date,
            end_date=end_date,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"生成周报失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/plan/intervention", summary="生成个性化干预方案")
async def generate_intervention_plan(req: InterventionPlanRequest):
    """根据风险等级生成个性化心理干预方案"""
    try:
        from backend.aigc.plan_generator import PlanGenerator
        gen = PlanGenerator()
        result = gen.generate(
            student_name=req.student_name,
            risk_level=req.risk_level,
            risk_factors=req.risk_factors,
            indicators=req.indicators,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"生成干预方案失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/letter/parent", summary="生成家校沟通函")
async def generate_parent_letter(req: ParentLetterRequest):
    """生成家校沟通函，根据风险等级使用不同措辞"""
    try:
        from backend.aigc.letter_generator import LetterGenerator
        gen = LetterGenerator()
        result = gen.generate(
            student_name=req.student_name,
            class_name=req.class_name,
            emotion_summary=req.emotion_summary,
            risk_level=req.risk_level,
            suggestions=req.suggestions,
            teacher_name=req.teacher_name,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"生成沟通函失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/narrative/growth", summary="生成学生成长叙事")
async def generate_growth_narrative(req: GrowthNarrativeRequest):
    """基于长期情绪数据生成学生心理成长轨迹"""
    try:
        from backend.aigc.narrative_generator import NarrativeGenerator
        gen = NarrativeGenerator()
        result = gen.generate(
            student_name=req.student_name,
            period_days=req.period_days,
            historical_data=req.historical_data,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"生成成长叙事失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/report/experiment", summary="生成情绪测量实验报告（学科教学/科研版）")
async def generate_experiment_report(req: ExperimentReportRequest):
    """基于 E1-E12 前庭振动参数 + 量表数据，生成符合心理测量课程规范的实验报告。"""
    try:
        from backend.aigc.experiment_generator import ExperimentReportGenerator
        gen = ExperimentReportGenerator()
        result = gen.generate(
            student_name=req.student_name,
            date=req.date,
            e_params=req.e_params,
            k_value=req.k_value,
            scale_data=req.scale_data,
            experiment_title=req.experiment_title,
            teacher_name=req.teacher_name,
        )
        return {"success": True, "data": result}
    except Exception as e:
        logger.error(f"生成实验报告失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/report/experiment/data-readme", summary="科研数据采集说明")
async def get_experiment_data_readme():
    """返回科研数据复用说明（附在导出数据包中的 README 文本）。"""
    try:
        from backend.aigc.experiment_generator import generate_research_data_readme
        return {"success": True, "data": {"readme": generate_research_data_readme()}}
    except Exception as e:
        logger.error(f"生成数据说明失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities", summary="获取AIGC能力列表")
async def get_aigc_capabilities():
    """返回平台支持的AIGC能力清单"""
    return {
        "capabilities": [
            {
                "id": "daily_report",
                "name": "心理评估日报",
                "description": "基于全天情绪数据生成结构化自然语言评估报告",
                "endpoint": "/api/aigc/report/daily",
            },
            {
                "id": "weekly_trend",
                "name": "周度趋势分析",
                "description": "生成7天情绪趋势分析报告",
                "endpoint": "/api/aigc/report/weekly",
            },
            {
                "id": "intervention_plan",
                "name": "个性化干预方案",
                "description": "针对黄/红色预警自动生成干预计划",
                "endpoint": "/api/aigc/plan/intervention",
            },
            {
                "id": "parent_letter",
                "name": "家校沟通函",
                "description": "自动生成给家长的情绪关注建议函",
                "endpoint": "/api/aigc/letter/parent",
            },
            {
                "id": "growth_narrative",
                "name": "学生成长叙事",
                "description": "基于长期数据生成学生心理成长轨迹",
                "endpoint": "/api/aigc/narrative/growth",
            },
            {
                "id": "experiment_report",
                "name": "情绪测量实验报告",
                "description": "生成符合心理测量课程规范的实验报告（学科教学/科研版）",
                "endpoint": "/api/aigc/report/experiment",
            },
        ],
        "platform": "沐曦MetaX GPU / Gitee.AI",
        "generator": "心镜·AIGC智能体平台 v2.4.0",
    }
