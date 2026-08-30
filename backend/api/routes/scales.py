"""
心理量表 API — 题目获取 + 自评提交 + 结果查询 + AI交叉验证 + CAT 自适应测验
========================================================================

支持量表：
  - SAS（焦虑自评，20题，4点计分，标准分=粗分×1.25）
  - SDS（抑郁自评，20题，4点计分，标准分=粗分×1.25）
  - SCL-90（症状自评，90题/10维度，5点计分，标准分=总均分×100）
  - PSS-10（知觉压力，10题，0-4计分，总分0-40）
  - PANAS（正负性情绪，20题，标准分=负性情绪维度均值×100）

计分引擎支持：
  - base=0（PSS-10）与 base=1（其余量表）两种选项起点
  - reverse_items 反向计分
  - 三种标准分公式：raw_x_125 / total_mean_x100 / raw
  - standard_score_from_dimension（PANAS 维度标准分）

CAT 自适应测验（教学演示版）：
  - POST /scales/cat/start  开启一次自适应测验
  - POST /scales/cat/next   按最大信息量法推送下一题 / 返回结果
"""

from __future__ import annotations
import os
import json
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/scales", tags=["心理量表"])

SCALES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "scales")
os.makedirs(SCALES_DIR, exist_ok=True)


# =================== 数据模型 ===================

class ScaleSubmitRequest(BaseModel):
    student_id: int = Field(..., description="学生ID")
    scale_type: str = Field(..., description="量表类型: SAS/SDS/SCL-90/PSS-10/PANAS")
    answers: list[int] = Field(..., description="答案列表（选项序号 1-N）")


class CatStartRequest(BaseModel):
    scale_type: str = Field(..., description="量表类型")


class CatAnswer(BaseModel):
    id: int = Field(..., description="条目ID")
    score: int = Field(..., description="选项序号 1-N")


class CatNextRequest(BaseModel):
    scale_type: str = Field(..., description="量表类型")
    answered: list[CatAnswer] = Field(default_factory=list, description="已答条目")


# =================== 题库与计分 ===================

def _load_scale(scale_type: str) -> dict:
    path = os.path.join(SCALES_DIR, f"{scale_type.upper()}.json")
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"量表 {scale_type} 不存在")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _score_scale(scale: dict, answers: list[int]) -> dict:
    """自动计分引擎。"""
    scoring = scale["scoring"]
    reverse_items = scoring.get("reverse_items", [])
    n = len(scale["questions"])

    if len(answers) != n:
        raise HTTPException(status_code=400, detail=f"答案数量应为 {n}，实际收到 {len(answers)}")

    base = scoring.get("base", 1)          # 选项起点：0（PSS-10）或 1（其余）
    options = scoring.get("options", [1])
    raw = 0
    for i, ans in enumerate(answers):
        qid = scale["questions"][i]["id"]
        if base == 0:
            # 0-base：前端提交 1..N，换算为选项值 0..N-1
            val = int(ans) - 1
            if qid in reverse_items:
                val = (len(options) - 1) - val
            raw += val
        else:
            val = int(ans)
            if qid in reverse_items:
                val = options[-1] + options[0] - val
            raw += val

    # ---- 标准分 ----
    formula = scoring.get("standard_score_formula", "raw")
    dim_from = scoring.get("standard_score_from_dimension")

    # 维度得分（SCL-90 / PANAS）
    dim_scores = {}
    if "dimensions" in scoring:
        for dim_name, item_ids in scoring["dimensions"].items():
            total = 0
            count = 0
            for i, ans in enumerate(answers):
                qid = scale["questions"][i]["id"]
                if base == 0:
                    a = int(ans) - 1
                    if qid in reverse_items:
                        a = (len(options) - 1) - a
                else:
                    a = int(ans)
                    if qid in reverse_items:
                        a = options[-1] + options[0] - a
                if qid in item_ids:
                    total += a
                    count += 1
            dim_scores[dim_name] = round(total / max(count, 1), 2)

    if dim_from and dim_from in dim_scores:
        std = int(round(dim_scores[dim_from] * 100))
    elif formula == "raw_x_125":
        std = int(raw * 1.25)
    elif formula == "total_mean_x100":
        std = int(round((raw / max(n, 1)) * 100))
    else:  # raw
        std = raw

    # ---- 等级 ----
    cutoff = scoring.get("cutoff", {})
    level = "normal"
    for lv in ["normal", "mild", "moderate", "severe"]:
        if lv in cutoff:
            lo, hi = cutoff[lv]
            if lo <= std <= hi:
                level = lv
                break

    return {
        "raw_score": raw,
        "standard_score": std,
        "total_mean": round(raw / max(n, 1), 2) if n else 0.0,
        "level": level,
        "dimension_scores": dim_scores,
    }


