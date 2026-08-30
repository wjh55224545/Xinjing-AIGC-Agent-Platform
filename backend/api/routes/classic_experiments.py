"""
经典心理学实验 API
==================

端点：
  - GET  /api/experiments/stroop/trials  生成 Stroop 实验试次
  - POST /api/experiments/stroop/analyze  分析 Stroop 实验数据
"""

from __future__ import annotations
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.services.classic_experiments import (
    generate_stroop_trials, analyze_stroop, STROOP_COLORS,
)

router = APIRouter(prefix="/experiments", tags=["经典心理学实验"])


@router.get("/stroop/trials", summary="生成 Stroop 实验试次")
async def get_stroop_trials(
    n_per_condition: int = Query(20, ge=5, le=100, description="每条件试次数"),
    seed: int | None = Query(None, description="随机种子（可复现）"),
):
    trials = generate_stroop_trials(n_per_condition=n_per_condition, seed=seed)
    return {
        "success": True,
        "data": {
            "experiment_type": "stroop",
            "total_trials": len(trials),
            "colors": {k: v["cn"] for k, v in STROOP_COLORS.items()},
            "trials": [
                {
                    "trial_id": t.trial_id,
                    "word": t.word,
                    "word_cn": STROOP_COLORS[t.word]["cn"],
                    "color": t.color,
                    "color_hex": STROOP_COLORS[t.color]["hex"],
                    "congruent": t.congruent,
                    "correct_answer": t.correct_answer,
                }
                for t in trials
            ],
        },
    }


class StroopTrialInput(BaseModel):
    trial_id: str = Field(..., description="试次ID")
    congruent: bool = Field(..., description="是否一致条件")
    rt: float = Field(..., gt=0, description="反应时 (ms)")
    correct: bool = Field(..., description="是否正确")


class StroopAnalyzeRequest(BaseModel):
    trials: list[StroopTrialInput]
    experiment_id: str | None = None


@router.post("/stroop/analyze", summary="分析 Stroop 实验数据")
async def analyze_stroop_data(req: StroopAnalyzeRequest):
    if len(req.trials) < 4:
        return {"success": False, "error": "至少需要 4 个试次"}
    trials_dict = [t.model_dump() for t in req.trials]
    result = analyze_stroop(trials_dict, experiment_id=req.experiment_id)
    return {
        "success": True,
        "data": {
            "experiment_id": result.experiment_id,
            "total_trials": result.total_trials,
            "congruent_rt_mean": result.congruent_rt_mean,
            "incongruent_rt_mean": result.incongruent_rt_mean,
            "stroop_effect": result.stroop_effect,
            "accuracy": result.accuracy,
            "congruent_accuracy": result.congruent_accuracy,
            "incongruent_accuracy": result.incongruent_accuracy,
            "interpretation": result.interpretation,
        },
    }
