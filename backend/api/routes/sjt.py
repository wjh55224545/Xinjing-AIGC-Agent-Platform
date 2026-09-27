"""
情境判断测验（SJT）API
=====================

端点：
  - GET  /api/sjt/questions     获取题目（不含选项分值）
  - POST /api/sjt/submit        提交作答并计分
  - POST /api/sjt/assess        对虚拟被试生成 SJT 作答并评估（合成数据）
"""

from __future__ import annotations
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.sjt import public_questions, score_sjt

router = APIRouter(prefix="/sjt", tags=["情境判断测验"])


class SjtSubmitRequest(BaseModel):
    answers: list[dict] = Field(..., description="作答列表 [{'id': 1, 'choice': 0}]，choice 为选项下标")
    student_id: int | None = Field(None, description="学生 ID（可选，用于关联）")


class SjtAssessRequest(BaseModel):
    profile_id: str = Field(..., description="虚拟被试剖面 ID")
    seed: int | None = Field(None, description="随机种子（可复现）")


@router.get("/questions", summary="获取 SJT 题库（不含分值）")
async def questions():
    return {"success": True, "data": public_questions()}


@router.post("/submit", summary="提交 SJT 作答并计分")
async def submit(req: SjtSubmitRequest):
    result = score_sjt(req.answers)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("detail", "无效作答"))
    # 关联学生（如提供）时标注来源
    if req.student_id is not None:
        result["data"]["student_id"] = req.student_id
        result["data"]["is_synthetic"] = False
    return result


@router.post("/assess", summary="对虚拟被试生成 SJT 作答并评估（合成数据）")
async def assess(req: SjtAssessRequest):
    """按剖面 θ 生成贴合其严重程度的 SJT 作答，用于演示与对照实验。"""
    import random

    from backend.services.virtual_subject import get_profile
    from backend.services.synthetic_data import generate_scale_answers, generate_e_params

    profile = get_profile(req.profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail=f"未知剖面: {req.profile_id}")

    from backend.services.sjt import _load_bank
    bank = _load_bank()
    rng = random.Random(req.seed if req.seed is not None else 42)
    theta = profile["theta"]

    # 应对倾向评分：θ 越大症状越重 → 选择积极应对的概率越低
    answers = []
    for q in bank["questions"]:
        p_good = 1.0 / (1.0 + 2.71828 ** (1.2 * theta))  # θ↑ → 积极应对概率↓
        # 各选项按 score 分层采样：score 越高被选概率越大（受 p_good 调制）
        scores = [o["score"] for o in q["options"]]
        max_s = max(scores)
        weights = []
        for s in scores:
            # 积极选项概率 ∝ p_good；消极选项概率 ∝ (1-p_good)
            w = p_good * (s / max_s) + (1 - p_good) * (1 - s / max_s)
            weights.append(max(w, 1e-3))
        choice = rng.choices(range(len(q["options"])), weights=weights, k=1)[0]
        answers.append({"id": q["id"], "choice": choice})

    result = score_sjt(answers)
    result["data"]["is_synthetic"] = True
    result["data"]["profile_id"] = profile["id"]
    result["data"]["profile_name"] = profile["name"]
    result["data"]["theta"] = theta
    return result
