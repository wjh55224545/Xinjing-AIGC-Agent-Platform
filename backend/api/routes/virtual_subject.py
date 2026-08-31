"""
虚拟被试合成数据 API
====================

端点：
  - GET  /api/virtual-subjects/profiles          剖面列表
  - POST /api/virtual-subjects/generate          生成一名虚拟被试（隐藏真值）
  - POST /api/virtual-subjects/auto-diagnose     系统自动诊断（量表计分+情绪判定+风险分级，与真值对照）
  - POST /api/virtual-subjects/grade             诊断对比批改（评估诊断算法准确性）
"""

from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.virtual_subject import (
    PROFILES, generate_virtual_subject, student_view, grade_diagnosis, auto_diagnose,
)

router = APIRouter(prefix="/virtual-subjects", tags=["虚拟被试合成数据"])


class GenerateRequest(BaseModel):
    profile_id: str = Field(..., description="剖面 ID，如 healthy_control / mild_anxiety")
    seed: int | None = Field(None, description="随机种子（固定可复现）")


class GradeRequest(BaseModel):
    subject_id: str = Field(..., description="虚拟被试 ID（由 generate 返回）")
    level_judgment: str = Field(..., description="量表等级判断：normal/mild/moderate/severe")
    emotion_judgment: str = Field(..., description="情绪判断：positive/neutral/mild_negative/severe_negative")
    suggestion: str = Field(..., description="干预建议文本")


class AutoDiagnoseRequest(BaseModel):
    subject_id: str = Field(..., description="虚拟被试 ID（由 generate 返回）")


# 内存缓存：generate 生成的被试（自动诊断/批改时按 subject_id 取回真值）
_SUBJECT_CACHE: dict[str, dict] = {}


@router.get("/profiles", summary="虚拟被试剖面列表")
async def list_profiles():
    return {
        "success": True,
        "data": [
            {
                "id": p["id"],
                "name": p["name"],
                "description": p["description"],
                "theta": p["theta"],
                "dominant_scale": p["dominant_scale"],
                "teaching_note": p["teaching_note"],
            }
            for p in PROFILES
        ],
    }


@router.post("/generate", summary="生成一名虚拟被试（隐藏真值）")
async def generate(req: GenerateRequest):
    subject = generate_virtual_subject(req.profile_id, seed=req.seed)
    _SUBJECT_CACHE[subject["subject_id"]] = subject
    return {"success": True, "data": student_view(subject)}


@router.post("/auto-diagnose", summary="系统自动诊断虚拟被试")
async def diagnose(req: AutoDiagnoseRequest):
    subject = _SUBJECT_CACHE.get(req.subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail=f"虚拟被试不存在或已过期: {req.subject_id}")
    result = auto_diagnose(subject)
    return {"success": True, "data": result}


@router.post("/grade", summary="诊断对比批改（评估诊断准确性）")
async def grade(req: GradeRequest):
    subject = _SUBJECT_CACHE.get(req.subject_id)
    if subject is None:
        raise HTTPException(status_code=404, detail=f"虚拟被试不存在或已过期: {req.subject_id}")
    result = grade_diagnosis(subject, {
        "level_judgment": req.level_judgment,
        "emotion_judgment": req.emotion_judgment,
        "suggestion": req.suggestion,
    })
    return {"success": True, "data": result}
