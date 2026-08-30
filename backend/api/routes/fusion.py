"""
多模态情绪融合 API（Dempster-Shafer 证据融合）
==============================================

升级项 B1：从「面部+前庭固定权重」升级为「面部+前庭+量表/CAT 三模态 D-S 融合」，
输出合成 mass、冲突系数、置信度与分歧解释。

端点：
  - POST /fusion/three-modal  三模态融合
  - POST /fusion/two-modal    双模态 D-S 融合（兼容旧对比）
"""

from __future__ import annotations
from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/fusion", tags=["多模态融合"])


class VAInput(BaseModel):
    valence: float = Field(0.0, description="效价，[-1,1]，正值=积极")
    arousal: float = Field(0.0, description="唤醒度，[-1,1]")
    confidence: float = Field(0.6, description="该模态置信度，[0,1]")


class ScaleInput(BaseModel):
    theta: float = Field(0.0, description="量表/CAT 能力估计 θ，[-3,3]")
    confidence: float = Field(0.6, description="量表置信度，[0,1]")


class ThreeModalRequest(BaseModel):
    facial: VAInput | None = None
    vestibular: VAInput | None = None
    scale: ScaleInput | None = None


class TwoModalRequest(BaseModel):
    facial: VAInput | None = None
    vestibular: VAInput | None = None


@router.post("/three-modal", summary="三模态 D-S 融合（面部+前庭+量表/CAT）")
async def three_modal_fusion(req: ThreeModalRequest):
    """将面部、前庭、量表三类证据用 Dempster-Shafer 规则融合，
    输出融合情绪、得分、置信度、冲突系数与分歧解释。"""
    from backend.services.fusion import fuse_three_modal

    facial = req.facial.model_dump() if req.facial else None
    vestibular = req.vestibular.model_dump() if req.vestibular else None
    scale = req.scale.model_dump() if req.scale else None
    result = fuse_three_modal(facial=facial, vestibular=vestibular, scale=scale)
    return {"success": True, "data": result}


@router.post("/two-modal", summary="双模态 D-S 融合（面部+前庭）")
async def two_modal_fusion(req: TwoModalRequest):
    """双模态 D-S 融合（用于与三模态做消融对比）。"""
    from backend.services.fusion import fuse_two_modal

    facial = req.facial.model_dump() if req.facial else None
    vestibular = req.vestibular.model_dump() if req.vestibular else None
    result = fuse_two_modal(facial=facial, vestibular=vestibular)
    return {"success": True, "data": result}
