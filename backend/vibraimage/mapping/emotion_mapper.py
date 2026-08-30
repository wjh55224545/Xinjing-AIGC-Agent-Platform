"""
情绪映射引擎 — E1-E12 → 效价/唤醒度/强度 → 10类情绪。

三阶段演进:
    1. 规则加权映射（当前，零数据启动）
    2. LightGBM多输出（积累500+标注后）
    3. 轻量MLP→ONNX（积累10K+标注后）

参考: VCE专著(Minkin, 2020)各参数定义及心理学语义
"""

import yaml
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class EmotionResult:
    """单次情绪映射结果。"""
    valence: float             # 效价 [0, 1]
    arousal: float             # 唤醒度 [0, 1]
    intensity: float           # 情绪强度 [0, 1]
    emotion_id: int            # 情绪类别编号 0-10 (0=中性/未分类)
    emotion_label: str         # 中文标签
    emotion_label_en: str      # 英文标签
    raw_scores: Dict[str, float] = field(default_factory=dict)  # 各情绪距离分数

    def to_dict(self) -> dict:
        return {
            'valence': self.valence,
            'arousal': self.arousal,
            'intensity': self.intensity,
            'emotion_id': self.emotion_id,
            'emotion_label': self.emotion_label,
            'emotion_label_en': self.emotion_label_en,
        }


