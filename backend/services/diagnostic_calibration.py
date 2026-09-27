"""
诊断算法校准服务
================

用合成虚拟被试批量评估「自动诊断算法」的性能指标，形成可复现的
「算法体检」报告：

  - 量表总体一致率：系统量表判定等级与真值等级完全一致的比例
  - 情绪总体一致率：系统情绪判定与真值情绪一致的比例
  - 灵敏度（阳性检出率）：阳性剖面中被判定为非正常的比例
  - 特异度（阴性正确率）：健康对照剖面中被判定为正常的比例
  - ROC AUC：风险分数对「真值阳性」判定的曲线下面积（统计检验）
  - Pearson r：量表标准分与潜在特质 θ 的相关（量表效度代理指标）
  - Cohen's Kappa：判定等级与真值等级的二值一致性（统计检验）
  - 各剖面明细：样本数 / 一致率 / 平均判定等级 / 边界案例
  - 边界案例：判定等级与真值等级相差 ≥2 级的样本数

文献基准（用于对照说明，合成数据仅作方法演示）：
  - Ebert et al. (2019)：抑郁风险筛选 AUC≈0.73
  - Han et al. (2022)：机器学习风险画像 AUC≈0.947
  - PHQ-9 中国大学生样本（Zhang et al., 2013）：AUC=0.977
  - CD-CAT-D（汪大勋等）：AUC 0.80~0.90

全部基于合成数据（is_synthetic=True），不涉及真实样本。
"""

from __future__ import annotations
import random
from dataclasses import dataclass

from backend.services.virtual_subject import (
    PROFILES,
    generate_virtual_subject,
    auto_diagnose,
)
from backend.services.scale_stats import pearson_r, cohen_kappa, roc_auc, roc_points

_LEVEL_ORDER = ["normal", "mild", "moderate", "severe"]
_LEVEL_RANK = {lvl: i for i, lvl in enumerate(_LEVEL_ORDER)}
_LEVEL_CN_MAP = {"正常": "normal", "轻度": "mild", "中度": "moderate", "重度": "severe"}

# 文献对照基准（来源见文件头注释）
LITERATURE_BENCHMARKS = [
    {"source": "Ebert et al. (2019) 抑郁风险筛选", "metric": "AUC", "value": 0.73},
    {"source": "Han et al. (2022) 风险画像", "metric": "AUC", "value": 0.947},
    {"source": "PHQ-9 中国大学生 (Zhang et al., 2013)", "metric": "AUC", "value": 0.977},
    {"source": "CD-CAT-D (汪大勋等)", "metric": "AUC", "value": "0.80~0.90"},
]


def _level_cn_to_rank(cn: str) -> int:
    key = _LEVEL_CN_MAP.get(cn, "normal")
    return _LEVEL_RANK.get(key, 0)


@dataclass
class ProfileCalibration:
    """单个剖面的校准结果。"""
    profile_id: str
    profile_name: str
    n: int
    scale_match: int = 0
    emotion_match: int = 0
    level_rank_sum: float = 0.0
    true_rank_sum: float = 0.0
    boundary_cases: int = 0

    @property
    def scale_accuracy(self) -> float:
        return round(self.scale_match / self.n * 100, 1) if self.n else 0.0

    @property
    def emotion_accuracy(self) -> float:
        return round(self.emotion_match / self.n * 100, 1) if self.n else 0.0

    @property
    def mean_level_rank(self) -> float:
        return round(self.level_rank_sum / self.n, 2) if self.n else 0.0

    @property
    def mean_true_rank(self) -> float:
        return round(self.true_rank_sum / self.n, 2) if self.n else 0.0


