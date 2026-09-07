"""
经典心理学实验 API
==================

端点：
  - GET  /api/experiments/stroop/trials     生成 Stroop 实验试次
  - POST /api/experiments/stroop/analyze     分析 Stroop 实验数据
  - GET  /api/experiments/flanker/trials     生成 Flanker 任务试次
  - POST /api/experiments/flanker/analyze     分析 Flanker 任务数据
  - GET  /api/experiments/gonogo/trials      生成 Go/No-Go 任务试次
  - POST /api/experiments/gonogo/analyze      分析 Go/No-Go 任务数据
  - GET  /api/experiments/iat/trials         生成 IAT 试次
  - POST /api/experiments/iat/analyze         分析 IAT 实验数据
"""

from __future__ import annotations
from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend.services.classic_experiments import (
    generate_stroop_trials, analyze_stroop, STROOP_COLORS,
    generate_flanker_trials, analyze_flanker, FLANKER_DIRECTIONS,
    generate_gonogo_trials, analyze_gonogo,
    generate_iat_trials, analyze_iat,
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


# ==================== Flanker ====================


@router.get("/flanker/trials", summary="生成 Flanker 任务试次")
async def get_flanker_trials(
    n_per_condition: int = Query(20, ge=5, le=100, description="每条件试次数"),
    seed: int | None = Query(None, description="随机种子（可复现）"),
):
    trials = generate_flanker_trials(n_per_condition=n_per_condition, seed=seed)
    return {
        "success": True,
        "data": {
            "experiment_type": "flanker",
            "total_trials": len(trials),
            "directions": {"left": "←", "right": "→"},
            "trials": [
                {
                    "trial_id": t.trial_id,
                    "target": t.target,
                    "flankers": t.flankers,
                    "flanker_type": t.flanker_type,
                    "correct_answer": t.correct_answer,
                }
                for t in trials
            ],
        },
    }


class FlankerTrialInput(BaseModel):
    trial_id: str = Field(..., description="试次ID")
    flanker_type: str = Field(..., description="congruent / incongruent")
    rt: float = Field(..., gt=0, description="反应时 (ms)")
    correct: bool = Field(..., description="是否正确")


class FlankerAnalyzeRequest(BaseModel):
    trials: list[FlankerTrialInput]
    experiment_id: str | None = None


@router.post("/flanker/analyze", summary="分析 Flanker 任务数据")
async def analyze_flanker_data(req: FlankerAnalyzeRequest):
    if len(req.trials) < 4:
        return {"success": False, "error": "至少需要 4 个试次"}
    result = analyze_flanker([t.model_dump() for t in req.trials], experiment_id=req.experiment_id)
    return {
        "success": True,
        "data": {
            "experiment_id": result.experiment_id,
            "total_trials": result.total_trials,
            "congruent_rt_mean": result.congruent_rt_mean,
            "incongruent_rt_mean": result.incongruent_rt_mean,
            "flanker_effect": result.flanker_effect,
            "accuracy": result.accuracy,
            "congruent_accuracy": result.congruent_accuracy,
            "incongruent_accuracy": result.incongruent_accuracy,
            "interpretation": result.interpretation,
        },
    }


# ==================== Go/No-Go ====================


@router.get("/gonogo/trials", summary="生成 Go/No-Go 任务试次")
async def get_gonogo_trials(
    n_go: int = Query(30, ge=5, le=200, description="Go 试次数"),
    n_nogo: int = Query(10, ge=2, le=100, description="No-Go 试次数"),
    seed: int | None = Query(None, description="随机种子（可复现）"),
):
    trials = generate_gonogo_trials(n_go=n_go, n_nogo=n_nogo, seed=seed)
    return {
        "success": True,
        "data": {
            "experiment_type": "gonogo",
            "total_trials": len(trials),
            "go_stimuli": sorted(list({"B", "D", "F"})),
            "nogo_stimuli": sorted(list({"A", "C", "E"})),
            "trials": [
                {
                    "trial_id": t.trial_id,
                    "stimulus": t.stimulus,
                    "is_go": t.is_go,
                    "correct_answer": t.correct_answer,
                }
                for t in trials
            ],
        },
    }


class GoNoGoTrialInput(BaseModel):
    trial_id: str = Field(..., description="试次ID")
    is_go: bool = Field(..., description="是否 Go 试次")
    rt: float | None = Field(None, gt=0, description="反应时 (ms)，No-Go 正确抑制时为 None")
    correct: bool = Field(..., description="是否正确")


class GoNoGoAnalyzeRequest(BaseModel):
    trials: list[GoNoGoTrialInput]
    experiment_id: str | None = None


@router.post("/gonogo/analyze", summary="分析 Go/No-Go 任务数据")
async def analyze_gonogo_data(req: GoNoGoAnalyzeRequest):
    if len(req.trials) < 4:
        return {"success": False, "error": "至少需要 4 个试次"}
    result = analyze_gonogo([t.model_dump() for t in req.trials], experiment_id=req.experiment_id)
    return {
        "success": True,
        "data": {
            "experiment_id": result.experiment_id,
            "total_trials": result.total_trials,
            "go_rt_mean": result.go_rt_mean,
            "hit_rate": result.hit_rate,
            "false_alarm_rate": result.false_alarm_rate,
            "inhibition_score": result.inhibition_score,
            "accuracy": result.accuracy,
            "interpretation": result.interpretation,
        },
    }


# ==================== IAT ====================


@router.get("/iat/trials", summary="生成 IAT 试次")
async def get_iat_trials(
    n_per_block: int = Query(16, ge=4, le=50, description="每 block 试次数"),
    seed: int | None = Query(None, description="随机种子（可复现）"),
):
    trials = generate_iat_trials(n_per_block=n_per_block, seed=seed)
    return {
        "success": True,
        "data": {
            "experiment_type": "iat",
            "total_trials": len(trials),
            "categories": {"self": "自我", "other": "他人", "positive": "积极", "negative": "消极"},
            "trials": [
                {
                    "trial_id": t.trial_id,
                    "stimulus": t.stimulus,
                    "category": t.category,
                    "block_type": t.block_type,
                    "correct_answer": t.correct_answer,
                }
                for t in trials
            ],
        },
    }


class IatTrialInput(BaseModel):
    trial_id: str = Field(..., description="试次ID")
    block_type: str = Field(..., description="compatible / incompatible")
    rt: float = Field(..., gt=0, description="反应时 (ms)")
    correct: bool = Field(..., description="是否正确")


class IatAnalyzeRequest(BaseModel):
    trials: list[IatTrialInput]
    experiment_id: str | None = None


@router.post("/iat/analyze", summary="分析 IAT 实验数据")
async def analyze_iat_data(req: IatAnalyzeRequest):
    if len(req.trials) < 4:
        return {"success": False, "error": "至少需要 4 个试次"}
    result = analyze_iat([t.model_dump() for t in req.trials], experiment_id=req.experiment_id)
    return {
        "success": True,
        "data": {
            "experiment_id": result.experiment_id,
            "total_trials": result.total_trials,
            "compatible_rt_mean": result.compatible_rt_mean,
            "incompatible_rt_mean": result.incompatible_rt_mean,
            "d_score": result.d_score,
            "accuracy": result.accuracy,
            "interpretation": result.interpretation,
        },
    }