class EmotionMapper:
    """
    E1-E12 → 效价/唤醒度 → 10类情绪映射器。

    工作流程:
        1. 归一化 E1-E12 到 [0, 1]
        2. 加权求和 → 效价/唤醒度（含K值微调）
        3. sigmoid 压缩
        4. 计算强度
        5. 在效价-唤醒度2D空间中匹配10类情绪区域

    Parameters
    ----------
    weights_path : str or Path, optional
        权重YAML路径。None则使用默认权重。
    """

    # E参数键名映射（兼容不同命名风格）
    _KEY_MAP = {
        'aggression': 'aggression', 'E1': 'aggression',
        'stress': 'stress', 'E2': 'stress',
        'tension': 'tension', 'E3': 'tension',
        'suspicious': 'suspicious', 'E4': 'suspicious',
        'balance': 'balance', 'E5': 'balance',
        'charm': 'charm', 'E6': 'charm',
        'energy': 'energy', 'E7': 'energy',
        'self_regulation': 'self_regulation', 'E8': 'self_regulation',
        'inhibition': 'inhibition', 'E9': 'inhibition',
        'neuroticism': 'neuroticism', 'E10': 'neuroticism',
        'depression': 'depression', 'E11': 'depression',
        'happiness': 'happiness', 'E12': 'happiness',
    }
    _PARAM_ORDER = [
        'aggression', 'stress', 'tension', 'suspicious',
        'balance', 'charm', 'energy', 'self_regulation',
        'inhibition', 'neuroticism', 'depression', 'happiness',
    ]

    # 温度参数：sigmoid(x/T)，T越小V/A分布越广。
    # T=2.5 → sigmoid(±6/2.5)=sigmoid(±2.4) ≈ [0.08, 0.92]，更好的类别分离。
    TEMPERATURE = 2.5

    def __init__(self, weights_path: Optional[Path] = None, temperature: float = 2.5):
        if weights_path is None:
            weights_path = Path(__file__).parent / 'weights.yaml'
        self.weights_path = Path(weights_path)
        self.TEMPERATURE = temperature
        self._load_weights()
        self._load_norms()

    def _load_weights(self):
        with open(self.weights_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        w = config['weights']
        self.w_valence = np.array([w['valence'][p] for p in self._PARAM_ORDER])
        self.w_arousal = np.array([w['arousal'][p] for p in self._PARAM_ORDER])

        self.emotion_regions = config['emotion_regions']
        self.default_emotion = config.get('default_emotion', '中性')
        self.default_emotion_en = config.get('default_emotion_en', 'neutral')

    def _load_norms(self):
        """从项目常量加载常模均值和标准差，用于z-score归一化。"""
        from ..utils.constants import NORMAL_NORMS, NORMAL_SDS
        self.norm_means = np.array([NORMAL_NORMS[p] for p in self._PARAM_ORDER])
        self.norm_sds = np.array([NORMAL_SDS[p] for p in self._PARAM_ORDER])

    def _standardize_12d(self, scores: Dict[str, float]) -> np.ndarray:
        """将E1-E12字典转为z-score（基于VCE常模均值和SD）。"""
        raw = np.array([scores.get(self._KEY_MAP.get(p, p), self.norm_means[i])
                        for i, p in enumerate(self._PARAM_ORDER)])
        return (raw - self.norm_means) / self.norm_sds

    def compute_valence_arousal(
        self,
        e_params: Dict[str, float],
        K: float = 0.0,
    ) -> Tuple[float, float, float]:
        """
        计算效价、唤醒度、强度。

        Parameters
        ----------
        e_params : dict
            E1-E12参数字典。键名支持 'aggression'/'E1' 等格式。
        K : float
            K值（心理不对称系数），用于微调效价。[−5, 5]

        Returns
        -------
        (valence, arousal, intensity) : (float, float, float)
        """
        x = self._standardize_12d(e_params)

        # 加权求和 (z-score × weight)
        v_raw = np.dot(x, self.w_valence)
        a_raw = np.dot(x, self.w_arousal)

        # K值微调：K正值→右脑激活优势→负性情绪偏多→效价略降
        # K范围[-5,5]，影响控制在[-0.08, 0.08] (z-score尺度)
        v_raw -= np.clip(K * 0.016, -0.08, 0.08)

        # sigmoid 压缩，temperature防止极端饱和
        valence = 1.0 / (1.0 + np.exp(-v_raw / self.TEMPERATURE))
        arousal = 1.0 / (1.0 + np.exp(-a_raw / self.TEMPERATURE))

        # 强度 = 唤醒度 × 效价偏离中性的程度
        intensity = arousal * abs(valence - 0.5) * 2.0

        return float(valence), float(arousal), float(intensity)

    def classify_emotion(
        self,
        valence: float,
        arousal: float,
    ) -> Tuple[int, str, str, Dict[str, float]]:
        """
        将效价-唤醒度坐标映射到10类情绪。

        匹配策略：计算到每个情绪区域中心的原始欧氏距离，
        取最近的情绪类别。与region是否包含该点无关。

        Returns
        -------
        (emotion_id, label_zh, label_en, distances) : (int, str, str, dict)
        """
        best_label = self.default_emotion
        best_label_en = self.default_emotion_en
        best_id = 0
        best_dist = float('inf')
        distances = {}

        for eid_str, region in self.emotion_regions.items():
            v_range = region['valence']
            a_range = region['arousal']

            v_center = (v_range[0] + v_range[1]) / 2
            a_center = (a_range[0] + a_range[1]) / 2

            dist = np.sqrt((valence - v_center)**2 + (arousal - a_center)**2)

            in_region = (
                v_range[0] <= valence <= v_range[1]
                and a_range[0] <= arousal <= a_range[1]
            )

            distances[region['label']] = {'distance': dist, 'in_region': in_region}

            if dist < best_dist:
                best_dist = dist
                best_label = region['label']
                best_label_en = region['label_en']
                best_id = int(eid_str.split('_')[0]) if eid_str[0].isdigit() else 0

        if best_dist > 0.5:
            best_label = self.default_emotion
            best_label_en = self.default_emotion_en
            best_id = 0

        return best_id, best_label, best_label_en, distances

    def map(self, e_params: Dict[str, float], K: float = 0.0) -> EmotionResult:
        """
        完整映射: E1-E12 → 效价/唤醒度/强度 → 情绪类别。

        Parameters
        ----------
        e_params : dict
            E1-E12参数字典。
        K : float
            K值。

        Returns
        -------
        EmotionResult
        """
        valence, arousal, intensity = self.compute_valence_arousal(e_params, K)
        eid, label, label_en, distances = self.classify_emotion(valence, arousal)

        return EmotionResult(
            valence=valence,
            arousal=arousal,
            intensity=intensity,
            emotion_id=eid,
            emotion_label=label,
            emotion_label_en=label_en,
            raw_scores=distances,
        )


def load_default_mapper() -> EmotionMapper:
    """加载默认权重配置的映射器。"""
    return EmotionMapper()
