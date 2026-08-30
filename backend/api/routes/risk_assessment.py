"""
焦虑抑郁风险分级筛查 API
========================

端点：
  - POST /api/risk/assess  综合风险评估（纯量表数据）
"""

from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.services.risk_assessment import assess_risk

router = APIRouter(prefix="/risk", tags=["焦虑抑郁风险筛查"])


class RiskAssessRequest(BaseModel):
    sas_score: float | None = Field(None, description="SAS 焦虑标准分")
    sds_score: float | None = Field(None, description="SDS 抑郁标准分")
    phq9_score: float | None = Field(None, description="PHQ-9 抑郁总分（0-27）")
    phq9_q9: int | None = Field(None, ge=0, le=3, description="PHQ-9 第9题得分（自杀意念）")
    gad7_score: float | None = Field(None, description="GAD-7 焦虑总分（0-21）")


@router.post("/assess", summary="焦虑抑郁综合风险分级筛查")
async def assess(req: RiskAssessRequest):
    result = assess_risk(
        sas_score=req.sas_score, sds_score=req.sds_score,
        phq9_score=req.phq9_score, phq9_q9=req.phq9_q9,
        gad7_score=req.gad7_score,
    )
    level_cn = {"low": "低风险", "medium": "中风险", "high": "高风险", "extreme": "极高风险"}
    return {
        "success": True,
        "data": {
            "overall_level": result.overall_level,
            "overall_level_cn": level_cn.get(result.overall_level, result.overall_level),
            "overall_score": result.overall_score,
            "anxiety": {"level": result.anxiety_level, "score": result.anxiety_score},
            "depression": {"level": result.depression_level, "score": result.depression_score},
            "suicide_risk": result.suicide_risk,
            "dimensions": result.dimensions,
            "recommendations": result.recommendations,
            "warning_flags": result.warning_flags,
        },
    }