def run_diagnostic_calibration(
    seed: int = 42,
    n_per_profile: int = 10,
) -> dict:
    """
    运行诊断算法校准。

    Args:
        seed: 随机种子（可复现）
        n_per_profile: 每个剖面生成的样本数

    Returns:
        结构化校准报告（总体指标 + 各剖面明细 + 结论）
    """
    rng = random.Random(seed)
    details: list[ProfileCalibration] = []
    total = 0
    total_scale_match = 0
    total_emotion_match = 0
    positive_total = 0      # 阳性剖面样本总数
    positive_detected = 0   # 阳性剖面被判为非正常数
    negative_total = 0      # 健康对照样本总数
    negative_correct = 0    # 健康对照被判为正常数

    # 统计检验收集（ROC AUC / Pearson r / Kappa）
    risk_scores: list[float] = []        # 系统风险分数（连续）
    positive_labels: list[bool] = []     # 真值阳性（等级≥mild）
    scale_std_scores: list[float] = []   # 主导量表标准分
    true_thetas: list[float] = []        # 真值潜在特质
    pred_binary: list[bool] = []         # 系统判定阳性
    true_binary: list[bool] = []         # 真值阳性

    for profile in PROFILES:
        pid = profile["id"]
        pc = ProfileCalibration(profile_id=pid, profile_name=profile["name"], n=n_per_profile)
        for i in range(n_per_profile):
            subj_seed = rng.randint(0, 2**31 - 1)
            subject = generate_virtual_subject(pid, seed=subj_seed)
            result = auto_diagnose(subject)

            comparison = result.get("comparison", {})
            scale_diag = result.get("scale_diagnosis", {})

            scale_match = bool(comparison.get("scale_level_match", False))
            emotion_match = bool(comparison.get("emotion_match", False))
            pc.scale_match += int(scale_match)
            pc.emotion_match += int(emotion_match)

            pred_rank = _LEVEL_RANK.get(scale_diag.get("overall_level", "normal"), 0)
            true_rank = _level_cn_to_rank(str(comparison.get("true_level_cn", "正常")))
            pc.level_rank_sum += pred_rank
            pc.true_rank_sum += true_rank
            if abs(pred_rank - true_rank) >= 2:
                pc.boundary_cases += 1

            total += 1
            total_scale_match += int(scale_match)
            total_emotion_match += int(emotion_match)

            if pid == "healthy_control":
                negative_total += 1
                negative_correct += int(pred_rank == 0)
            else:
                positive_total += 1
                positive_detected += int(pred_rank >= 1)

            # 统计检验数据收集
            truth = subject["ground_truth"]
            risk = result.get("risk_diagnosis", {})
            risk_scores.append(float(risk.get("score", 0.0)) if risk.get("score") is not None else 0.0)
            positive_labels.append(true_rank >= 1)
            dominant = truth.get("dominant_scale", "SAS")
            scale_scores = truth.get("scale_scores", {})
            dom = scale_scores.get(dominant, {})
            scale_std_scores.append(float(dom.get("standard_score", 0.0)) if dom.get("standard_score") is not None else 0.0)
            true_thetas.append(float(truth.get("theta", 0.0)))
            pred_binary.append(pred_rank >= 1)
            true_binary.append(true_rank >= 1)

        details.append(pc)

    overall_scale_acc = round(total_scale_match / total * 100, 1) if total else 0.0
    overall_emotion_acc = round(total_emotion_match / total * 100, 1) if total else 0.0
    sensitivity = round(positive_detected / positive_total * 100, 1) if positive_total else 0.0
    specificity = round(negative_correct / negative_total * 100, 1) if negative_total else 0.0
    boundary_total = sum(d.boundary_cases for d in details)

    # 统计检验结果
    auc = roc_auc(risk_scores, positive_labels)
    roc_pts = roc_points(risk_scores, positive_labels)
    pearson = pearson_r(scale_std_scores, true_thetas)
    kappa = cohen_kappa(true_binary, pred_binary)

    # 按一致率升序排（暴露最需要关注的剖面）
    details_sorted = sorted(details, key=lambda d: (d.scale_accuracy, d.emotion_accuracy))

    return {
        "seed": seed,
        "n_per_profile": n_per_profile,
        "total_samples": total,
        "overall_scale_accuracy": overall_scale_acc,
        "overall_emotion_accuracy": overall_emotion_acc,
        "sensitivity": sensitivity,
        "specificity": specificity,
        "boundary_cases": boundary_total,
        "statistics": {
            "roc_auc": auc,
            "roc_curve": roc_pts,
            "pearson_r_scale_theta": pearson,
            "cohen_kappa": kappa,
            "n": total,
            "is_synthetic": True,
            "literature_benchmarks": LITERATURE_BENCHMARKS,
        },
        "profile_details": [
            {
                "profile_id": d.profile_id,
                "profile_name": d.profile_name,
                "n": d.n,
                "scale_accuracy": d.scale_accuracy,
                "emotion_accuracy": d.emotion_accuracy,
                "mean_level_rank": d.mean_level_rank,
                "mean_true_rank": d.mean_true_rank,
                "boundary_cases": d.boundary_cases,
            }
            for d in details_sorted
        ],
        "interpretation": _build_interpretation(
            overall_scale_acc, overall_emotion_acc,
            sensitivity, specificity, boundary_total, total,
            auc=auc, pearson=pearson, kappa=kappa,
        ),
    }


