"""
升级 20-24 边界测试
====================

覆盖：
  - 升级20 多模态融合（MultiModalEmotionFuser）：置信度计算与融合边界
  - 升级21 经典实验（Flanker / Go-NoGo / IAT）：空数据与极端输入边界
  - 升级16 风险分级（assess_risk）：极端分数与空输入
  - 升级19 虚拟被试自动诊断（auto_diagnose）：全部剖面可诊断 + 可复现
"""

from __future__ import annotations
import pytest
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.tools.multi_modal_fusion import MultiModalEmotionFuser
from backend.services.classic_experiments import (
    generate_flanker_trials, analyze_flanker,
    generate_gonogo_trials, analyze_gonogo,
    generate_iat_trials, analyze_iat,
)
from backend.services.risk_assessment import assess_risk
from backend.services.virtual_subject import PROFILES, generate_virtual_subject, auto_diagnose

fuser = MultiModalEmotionFuser()


# ==================== 多模态融合 · 置信度 ====================

def test_entropy_confidence_certain_is_one():
    """完全确定的概率分布 → 熵置信度 = 1。"""
    probs = {"happy": 1.0, "sad": 0.0, "neutral": 0.0}
    assert fuser.compute_facial_confidence_entropy(probs) == pytest.approx(1.0)


def test_entropy_confidence_uniform_is_zero():
    """均匀分布 → 熵置信度 ≈ 0。"""
    probs = {k: 1.0 / 7 for k in ["开心", "中性", "悲伤", "愤怒", "惊讶", "害怕", "厌恶"]}
    assert fuser.compute_facial_confidence_entropy(probs) == pytest.approx(0.0, abs=1e-9)


def test_entropy_confidence_empty_is_zero():
    """空概率字典 → 熵置信度 = 0（不崩溃）。"""
    assert fuser.compute_facial_confidence_entropy({}) == 0.0


def test_variance_confidence_empty_is_zero():
    """无窗口数据 → 方差置信度 = 0。"""
    assert fuser.compute_vestibular_confidence_variance([]) == 0.0


def test_variance_confidence_single_window_default():
    """仅 1 个窗口 → 返回默认置信度 0.5（数据不足）。"""
    window = {k: 5.0 for k in ["aggression", "stress", "tension", "suspect",
                               "balance", "charm", "energy", "self_regulation",
                               "inhibition", "neuroticism", "depression", "happiness"]}
    assert fuser.compute_vestibular_confidence_variance([window]) == 0.5


def test_variance_confidence_stable_higher_than_noisy():
    """稳定窗口序列的置信度应高于波动大的序列。"""
    keys = ["aggression", "stress", "tension", "suspect",
            "balance", "charm", "energy", "self_regulation",
            "inhibition", "neuroticism", "depression", "happiness"]
    stable = [{k: 5.0 for k in keys} for _ in range(5)]
    noisy = [{k: 5.0 + i * 2.0 for k in keys} for i in range(5)]
    assert fuser.compute_vestibular_confidence_variance(stable) > fuser.compute_vestibular_confidence_variance(noisy)


# ==================== 多模态融合 · 融合行为 ====================

def _facial(valence, arousal, probs):
    return {"facial_valence": valence, "facial_arousal": arousal, "emotion_probs": probs}


def _vestibular(valence, arousal, windows=None):
    return {"valence": valence, "arousal": arousal, "window_results": windows or []}


def test_fuse_weights_favor_high_confidence_modality():
    """面部高置信 + 前庭低置信 → 面部权重应更大。"""
    certain = {"开心": 0.99, "中性": 0.01, "悲伤": 0.0, "愤怒": 0.0, "惊讶": 0.0, "害怕": 0.0, "厌恶": 0.0}
    # 前庭无窗口数据 → c_vi = 0 → 权重几乎全给面部
    result = fuser.fuse(_facial(0.8, 0.6, certain), _vestibular(0.1, 0.1))
    assert result is not None
    assert result.w_face > result.w_vi
    assert result.fused_valence > 0.6  # 融合结果偏向面部


