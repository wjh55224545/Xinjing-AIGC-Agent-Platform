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
        ],
        "platform": "沐曦MetaX GPU / Gitee.AI",
        "generator": "心镜·AIGC智能体平台 v2.0",
    }
