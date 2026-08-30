"""
合成数据引擎（Synthetic Subject Generator）
==========================================

用途：在**不依赖真实学生数据**的前提下，为以下升级提供可复现的数据基础：
  1. 多模态融合消融对照实验（E3）
  2. CAT 全量表 vs 自适应等价性实验（E2）
  3. 量表信效度检验套件（Cronbach α / 结构效度）
  4. 虚拟被试驱动的教学实验演示

设计要点：
  - 每个合成被试由潜在特质 θ 驱动（θ>0 症状倾向更强，θ<0 更健康）
  - 量表作答按 IRT 3PL 模型 + 选项分映射生成（保留题目难度/区分度结构）
  - E1-E12 参数按常模均值/标准差采样，并与 θ 相关联（负性参数随 θ 升高）
  - 输出一律带 is_synthetic=True 标记，与真实数据严格隔离

⚠️ 明确边界：合成数据仅用于方法验证与教学演示，不冒充真实样本。
"""

from __future__ import annotations
import math
import random

# IRT 缩放常数（与 cat.py 一致）
_D = 1.702


def _irt_prob(theta: float, a: float, b: float, c: float) -> float:
    """3PL 认可概率。"""
    e = math.exp(-_D * a * (theta - b))
    return c + (1 - c) / (1 + e)


def generate_scale_answers(scale: dict, theta: float, rng: random.Random) -> list[int]:
    """
    按 IRT 模型为某量表生成合成作答。

    scale: 量表 dict（含 questions / scoring）
    theta: 潜在特质
    rng:   随机源（可复现）
    返回:   与 questions 等长的选项分列表（1-based，与真实计分一致）
    """
    scoring = scale.get("scoring", {})
    options = scoring.get("options", [1, 2, 3, 4])
    labels = scoring.get("labels", [])
    n_levels = len(options)
    reverse_items = scoring.get("reverse_items", [])

    answers = []
    for q in scale["questions"]:
        irt = q.get("irt") or {}
        a = float(irt.get("a", 1.0))
        b = float(irt.get("b", 0.0))
        c = float(irt.get("c", 0.1))
        qid = q.get("id")

        # 症状方向：正向题 θ 越大越认可；反向题 θ 越大越不认可
        direction = -1.0 if qid in reverse_items else 1.0
        p = _irt_prob(direction * theta, a, b, c)
        p = min(max(p, 1e-6), 1 - 1e-6)

        # 期望选项分 = 1 + (n_levels-1)·P，加小噪声后取整（与 θ 强相关，保证内部一致性）
        expected = 1.0 + (n_levels - 1) * p
        score = int(round(min(max(expected + rng.gauss(0, 0.6), 1.0), n_levels)))
        answers.append(score)
    return answers


def generate_e_params(theta: float, rng: random.Random) -> dict:
    """
    生成 E1-E12 参数（Minkin 体系，单位与常模一致）。
    θ>0 → 负性参数升高、正性参数降低。
    """
    try:
        from backend.vibraimage.utils.constants import NORMAL_NORMS, NORMAL_SDS
    except Exception:  # 常模缺失时用默认值
        NORMAL_NORMS = {"aggression": 40.5, "stress": 31.2, "tension": 30.5, "suspicious": 28.3,
                        "balance": 61.6, "charm": 56.4, "energy": 46.1, "self_regulation": 55.3,
                        "inhibition": 24.9, "neuroticism": 31.3, "depression": 31.2, "happiness": 49.8}
        NORMAL_SDS = {k: 8.0 for k in NORMAL_NORMS}

    negative = ["aggression", "stress", "tension", "suspicious", "inhibition", "neuroticism", "depression"]
    positive = ["balance", "charm", "energy", "self_regulation", "happiness"]

    e_params = {}
    for key, mean in NORMAL_NORMS.items():
        sd = float(NORMAL_SDS.get(key, 8.0))
        # θ 调制：负性随 θ 增大而增大，正性随 θ 增大而减小（幅度约 1.2·θ·sd）
        if key in negative:
            shift = 1.2 * theta * sd
        elif key in positive:
            shift = -1.2 * theta * sd
        else:
            shift = 0.0
        value = mean + shift + rng.gauss(0, sd * 0.35)
        e_params[key] = round(min(max(value, 0.0), 100.0), 2)
    return e_params


def emotion_from_theta(theta: float) -> str:
    """由潜在特质映射情绪标签（用于融合对照实验的真值）。"""
    if theta >= 1.0:
        return "severe_negative"
    if theta >= 0.3:
        return "mild_negative"
    if theta <= -0.3:
        return "positive"
    return "neutral"


def generate_subject(theta: float | None = None, seed: int | None = None,
                     scales: list[dict] | None = None) -> dict:
    """
    生成一名合成被试。

    theta: 潜在特质（None 时从 N(0,1) 采样）
    scales: 量表 dict 列表（None 时加载全部五套）
    返回: {is_synthetic, theta, emotion_label, scale_answers, e_params, ...}
    """
    rng = random.Random(seed)
    if theta is None:
        theta = round(rng.gauss(0.0, 1.0), 3)

    if scales is None:
        from backend.api.routes.scales import _load_scale
        scales = [_load_scale(c) for c in ["SAS", "SDS", "SCL-90", "PSS-10", "PANAS"]]

    answers = {}
    for s in scales:
        answers[s["code"]] = generate_scale_answers(s, theta, rng)

    return {
        "is_synthetic": True,
        "theta": theta,
        "emotion_label": emotion_from_theta(theta),
        "scale_answers": answers,
        "e_params": generate_e_params(theta, rng),
        "k_value": round(min(max(1.5 + 3.0 * abs(theta), 0.5), 12.0), 2),
    }


def generate_subjects(n: int, seed: int = 42, scales: list[dict] | None = None,
                      theta_list: list[float] | None = None) -> list[dict]:
    """批量生成 n 名合成被试（theta_list 提供时按给定 θ 逐个生成）。"""
    if theta_list is not None:
        return [generate_subject(theta=t, seed=seed + i, scales=scales)
                for i, t in enumerate(theta_list)]
    return [generate_subject(seed=seed + i, scales=scales) for i in range(n)]


def generate_e_params_with_noise(e_params: dict, noise_sd: float = 4.0,
                                 seed: int | None = None) -> dict:
    """为同一名被试的多模态信号加噪声（模拟同一场景多次测量），用于消融实验。"""
    rng = random.Random(seed)
    return {k: round(min(max(v + rng.gauss(0, noise_sd), 0.0), 100.0), 2)
            for k, v in e_params.items()}
