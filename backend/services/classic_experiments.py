"""
经典心理学实验数字化服务
========================

升级项：主攻实验心理学（经典实验范式的在线实现与数据采集分析）。

目前实现：
  1. Stroop 效应实验（Stroop, 1935）—— 注意力与认知控制的经典范式

文献依据：
  - Stroop, J. R. (1935). Studies of interference in serial verbal reactions.
    Journal of Experimental Psychology, 18(6), 643-662.
  - MacLeod, C. M. (1991). Half a century of research on the Stroop effect.
    Psychological Bulletin, 109(2), 163-203.
"""

from __future__ import annotations
import random
import uuid
from dataclasses import dataclass, field


# ==================== Stroop 实验 ====================

STROOP_COLORS = {
    "red": {"cn": "红", "hex": "#ef4444"},
    "blue": {"cn": "蓝", "hex": "#3b82f6"},
    "green": {"cn": "绿", "hex": "#10b981"},
    "yellow": {"cn": "黄", "hex": "#f59e0b"},
}

STROOP_WORDS = ["red", "blue", "green", "yellow"]


@dataclass
class StroopTrial:
    """单次 Stroop 试次。"""
    trial_id: str
    word: str           # 词义（red/blue/green/yellow）
    color: str          # 字的颜色（red/blue/green/yellow）
    congruent: bool     # 是否一致（词义=颜色）
    correct_answer: str  # 正确答案（颜色）


@dataclass
class StroopResult:
    """Stroop 实验结果。"""
    experiment_id: str
    total_trials: int
    congruent_rt_mean: float       # 一致条件平均反应时 (ms)
    incongruent_rt_mean: float     # 不一致条件平均反应时 (ms)
    stroop_effect: float           # Stroop 效应量 = 不一致 - 一致 (ms)
    accuracy: float                 # 正确率
    congruent_accuracy: float       # 一致条件正确率
    incongruent_accuracy: float     # 不一致条件正确率
    interpretation: str             # 结果解释
    trials: list = field(default_factory=list)  # 试次详情


def generate_stroop_trials(n_per_condition: int = 20, seed: int | None = None) -> list[StroopTrial]:
    """
    生成 Stroop 实验试次。

    n_per_condition: 每个条件（一致/不一致）的试次数
    seed: 随机种子（可复现）
    """
    rng = random.Random(seed)
    trials = []

    # 一致条件：词义=颜色
    for _ in range(n_per_condition):
        color = rng.choice(STROOP_WORDS)
        trials.append(StroopTrial(
            trial_id=str(uuid.uuid4())[:8],
            word=color, color=color, congruent=True,
            correct_answer=color,
        ))

    # 不一致条件：词义≠颜色
    for _ in range(n_per_condition):
        word = rng.choice(STROOP_WORDS)
        color = rng.choice([c for c in STROOP_WORDS if c != word])
        trials.append(StroopTrial(
            trial_id=str(uuid.uuid4())[:8],
            word=word, color=color, congruent=False,
            correct_answer=color,
        ))

    rng.shuffle(trials)
    return trials


def analyze_stroop(
    trials: list[dict],
    experiment_id: str | None = None,
) -> StroopResult:
    """
    分析 Stroop 实验数据。

    trials: 试次列表，每个含 trial_id, congruent, rt(ms), correct(bool)
    """
    if not experiment_id:
        experiment_id = str(uuid.uuid4())[:8]

    congruent_rts = [t["rt"] for t in trials if t.get("congruent") and t.get("correct")]
    incongruent_rts = [t["rt"] for t in trials if not t.get("congruent") and t.get("correct")]

    congruent_total = sum(1 for t in trials if t.get("congruent"))
    incongruent_total = sum(1 for t in trials if not t.get("congruent"))
    congruent_correct = sum(1 for t in trials if t.get("congruent") and t.get("correct"))
    incongruent_correct = sum(1 for t in trials if not t.get("congruent") and t.get("correct"))

    cong_rt = round(sum(congruent_rts) / len(congruent_rts), 1) if congruent_rts else 0
    incong_rt = round(sum(incongruent_rts) / len(incongruent_rts), 1) if incongruent_rts else 0
    stroop_effect = round(incong_rt - cong_rt, 1)

    total_correct = congruent_correct + incongruent_correct
    accuracy = round(total_correct / len(trials) * 100, 1) if trials else 0
    cong_acc = round(congruent_correct / congruent_total * 100, 1) if congruent_total else 0
    incong_acc = round(incongruent_correct / incongruent_total * 100, 1) if incongruent_total else 0

    # 结果解释（基于经典 Stroop 效应文献）
    if stroop_effect > 50:
        effect_desc = "显著"
        interp = (
            f"Stroop 效应量为 {stroop_effect}ms（{effect_desc}），"
            f"不一致条件比一致条件反应时显著延长。这符合经典 Stroop 效应"
            f"（Stroop, 1935; MacLeod, 1991），说明词义自动加工干扰了颜色命名，"
            f"反映了认知控制能力。效应量越大，说明干扰越强、认知控制需求越高。"
        )
    elif stroop_effect > 20:
        effect_desc = "中等"
        interp = (
            f"Stroop 效应量为 {stroop_effect}ms（{effect_desc}），"
            f"存在一定的词义干扰效应。建议增加试次数以提高统计检验力。"
        )
    else:
        effect_desc = "不明显"
        interp = (
            f"Stroop 效应量为 {stroop_effect}ms（{effect_desc}），"
            f"未观察到典型的 Stroop 干扰。可能原因：试次数不足、练习效应、"
            f"或被试采用了特殊策略。建议至少每条件 20 试次，并设置练习阶段。"
        )

    if accuracy < 80:
        interp += f" 注意：正确率仅 {accuracy}%，数据质量可能受影响，建议检查被试理解程度。"

    return StroopResult(
        experiment_id=experiment_id,
        total_trials=len(trials),
        congruent_rt_mean=cong_rt,
        incongruent_rt_mean=incong_rt,
        stroop_effect=stroop_effect,
        accuracy=accuracy,
        congruent_accuracy=cong_acc,
        incongruent_accuracy=incong_acc,
        interpretation=interp,
        trials=trials,
    )