def test_fuse_both_low_confidence_falls_back_equal():
    """两者置信度都极低 → 退化为等权融合。"""
    uniform = {k: 1.0 / 7 for k in ["开心", "中性", "悲伤", "愤怒", "惊讶", "害怕", "厌恶"]}
    result = fuser.fuse(_facial(0.8, 0.6, uniform), _vestibular(-0.4, -0.2))
    assert result is not None
    assert result.w_face == pytest.approx(0.5, abs=0.05)
    assert result.fused_valence == pytest.approx(0.2, abs=0.05)


def test_fuse_modal_inconsistency_flag():
    """两模态 V-A 距离超过阈值 → 标记需复核。"""
    certain = {"开心": 0.99, "中性": 0.01, "悲伤": 0.0, "愤怒": 0.0, "惊讶": 0.0, "害怕": 0.0, "厌恶": 0.0}
    result = fuser.fuse(_facial(0.9, 0.7, certain), _vestibular(-0.9, -0.7))
    assert result is not None
    assert result.modal_inconsistent is True


def test_fuse_consistent_modality_no_flag():
    """两模态一致且距离小 → 不标记复核。"""
    certain = {"开心": 0.99, "中性": 0.01, "悲伤": 0.0, "愤怒": 0.0, "惊讶": 0.0, "害怕": 0.0, "厌恶": 0.0}
    result = fuser.fuse(_facial(0.5, 0.4, certain), _vestibular(0.4, 0.3))
    assert result is not None
    assert result.modal_inconsistent is False


# ==================== 经典实验 · Flanker ====================

def test_flanker_generate_reproducible():
    """相同 seed → 生成相同试次。"""
    a = generate_flanker_trials(n_per_condition=10, seed=7)
    b = generate_flanker_trials(n_per_condition=10, seed=7)
    assert [(t.target, t.flanker_type) for t in a] == [(t.target, t.flanker_type) for t in b]


def test_flanker_analyze_empty():
    """空试次 → 不崩溃，指标归零。"""
    r = analyze_flanker([])
    assert r.total_trials == 0
    assert r.flanker_effect == 0
    assert r.accuracy == 0


def test_flanker_analyze_all_incorrect():
    """全错试次 → 正确率 0，RT 归零。"""
    trials = [{"trial_id": "a", "flanker_type": "congruent", "rt": 500, "correct": False}] * 10
    r = analyze_flanker(trials)
    assert r.accuracy == 0
    assert r.congruent_rt_mean == 0


def test_flanker_analyze_extreme_rt():
    """极端反应时（如 3000ms）不破坏计算。"""
    trials = [
        {"trial_id": "a", "flanker_type": "congruent", "rt": 3000, "correct": True},
        {"trial_id": "b", "flanker_type": "incongruent", "rt": 3400, "correct": True},
    ]
    r = analyze_flanker(trials)
    assert r.flanker_effect == 400


# ==================== 经典实验 · Go/No-Go ====================

def test_gonogo_generate_reproducible():
    """相同 seed → 生成相同试次。"""
    a = generate_gonogo_trials(n_go=20, n_nogo=8, seed=9)
    b = generate_gonogo_trials(n_go=20, n_nogo=8, seed=9)
    assert [(t.stimulus, t.is_go) for t in a] == [(t.stimulus, t.is_go) for t in b]


def test_gonogo_analyze_empty():
    """空试次 → 不崩溃。"""
    r = analyze_gonogo([])
    assert r.total_trials == 0
    assert r.hit_rate == 0
    assert r.false_alarm_rate == 0


def test_gonogo_all_false_alarm():
    """全部 No-Go 误反应 → 虚报率 100%、抑制正确率 0。"""
    trials = [{"trial_id": "a", "is_go": False, "rt": 500, "correct": False}] * 10
    r = analyze_gonogo(trials)
    assert r.false_alarm_rate == 100
    assert r.inhibition_score == 0


def test_gonogo_no_rt_data():
    """No-Go 正确抑制（rt=None）不报错，Go 无数据时反应时归零。"""
    trials = [{"trial_id": "a", "is_go": False, "rt": None, "correct": True}] * 10
    r = analyze_gonogo(trials)
    assert r.false_alarm_rate == 0
    assert r.go_rt_mean == 0


