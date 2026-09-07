"""
经典心理学实验数字化服务
========================

升级项：面向实验心理学（经典实验范式的在线实现与数据采集分析）。

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


# ==================== Flanker 任务 ====================
# 文献依据：
#   - Eriksen, B. A., & Eriksen, C. W. (1974). Effects of noise letters upon the
#     identification of a target letter in a nonspeed task.
#     Perception & Psychophysics, 16(1), 143-149.
#   - Ridderinkhof, K. R., et al. (2004). Neurocognitive mechanisms of cognitive
#     control: The role of prefrontal cortex in action selection, response
#     inhibition, performance monitoring, and reward-based learning.
#     Brain and Cognition, 56(2), 129-140.

FLANKER_DIRECTIONS = ["left", "right"]


@dataclass
class FlankerTrial:
    """单次 Flanker 试次。"""
    trial_id: str
    target: str            # 中央目标方向（left/right）
    flankers: str          # 两侧干扰方向（left/right）
    flanker_type: str      # congruent / incongruent
    correct_answer: str    # 正确答案（中央目标方向）


@dataclass
class FlankerResult:
    """Flanker 实验结果。"""
    experiment_id: str
    total_trials: int
    congruent_rt_mean: float        # 一致条件平均反应时 (ms)
    incongruent_rt_mean: float      # 不一致条件平均反应时 (ms)
    flanker_effect: float           # Flanker 干扰效应量 = 不一致 - 一致 (ms)
    accuracy: float                 # 总正确率
    congruent_accuracy: float
    incongruent_accuracy: float
    interpretation: str
    trials: list = field(default_factory=list)


def generate_flanker_trials(n_per_condition: int = 20, seed: int | None = None) -> list[FlankerTrial]:
    """生成 Flanker 任务试次（中央箭头 + 两侧干扰箭头）。"""
    rng = random.Random(seed)
    trials = []
    for _ in range(n_per_condition):
        target = rng.choice(FLANKER_DIRECTIONS)
        trials.append(FlankerTrial(
            trial_id=str(uuid.uuid4())[:8],
            target=target, flankers=target, flanker_type="congruent",
            correct_answer=target,
        ))
    for _ in range(n_per_condition):
        target = rng.choice(FLANKER_DIRECTIONS)
        flankers = "left" if target == "right" else "right"
        trials.append(FlankerTrial(
            trial_id=str(uuid.uuid4())[:8],
            target=target, flankers=flankers, flanker_type="incongruent",
            correct_answer=target,
        ))
    rng.shuffle(trials)
    return trials


def analyze_flanker(
    trials: list[dict],
    experiment_id: str | None = None,
) -> FlankerResult:
    """分析 Flanker 任务数据。"""
    if not experiment_id:
        experiment_id = str(uuid.uuid4())[:8]

    cong_rts = [t["rt"] for t in trials if t.get("flanker_type") == "congruent" and t.get("correct")]
    incong_rts = [t["rt"] for t in trials if t.get("flanker_type") == "incongruent" and t.get("correct")]
    cong_total = sum(1 for t in trials if t.get("flanker_type") == "congruent")
    incong_total = sum(1 for t in trials if t.get("flanker_type") == "incongruent")
    cong_correct = sum(1 for t in trials if t.get("flanker_type") == "congruent" and t.get("correct"))
    incong_correct = sum(1 for t in trials if t.get("flanker_type") == "incongruent" and t.get("correct"))

    cong_rt = round(sum(cong_rts) / len(cong_rts), 1) if cong_rts else 0
    incong_rt = round(sum(incong_rts) / len(incong_rts), 1) if incong_rts else 0
    flanker_effect = round(incong_rt - cong_rt, 1)
    accuracy = round((cong_correct + incong_correct) / len(trials) * 100, 1) if trials else 0
    cong_acc = round(cong_correct / cong_total * 100, 1) if cong_total else 0
    incong_acc = round(incong_correct / incong_total * 100, 1) if incong_total else 0

    if flanker_effect > 50:
        interp = (
            f"Flanker 干扰效应量为 {flanker_effect}ms（显著），不一致条件比一致条件反应时明显延长，"
            f"符合经典 Flanker 效应（Eriksen & Eriksen, 1974）：两侧干扰刺激自动加工与中央目标"
            f"竞争，反映了选择性注意与认知控制能力。效应量越大，说明对干扰的抑制需求越高。"
        )
    elif flanker_effect > 20:
        interp = (
            f"Flanker 干扰效应量为 {flanker_effect}ms（中等），存在一定的干扰物竞争效应。"
            f"建议增加试次数以提高统计检验力。"
        )
    else:
        interp = (
            f"Flanker 干扰效应量为 {flanker_effect}ms（不明显），未观察到典型干扰效应。"
            f"可能原因：练习效应、试次数不足或任务理解问题，建议至少每条件 20 试次。"
        )
    if accuracy < 80:
        interp += f" 注意：正确率仅 {accuracy}%，数据质量可能受影响。"

    return FlankerResult(
        experiment_id=experiment_id,
        total_trials=len(trials),
        congruent_rt_mean=cong_rt,
        incongruent_rt_mean=incong_rt,
        flanker_effect=flanker_effect,
        accuracy=accuracy,
        congruent_accuracy=cong_acc,
        incongruent_accuracy=incong_acc,
        interpretation=interp,
        trials=trials,
    )


# ==================== Go/No-Go 任务 ====================
# 文献依据：
#   - Donders, F. C. (1868). Over de snelheid van psychische processen. 中文译见
#     Acta Psychologica, 1969（减法反应时范式源头，go/no-go 为其分支）。
#   - Newman, J. P., & Kosson, D. S. (1986). Passive avoidance learning in
#     psychopathic and nonpsychopathic offenders. Journal of Abnormal Psychology,
#     95(3), 252-256.（go/no-go 用于反应抑制与冲动性研究）

GONOGO_STIMULI = ["A", "B", "C", "D", "E", "F"]
GONOGO_TARGETS = {"B", "D", "F"}   # 字母 B/D/F 为 Go 刺激
GONOGO_NON_TARGETS = {"A", "C", "E"}  # 字母 A/C/E 为 No-Go 刺激


@dataclass
class GoNoGoTrial:
    """单次 Go/No-Go 试次。"""
    trial_id: str
    stimulus: str          # 刺激字母
    is_go: bool            # True=Go（需按键），False=No-Go（需抑制）
    correct_answer: str    # "go" / "nogo"


@dataclass
class GoNoGoResult:
    """Go/No-Go 实验结果。"""
    experiment_id: str
    total_trials: int
    go_rt_mean: float          # Go 试次平均反应时 (ms)
    hit_rate: float            # 命中率（Go 正确反应比例 %）
    false_alarm_rate: float    # 虚报率（No-Go 错误反应比例 %）
    inhibition_score: float    # 抑制正确率（1 - 虚报率，%）
    accuracy: float            # 总正确率
    interpretation: str
    trials: list = field(default_factory=list)


def generate_gonogo_trials(n_go: int = 30, n_nogo: int = 10, seed: int | None = None) -> list[GoNoGoTrial]:
    """生成 Go/No-Go 试次（Go 占 75%，No-Go 占 25%，制造反应偏向）。"""
    rng = random.Random(seed)
    trials = []
    for _ in range(n_go):
        stim = rng.choice(sorted(GONOGO_TARGETS))
        trials.append(GoNoGoTrial(
            trial_id=str(uuid.uuid4())[:8],
            stimulus=stim, is_go=True, correct_answer="go",
        ))
    for _ in range(n_nogo):
        stim = rng.choice(sorted(GONOGO_NON_TARGETS))
        trials.append(GoNoGoTrial(
            trial_id=str(uuid.uuid4())[:8],
            stimulus=stim, is_go=False, correct_answer="nogo",
        ))
    rng.shuffle(trials)
    return trials


def analyze_gonogo(
    trials: list[dict],
    experiment_id: str | None = None,
) -> GoNoGoResult:
    """分析 Go/No-Go 实验数据。"""
    if not experiment_id:
        experiment_id = str(uuid.uuid4())[:8]

    go_trials = [t for t in trials if t.get("is_go")]
    nogo_trials = [t for t in trials if not t.get("is_go")]
    go_rts = [t["rt"] for t in go_trials if t.get("rt") is not None and t.get("correct")]

    hit_rate = round(sum(1 for t in go_trials if t.get("correct")) / len(go_trials) * 100, 1) if go_trials else 0
    false_alarm_rate = round(
        sum(1 for t in nogo_trials if not t.get("correct")) / len(nogo_trials) * 100, 1) if nogo_trials else 0
    go_rt = round(sum(go_rts) / len(go_rts), 1) if go_rts else 0
    inhibition_score = round(100 - false_alarm_rate, 1)
    accuracy = round(
        sum(1 for t in trials if t.get("correct")) / len(trials) * 100, 1) if trials else 0

    if false_alarm_rate > 20:
        interp = (
            f"虚报率 {false_alarm_rate}%（偏高）：对 No-Go 刺激的错误反应比例较大，"
            f"提示反应抑制（response inhibition）能力偏弱、冲动性较高"
            f"（Newman & Kosson, 1986）。结合 Go 平均反应时 {go_rt}ms 可进一步判断"
            f"是速度-准确性权衡还是抑制缺陷。"
        )
    elif false_alarm_rate > 8:
        interp = (
            f"虚报率 {false_alarm_rate}%（中等），存在一定程度的抑制失败，"
            f"属于正常范围内的个体差异。可增加 No-Go 比例以提高敏感度。"
        )
    else:
        interp = (
            f"虚报率 {false_alarm_rate}%（较低），对 No-Go 刺激的抑制表现良好，"
            f"反应抑制功能正常。Go 试次命中率 {hit_rate}%、平均反应时 {go_rt}ms。"
        )
    if hit_rate < 80:
        interp += f" 注意：命中率仅 {hit_rate}%，Go 试次漏报较多，需检查被试是否理解任务。"
    if not go_rts:
        interp += " 注意：没有有效的 Go 反应时数据。"

    return GoNoGoResult(
        experiment_id=experiment_id,
        total_trials=len(trials),
        go_rt_mean=go_rt,
        hit_rate=hit_rate,
        false_alarm_rate=false_alarm_rate,
        inhibition_score=inhibition_score,
        accuracy=accuracy,
        interpretation=interp,
        trials=trials,
    )


# ==================== IAT 内隐联想测验 ====================
# 文献依据：
#   - Greenwald, A. G., McGhee, D. E., & Schwartz, J. L. K. (1998). Measuring
#     individual differences in implicit cognition: The implicit association test.
#     Journal of Personality and Social Psychology, 74(6), 1464-1480.
#   - Greenwald, A. G., Nosek, B. A., & Banaji, M. R. (2003). Understanding and
#     using the implicit association test: I. An improved scoring algorithm.
#     Journal of Personality and Social Psychology, 85(2), 197-216.

IAT_CATEGORY_A = {"自我": ["我", "我的", "自己", "本人"], "他人": ["他", "别人", "他们", "他人"]}
IAT_CATEGORY_B = {"积极": ["快乐", "成功", "美好", "健康"], "消极": ["痛苦", "失败", "糟糕", "疾病"]}
# IAT 刺激词表（标准中文字词，教学演示用）


@dataclass
class IatTrial:
    """单次 IAT 试次。"""
    trial_id: str
    stimulus: str          # 刺激词
    category: str          # 所属类别（自我/他人/积极/消极）
    block_type: str        # compatible（自我+积极） / incompatible（自我+消极）
    correct_answer: str    # "left" / "right"


@dataclass
class IatResult:
    """IAT 实验结果。"""
    experiment_id: str
    total_trials: int
    compatible_rt_mean: float      # 相容 block 平均反应时 (ms)
    incompatible_rt_mean: float    # 不相容 block 平均反应时 (ms)
    d_score: float                 # IAT D 分数（Greenwald et al., 2003）
    accuracy: float
    interpretation: str
    trials: list = field(default_factory=list)


def _iat_block_trials(block_type: str, rng: random.Random, n: int) -> list[IatTrial]:
    """生成一个 IAT block 的试次（左=类别A首项+类别B首项，右=其余）。"""
    trials = []
    all_words = []
    for cat, words in {**IAT_CATEGORY_A, **IAT_CATEGORY_B}.items():
        all_words.extend((w, cat) for w in words)
    rng.shuffle(all_words)
    for word, cat in all_words[:n]:
        # 相容：自我/积极 → 左；他人/消极 → 右
        if block_type == "compatible":
            left = cat in ("自我", "积极")
        else:
            left = cat in ("自我", "消极")
        trials.append(IatTrial(
            trial_id=str(uuid.uuid4())[:8],
            stimulus=word, category=cat, block_type=block_type,
            correct_answer="left" if left else "right",
        ))
    return trials


def generate_iat_trials(n_per_block: int = 16, seed: int | None = None) -> list[IatTrial]:
    """生成 IAT 试次（相容 block + 不相容 block）。"""
    rng = random.Random(seed)
    trials = _iat_block_trials("compatible", rng, n_per_block)
    trials += _iat_block_trials("incompatible", rng, n_per_block)
    rng.shuffle(trials)
    return trials


def analyze_iat(
    trials: list[dict],
    experiment_id: str | None = None,
) -> IatResult:
    """分析 IAT 实验数据（Greenwald et al., 2003 改进计分）。

    D 分数 = (mean_incompatible - mean_compatible) / 合并标准差。
    正值表示"自我+积极"联结更强（相容条件更快）。
    """
    if not experiment_id:
        experiment_id = str(uuid.uuid4())[:8]

    def block_stats(block: str) -> tuple:
        rts = [t["rt"] for t in trials
               if t.get("block_type") == block and t.get("rt") is not None and t.get("correct")]
        total = sum(1 for t in trials if t.get("block_type") == block)
        correct = sum(1 for t in trials if t.get("block_type") == block and t.get("correct"))
        mean_rt = sum(rts) / len(rts) if rts else 0.0
        acc = correct / total * 100 if total else 0.0
        return mean_rt, acc, rts

    comp_mean, comp_acc, comp_rts = block_stats("compatible")
    incom_mean, incom_acc, incom_rts = block_stats("incompatible")
    accuracy = round((comp_acc * 0.5 + incom_acc * 0.5), 1) if (comp_rts or incom_rts) else 0

    # D 分数（简化版）：正确试次均值差 / 合并标准差
    all_rts = comp_rts + incom_rts
    if len(all_rts) >= 2:
        n1, n2 = len(comp_rts), len(incom_rts)
        mean_all = sum(all_rts) / len(all_rts)
        var_all = sum((x - mean_all) ** 2 for x in all_rts) / (len(all_rts) - 1)
        sd_all = var_all ** 0.5
        d_score = round((incom_mean - comp_mean) / sd_all, 3) if sd_all > 0 else 0.0
    else:
        d_score = 0.0

    if d_score > 0.2:
        interp = (
            f"IAT D 分数为 {d_score}（正值，中等以上内隐联结）：对「自我+积极」类配对反应更快，"
            f"提示被试存在正向的自我内隐联结（Greenwald et al., 1998）。"
            f"相容 block 平均反应时 {comp_mean:.0f}ms 显著快于不相容 {incom_mean:.0f}ms。"
        )
    elif d_score < -0.2:
        interp = (
            f"IAT D 分数为 {d_score}（负值）：对「自我+消极」类配对反应更快，"
            f"提示可能存在负向的自我内隐联结（如低自尊、自我否定倾向），"
            f"该模式在临床心理学中与抑郁、焦虑的认知偏差相关"
            f"（Greenwald et al., 2003）。建议结合量表结果综合解读。"
        )
    else:
        interp = (
            f"IAT D 分数为 {d_score}（接近零）：自我与积极/消极联结无显著差异，"
            f"内隐自我态度偏中性。可能受练习效应或刺激词熟悉度影响。"
        )
    if accuracy < 70:
        interp += f" 注意：总正确率仅 {accuracy}%，数据质量可能受影响，建议检查任务理解。"

    return IatResult(
        experiment_id=experiment_id,
        total_trials=len(trials),
        compatible_rt_mean=round(comp_mean, 1),
        incompatible_rt_mean=round(incom_mean, 1),
        d_score=d_score,
        accuracy=accuracy,
        interpretation=interp,
        trials=trials,
    )