# =================== API ===================

@router.get("/{scale_type}", summary="获取量表题目")
async def get_scale(scale_type: str):
    """返回量表题目、选项标签和计分规则，前端据此渲染测验页面。"""
    scale = _load_scale(scale_type)
    return {
        "success": True,
        "data": {
            "code": scale["code"],
            "name": scale["name"],
            "description": scale["description"],
            "questions": scale["questions"],
            "options": scale["scoring"]["labels"],
            "question_count": scale["questions_count"],
        },
    }


@router.get("/list/all", summary="列出所有可用量表")
async def list_scales():
    scales = []
    for fname in sorted(os.listdir(SCALES_DIR)):
        if fname.endswith(".json"):
            path = os.path.join(SCALES_DIR, fname)
            with open(path, "r", encoding="utf-8") as f:
                s = json.load(f)
            scales.append({
                "code": s["code"], "name": s["name"],
                "description": s["description"], "question_count": s["questions_count"],
            })
    return {"success": True, "data": scales}


@router.post("/submit", summary="提交量表自评")
async def submit_scale(req: ScaleSubmitRequest):
    """提交量表自评答案，系统自动计分并存储。"""
    scale = _load_scale(req.scale_type)
    scoring = _score_scale(scale, req.answers)

    from backend.database import SessionLocal
    from backend.models.scale_result import ScaleResult

    db = SessionLocal()
    try:
        record = ScaleResult(
            student_id=req.student_id,
            scale_type=scale["code"],
            raw_score=scoring["raw_score"],
            standard_score=scoring["standard_score"],
            level=scoring["level"],
            dimension_scores=json.dumps(scoring["dimension_scores"], ensure_ascii=False),
            answers=json.dumps(req.answers),
            submitted_at=datetime.now().isoformat(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        return {
            "success": True,
            "data": {
                "id": record.id,
                "scale_type": scale["code"],
                "raw_score": scoring["raw_score"],
                "standard_score": scoring["standard_score"],
                "total_mean": scoring["total_mean"],
                "level": scoring["level"],
                "dimension_scores": scoring["dimension_scores"],
                "cutoff": scale["scoring"].get("cutoff", {}),
            },
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()


@router.get("/results/{student_id}", summary="查询学生量表结果")
async def get_results(student_id: int):
    from backend.database import SessionLocal
    from backend.models.scale_result import ScaleResult

    db = SessionLocal()
    try:
        records = db.query(ScaleResult).filter(
            ScaleResult.student_id == student_id
        ).order_by(ScaleResult.submitted_at.desc()).all()
        return {
            "success": True,
            "data": [
                {
                    "id": r.id, "scale_type": r.scale_type,
                    "standard_score": r.standard_score, "level": r.level,
                    "dimension_scores": json.loads(r.dimension_scores),
                    "submitted_at": r.submitted_at,
                }
                for r in records
            ],
        }
    finally:
        db.close()


# =================== AI 交叉验证（含统计检验） ===================

@router.get("/crosscheck/{student_id}", summary="量表与AI情绪交叉验证")
async def crosscheck(student_id: int):
    """将量表结果与AI情绪数据对比，输出一致性报告（含统计检验指标）。"""
    from backend.database import SessionLocal
    from backend.models.scale_result import ScaleResult
    from backend.models.emotion_record import EmotionRecord
    from backend.services.scale_stats import cohen_kappa, binary_metrics

    db = SessionLocal()
    try:
        scale_records = db.query(ScaleResult).filter(
            ScaleResult.student_id == student_id
        ).order_by(ScaleResult.submitted_at.desc()).limit(3).all()

        emotion_records = db.query(EmotionRecord).filter(
            EmotionRecord.student_id == student_id
        ).order_by(EmotionRecord.recorded_at.desc()).limit(30).all()

        if not emotion_records:
            return {"success": False, "detail": "该学生暂无AI情绪数据"}

        avg_score = sum(r.fused_score for r in emotion_records) / len(emotion_records)
        neg_ratio = sum(1 for r in emotion_records if r.fused_emotion in {"悲伤", "焦虑", "愤怒", "恐惧"}) / len(emotion_records)
        ai_high_risk = avg_score < 0.4 and neg_ratio > 0.5

        checks = []
        actuals, preds = [], []
        for sr in scale_records:
            scale_high = sr.standard_score >= 60
            ai_severe = avg_score < 0.4 and neg_ratio > 0.5
            actuals.append(scale_high)
            preds.append(ai_severe)
            checks.append({
                "scale": sr.scale_type,
                "scale_score": sr.standard_score,
                "scale_level": sr.level,
                "ai_avg_score": round(avg_score, 2),
                "ai_negative_ratio": round(neg_ratio, 2),
                "consistent": scale_high == ai_severe,
                "detail": "量表与AI一致：均提示高风险" if (scale_high and ai_severe) else
                          "量表与AI一致：均正常" if (not scale_high and not ai_severe) else
                          "量表与AI不一致：建议复核",
            })

        return {
            "success": True,
            "data": {
                "checks": checks,
                "ai_summary": {"avg_score": round(avg_score, 2), "negative_ratio": round(neg_ratio, 2)},
                "statistics": {
                    "kappa": cohen_kappa(actuals, preds),
                    "metrics": binary_metrics(actuals, preds),
                    "sample_size": len(checks),
                },
            },
        }
    finally:
        db.close()


@router.get("/validation/summary", summary="全库量表×AI 效度统计检验")
async def validation_summary():
    """
    对全体有「量表记录 + AI情绪记录」的学生，计算量表与 AI 的一致性统计：
    Pearson r（量表标准分 vs AI 平均分）、Cohen's Kappa、灵敏度/特异度。
    用于「量表为 AI 评估提供效度基准」的量化证据。
    """
    from backend.database import SessionLocal
    from backend.models.student import Student
    from backend.models.scale_result import ScaleResult
    from backend.models.emotion_record import EmotionRecord
    from backend.services.scale_stats import pearson_r, cohen_kappa, binary_metrics

    db = SessionLocal()
    try:
        students = db.query(Student).all()
        xs, ys = [], []          # 量表标准分 vs AI 平均分
        actuals, preds = [], []  # 高风险二值
        paired = 0
        for stu in students:
            scales = db.query(ScaleResult).filter(ScaleResult.student_id == stu.id).all()
            emotions = db.query(EmotionRecord).filter(EmotionRecord.student_id == stu.id).all()
            if not scales or not emotions:
                continue
            avg_ai = sum(r.fused_score for r in emotions) / len(emotions)
            neg_ratio = sum(1 for r in emotions if r.fused_emotion in {"悲伤", "焦虑", "愤怒", "恐惧"}) / len(emotions)
            ai_high = avg_ai < 0.4 and neg_ratio > 0.5
            for s in scales:
                if s.scale_type not in {"SAS", "SDS"}:
                    continue
                paired += 1
                xs.append(s.standard_score)
                ys.append(round(avg_ai, 3))
                actuals.append(s.standard_score >= 60)
                preds.append(ai_high)

        return {
            "success": True,
            "data": {
                "sample_size": paired,
                "pearson_r": pearson_r(xs, ys),
                "kappa": cohen_kappa(actuals, preds),
                "metrics": binary_metrics(actuals, preds),
                "note": "基于系统内真实量表与AI情绪记录计算；样本不足时指标为 0 属正常，随试点数据增长而充实。",
            },
        }
    finally:
        db.close()


@router.get("/validation/reliability", summary="合成数据信效度套件（升级新增）")
async def validation_reliability(n_subjects: int = 200, seed: int = 42):
    """
    在**合成被试**（非真实学生数据）上运行量表信效度检验套件：
      - 内部一致性：Cronbach α / 条目间平均相关（SAS/SDS/PSS-10/PANAS）
      - 结构效度：SCL-90 十维度相关矩阵（同维度聚类、不同维度区分）
    用于在无真实试点数据阶段，演示"心理测量学规范"的可执行证据链。
    ⚠️ 结果一律标记 is_synthetic=True，不冒充真实样本。
    """
    from backend.services.synthetic_data import generate_subjects
    from backend.services.scale_stats import cronbach_alpha, inter_item_correlation

    n = max(50, min(int(n_subjects), 2000))
    subjects = generate_subjects(n, seed=seed)

    result = {"is_synthetic": True, "n_subjects": len(subjects), "scales": {}}
    for code in ["SAS", "SDS", "PSS-10", "PANAS"]:
        matrix = [s["scale_answers"][code] for s in subjects]
        result["scales"][code] = {
            "cronbach_alpha": cronbach_alpha(matrix),
            "inter_item_correlation": inter_item_correlation(matrix),
        }

    # SCL-90 结构效度（十维度相关矩阵，按真实计分引擎算维度分）
    scl = _load_scale("SCL-90")
    dim_scores = [_score_scale(scl, s["scale_answers"]["SCL-90"])["dimension_scores"] for s in subjects]
    from backend.services.scale_stats import dimension_correlation_matrix
    matrix_scl = dimension_correlation_matrix(dim_scores)
    # 简化为平均相关汇总（避免响应过大）
    dims = list(matrix_scl.keys())
    avg_corr = {}
    for d in dims:
        vals = [matrix_scl[d][o] for o in dims if o != d]
        avg_corr[d] = round(sum(vals) / len(vals), 4) if vals else 0.0
    result["scales"]["SCL-90"] = {
        "dimensions": dims,
        "mean_inter_dimension_correlation": avg_corr,
    }

    result["note"] = "合成数据仅用于方法验证与教学演示，与真实样本严格隔离（is_synthetic=True）。"
    return {"success": True, "data": result}


# =================== CAT 自适应测验 ===================

@router.post("/cat/start", summary="开启 CAT 自适应测验")
async def cat_start(req: CatStartRequest):
    """初始化一次 CAT 会话，返回第一题。"""
    from backend.services import cat as cat_engine

    scale = _load_scale(req.scale_type)
    scoring = scale["scoring"]
    reverse_items = scoring.get("reverse_items", [])
    n_levels = len(scoring.get("options", [1, 2, 3, 4]))
    first = cat_engine.next_item(
        scale["questions"], [], reverse_items, theta=0.0,
        max_items=cat_engine._default_max(scale["questions"]),
        model="grm", n_levels=n_levels,
    )
    return {
        "success": True,
        "data": {
            "scale_type": scale["code"],
            "name": scale["name"],
            "options": scoring["labels"],
            "question_count": scale["questions_count"],
            "model": first["model"],
            "question": first["next"],
            "session": {
                "answered_count": 0,
                "max_items": first["max_items"],
                "theta": 0.0,
                "se": 1.0,
            },
        },
    }


@router.post("/cat/next", summary="CAT 推题 / 出结果")
async def cat_next(req: CatNextRequest):
    """依据已答条目推送下一题；满足终止条件时返回评估结果。"""
    from backend.services import cat as cat_engine

    scale = _load_scale(req.scale_type)
    scoring = scale["scoring"]
    reverse_items = scoring.get("reverse_items", [])
    n_levels = len(scoring.get("options", [1, 2, 3, 4]))
    answered = [{"id": a.id, "score": a.score} for a in req.answered]

    res = cat_engine.next_item(
        scale["questions"], answered, reverse_items,
        theta=0.0, max_items=cat_engine._default_max(scale["questions"]),
        model="grm", n_levels=n_levels,
    )

    payload = {
        "success": True,
        "data": {
            "scale_type": scale["code"],
            "done": res["done"],
            "question": res["next"],
            "session": {
                "answered_count": res["answered_count"],
                "max_items": res["max_items"],
                "theta": res["theta"],
                "se": res["se"],
            },
            "score_estimate": res["score_estimate"],
        },
    }
    if res["done"]:
        payload["data"]["result"] = _cat_final_result(scale, res)
    return payload


def _cat_final_result(scale: dict, res: dict) -> dict:
    """CAT 结束时的结果说明（教学演示用简化映射）。"""
    idx = res["score_estimate"]["theta_index"]
    level = res["score_estimate"]["level"]
    return {
        "theta": res["theta"],
        "se": res["se"],
        "theta_index": idx,
        "level": level,
        "note": (
            "本结果为 CAT 简化教学演示的能力估计（θ 映射 0-100），"
            "正式测评请以全量表标准计分为准。"
        ),
    }
