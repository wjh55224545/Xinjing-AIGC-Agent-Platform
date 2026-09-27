"""
个体多维心理画像 API
====================

端点：
  - GET  /api/psychological-profile/{student_id}   真实学生画像（量表+AI情绪+预警）
  - POST /api/psychological-profile/virtual         虚拟被试画像（全合成）
"""

from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.psychological_profile import build_student_profile, build_virtual_profile

router = APIRouter(prefix="/psychological-profile", tags=["个体多维心理画像"])


class VirtualProfileRequest(BaseModel):
    profile_id: str = Field(..., description="虚拟被试剖面 ID")
    seed: int | None = Field(None, description="随机种子（可复现）")


@router.get("/{student_id}", summary="真实学生多维心理画像")
async def student_profile(student_id: int):
    result = build_student_profile(student_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("detail", "画像生成失败"))
    return result


@router.post("/virtual", summary="虚拟被试多维心理画像（合成数据）")
async def virtual_profile(req: VirtualProfileRequest):
    result = build_virtual_profile(req.profile_id, seed=req.seed)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("detail", "未知剖面"))
    return result
