"""
情绪预测与异常检测 API
======================

端点：
  - POST /api/emotion/forecast  提交历史情绪时序，返回预测 + 异常检测
"""

from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.emotion_forecast import analyze_emotion_series

router = APIRouter(prefix="/emotion", tags=["情绪预测与异常检测"])


class ForecastRequest(BaseModel):
    series: list[float] = Field(..., description="历史情绪得分时序（按时间顺序，值∈[0,1]，越高越积极）")
    steps: int = Field(5, ge=1, le=30, description="预测未来步数")


@router.post("/forecast", summary="情绪趋势预测 + 异常检测")
async def forecast(req: ForecastRequest):
    if len(req.series) < 3:
        raise HTTPException(status_code=400, detail="历史时序至少需要 3 个数据点")
    # 校验值范围
    for v in req.series:
        if not (0.0 <= v <= 1.0):
            raise HTTPException(status_code=400, detail=f"情绪得分应在 [0,1] 范围内，收到 {v}")
    result = analyze_emotion_series(req.series, forecast_steps=req.steps)
    return {"success": True, "data": result}
