"""
经典实验群体对照服务
====================

把单被试的经典实验（Stroop/Flanker/Go-NoGo/IAT）结果聚合为群体画像，
与全校基准对照，输出"个体诊断 + 群体画像"双价值。

依据：
  - Ebert et al. (2019). Prediction of major depressive disorder onset in college
    students. Depression and Anxiety.（入学筛查分层可行：入校筛查 AUC=0.73，
    10% 最高危学生覆盖 36% 新发病例——支持群体分层观察）
  - Han et al. (2022). College students' screening early warning factors in
    identification of suicide risk. Frontiers in Genetics.（预警因素随机森林
    AUC=0.947——支持多因素群体画像）

指标语义：
  - stroop_effect / flanker_effect：不一致-一致反应时差，越大认知干扰越强
  - gonogo false_alarm_rate：虚报率，越高反应抑制越弱、冲动性越高
  - iat d_score：负值提示消极自我内隐联结
"""

from __future__ import annotations
import json
import statistics
from sqlalchemy.orm import Session

from backend.models.experiment_record import ExperimentRecord

# 各范式关键指标字段名（key_metric 的语义）
METRIC_NAMES = {
    "stroop": "Stroop 效应量 (ms)",
    "flanker": "Flanker 干扰效应量 (ms)",
    "gonogo": "虚报率 (%)",
    "iat": "IAT D 分数",
}

# 指标方向：越大越"需要关注"为 True
METRIC_HIGHER_IS_RISK = {
    "stroop": True, "flanker": True, "gonogo": True, "iat": False,
}

# 最小有效样本量（低于该值提示样本不足）
MIN_SAMPLE = 3


def record_experiment(
    db: Session,
    student_id: int | None = None,
    class_name: str = "",
    experiment_type: str = "",
    key_metric: float = 0.0,
    accuracy: float = 0.0,
    detail: dict | None = None,
) -> ExperimentRecord:
    """保存一次实验记录（供群体对照聚合，student_id 可空，仅按班级聚合）。"""
    rec = ExperimentRecord(
        student_id=student_id,
        class_name=class_name or "",
        experiment_type=experiment_type,
        key_metric=round(float(key_metric), 3),
        accuracy=round(float(accuracy), 1),
        detail=json.dumps(detail or {}, ensure_ascii=False),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def _stats(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mean": None, "sd": None, "median": None, "min": None, "max": None}
    mean = statistics.mean(values)
    sd = statistics.stdev(values) if len(values) >= 2 else 0.0
    return {
        "n": len(values),
        "mean": round(mean, 3),
        "sd": round(sd, 3),
        "median": round(statistics.median(values), 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }


def _interpret_group(
    experiment_type: str, class_stats: dict, school_stats: dict,
) -> str:
    """基于指标语义生成群体画像解释。"""
    c_mean = class_stats.get("mean")
    s_mean = school_stats.get("mean")
    if c_mean is None or s_mean is None:
        return "数据不足，暂无法生成群体画像解释。"

    higher_is_risk = METRIC_HIGHER_IS_RISK.get(experiment_type, True)
    delta = round(c_mean - s_mean, 3)
    direction = "高于" if delta > 0 else ("低于" if delta < 0 else "持平于")
    risk_word = "需要关注" if higher_is_risk else "为积极信号"

    texts = {
        "stroop": (
            f"该班平均 Stroop 效应量 {c_mean}ms，{direction}全校基准 {s_mean}ms"
            f"（差值 {delta:+}ms）。效应量越大说明词义干扰越强、认知控制负荷越高。"
            f"若显著高于基准，{risk_word}，可结合课堂专注表现综合观察。"
        ),
        "flanker": (
            f"该班平均 Flanker 干扰效应量 {c_mean}ms，{direction}全校基准 {s_mean}ms"
            f"（差值 {delta:+}ms）。干扰效应反映选择性注意与冲突抑制能力。"
        ),
        "gonogo": (
            f"该班平均虚报率 {c_mean}%，{direction}全校基准 {s_mean}%"
            f"（差值 {delta:+} 个百分点）。虚报率越高提示反应抑制能力越弱、冲动性越高。"
        ),
        "iat": (
            f"该班平均 IAT D 分数 {c_mean}，{direction}全校基准 {s_mean}"
            f"（差值 {delta:+}）。D 分数为负提示消极自我内隐联结倾向，"
            f"若全班整体偏负，{risk_word}，建议结合量表筛查重点关注。"
        ),
    }
    return texts.get(experiment_type, "已生成群体画像，详见数据。")


def compare_group(
    db: Session,
    class_name: str,
    experiment_type: str,
) -> dict:
    """
    班级 vs 全校群体对照。

    返回：班级统计、全校统计、班级-全校差值、群体画像解释、样本量提示。
    """
    class_recs = (
        db.query(ExperimentRecord)
        .filter(ExperimentRecord.class_name == class_name,
                ExperimentRecord.experiment_type == experiment_type)
        .all()
    )
    school_recs = (
        db.query(ExperimentRecord)
        .filter(ExperimentRecord.experiment_type == experiment_type)
        .all()
    )

    class_values = [r.key_metric for r in class_recs]
    school_values = [r.key_metric for r in school_recs]

    class_stats = _stats(class_values)
    school_stats = _stats(school_values)

    delta = None
    if class_stats.get("mean") is not None and school_stats.get("mean") is not None:
        delta = round(class_stats["mean"] - school_stats["mean"], 3)

    return {
        "experiment_type": experiment_type,
        "class_name": class_name,
        "metric_name": METRIC_NAMES.get(experiment_type, "关键指标"),
        "class_stats": class_stats,
        "school_stats": school_stats,
        "delta": delta,
        "interpretation": _interpret_group(experiment_type, class_stats, school_stats),
        "sample_warning": (
            "该班样本量不足，结果仅供参考" if class_stats.get("n", 0) < MIN_SAMPLE
            else "" if class_stats.get("n", 0) >= 1
            else "该班暂无实验记录"
        ),
    }