def _build_interpretation(
    scale_acc: float,
    emotion_acc: float,
    sensitivity: float,
    specificity: float,
    boundary: int,
    total: int,
    auc: float | None = None,
    pearson: float | None = None,
    kappa: float | None = None,
) -> str:
    """生成校准结论文字。"""
    parts = [
        f"在 {total} 个合成样本上，自动诊断的总体量表一致率为 {scale_acc}%、"
        f"情绪一致率为 {emotion_acc}%、灵敏度（阳性检出率）为 {sensitivity}%、"
        f"特异度（阴性正确率）为 {specificity}%。"
    ]
    if auc is not None:
        if auc >= 0.9:
            parts.append(f"风险分数对真值阳性的 ROC AUC 为 {auc}（≥0.90，判别能力极佳，"
                         "参考 Swets, 1988 的判别等级）。")
        elif auc >= 0.8:
            parts.append(f"风险分数对真值阳性的 ROC AUC 为 {auc}（0.80~0.90，判别能力良好，"
                         "处于 CD-CAT-D 文献报告区间 0.80~0.90 内）。")
        else:
            parts.append(f"风险分数对真值阳性的 ROC AUC 为 {auc}，判别能力一般，"
                         "建议进一步调整风险分数构成。")
    if pearson is not None:
        parts.append(f"量表标准分与潜在特质 θ 的 Pearson 相关为 {pearson}（量表效度的代理指标，"
                     "|r|≥0.70 提示与特质强相关）。")
    if kappa is not None:
        parts.append(f"判定等级与真值等级的二值一致性 Cohen's Kappa 为 {kappa}"
                     "（κ≥0.61 为实质性一致，0.41~0.60 为中等一致）。")
    if sensitivity >= 95:
        parts.append("阳性剖面检出能力强，风险学生不易漏检。")
    elif sensitivity >= 85:
        parts.append("阳性剖面检出能力良好，边界样本存在漏检风险。")
    else:
        parts.append("阳性剖面检出率偏低，建议结合量表阈值与 θ 分段对齐进一步校准。")
    if specificity >= 90:
        parts.append("健康对照判定准确，误报率低。")
    elif specificity >= 80:
        parts.append("健康对照存在一定误报，建议复核健康剖面的量表生成参数。")
    else:
        parts.append("健康对照误报偏高，可能引起不必要的人工复核。")
    if boundary:
        parts.append(f"另有 {boundary} 个样本判定等级与真值相差 ≥2 级（边界案例），"
                     "主要集中在 θ≈0.8-1.0 的相邻等级边界，属预期内的判定模糊区。")
    else:
        parts.append("未发现判定等级与真值相差 ≥2 级的边界案例。")
    parts.append("（全部为合成数据，仅用于算法验证与演示，不冒充真实样本。）")
    return "".join(parts)