# ==================== 经典实验 · IAT ====================

def test_iat_generate_reproducible():
    """相同 seed → 生成相同试次。"""
    a = generate_iat_trials(n_per_block=10, seed=11)
    b = generate_iat_trials(n_per_block=10, seed=11)
    assert [(t.stimulus, t.block_type, t.correct_answer) for t in a] == \
           [(t.stimulus, t.block_type, t.correct_answer) for t in b]


def test_iat_d_score_positive_when_compatible_faster():
    """相容更快 → D 分数为正。"""
    trials = [
        {"trial_id": "a", "block_type": "compatible", "rt": 500, "correct": True},
        {"trial_id": "b", "block_type": "compatible", "rt": 520, "correct": True},
        {"trial_id": "c", "block_type": "incompatible", "rt": 800, "correct": True},
        {"trial_id": "d", "block_type": "incompatible", "rt": 840, "correct": True},
    ]
    r = analyze_iat(trials)
    assert r.d_score > 0


def test_iat_d_score_negative_when_incompatible_faster():
    """不相容更快 → D 分数为负。"""
    trials = [
        {"trial_id": "a", "block_type": "compatible", "rt": 800, "correct": True},
        {"trial_id": "b", "block_type": "compatible", "rt": 840, "correct": True},
        {"trial_id": "c", "block_type": "incompatible", "rt": 500, "correct": True},
        {"trial_id": "d", "block_type": "incompatible", "rt": 520, "correct": True},
    ]
    r = analyze_iat(trials)
    assert r.d_score < 0


def test_iat_single_block_only():
    """仅一个 block 数据 → D 分数不崩溃。"""
    trials = [
        {"trial_id": "a", "block_type": "compatible", "rt": 600, "correct": True},
        {"trial_id": "b", "block_type": "compatible", "rt": 620, "correct": True},
    ]
    r = analyze_iat(trials)
    assert r.total_trials == 2


# ==================== 风险分级 ====================

def test_risk_extreme_scores_trigger_extreme_and_suicide():
    """全部极端高分 → 最高风险级 + 自杀意念标志。"""
    r = assess_risk(sas_score=100, sds_score=100, phq9_score=27, phq9_q9=3, gad7_score=21)
    assert r.overall_level == "extreme"
    assert r.suicide_risk is True


def test_risk_all_normal_scores():
    """全部低分 → 低风险。"""
    r = assess_risk(sas_score=25, sds_score=25, phq9_score=0, phq9_q9=0, gad7_score=0)
    assert r.overall_level == "low"


def test_risk_empty_inputs_do_not_crash():
    """全部为空 → 不崩溃并给出可解释结果。"""
    r = assess_risk()
    assert r.overall_level in ("low", "moderate", "high", "extreme")


def test_risk_partial_phq9_q9():
    """仅 Q9 高（自杀意念）也应触发 warning_flags。"""
    r = assess_risk(sas_score=30, sds_score=30, phq9_score=5, phq9_q9=2, gad7_score=4)
    assert len(r.warning_flags) > 0


# ==================== 虚拟被试 · 自动诊断 ====================

def test_auto_diagnose_all_18_profiles():
    """18 个剖面全部可生成并可自动诊断，结果结构完整。"""
    for p in PROFILES:
        subj = generate_virtual_subject(p["id"], seed=1)
        result = auto_diagnose(subj)
        assert result["profile_id"] == p["id"]
        assert result["comparison"]["scale_level_match"] in (True, False)
        assert result["scale_diagnosis"]["overall_level"] in ("normal", "mild", "moderate", "severe")


def test_auto_diagnose_reproducible():
    """相同 seed → 相同诊断结果。"""
    a = auto_diagnose(generate_virtual_subject("mild_anxiety", seed=42))
    b = auto_diagnose(generate_virtual_subject("mild_anxiety", seed=42))
    assert a["scale_diagnosis"]["overall_level"] == b["scale_diagnosis"]["overall_level"]
    assert a["emotion_diagnosis"]["emotion"] == b["emotion_diagnosis"]["emotion"]
