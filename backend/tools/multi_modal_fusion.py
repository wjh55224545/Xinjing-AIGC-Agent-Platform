"""
多模态情绪融合模块 (MultiModalFusion)
======================================

面部情绪识别 + 前庭振动情绪识别的自适应融合。

融合策略:
1. 置信度计算:
   - 面部：熵归一化 c_face = 1 - H / log(7)，H 为 7 类情绪概率的香农熵
   - 前庭：窗口方差置信度 c_vi = 1 - mean(sigma_E) / max_sigma

2. 加权融合:
   w_vi = c_vi / (c_vi + c_face)
   w_face = c_face / (c_vi + c_face)

   V_fused = w_vi * V_vi + w_face * V_face
   A_fused = w_vi * A_vi + w_face * A_face
   conf_fused = (c_vi + c_face) / 2

3. 输出:
   - fused_valence, fused_arousal: [-1, 1] 尺度
   - fused_conf: [0, 1]
   - fused_emotion: 可选，通过查表得到 7 类或 10 类情绪标签
"""

from __future__ import annotations
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass


@dataclass
class FusionResult:
    """融合结果。"""
    fused_valence: float          # [-1, 1]
    fused_arousal: float          # [-1, 1]
    fused_conf: float             # [0, 1]
    fused_emotion_7: str          # 7 类情绪标签（基于面部分类体系）
    fused_emotion_10: str         # 10 类情绪标签（基于 VibraImage 体系）

    # 各模态置信度和权重
    c_face: float                 # 面部熵置信度
    c_vi: float                   # 前庭窗口方差置信度
    w_face: float                 # 面部权重
    w_vi: float                   # 前庭权重

    # 原始输入（用于调试）
    facial_valence: float
    facial_arousal: float
    vestibular_valence: float
    vestibular_arousal: float

    # 模态一致性复核（设计规范第5步）
    modal_distance: float         # 两模态原始 V-A 预测的欧氏距离 d
    modal_inconsistent: bool      # d > MODAL_DISTANCE_THRESHOLD 时为 True

    def to_dict(self) -> dict:
        return {
            "fused_valence": round(self.fused_valence, 3),
            "fused_arousal": round(self.fused_arousal, 3),
            "fused_conf": round(self.fused_conf, 3),
            "fused_emotion_7": self.fused_emotion_7,
            "fused_emotion_10": self.fused_emotion_10,
            "c_face": round(self.c_face, 3),
            "c_vi": round(self.c_vi, 3),
            "w_face": round(self.w_face, 3),
            "w_vi": round(self.w_vi, 3),
            "facial_valence": round(self.facial_valence, 3),
            "facial_arousal": round(self.facial_arousal, 3),
            "vestibular_valence": round(self.vestibular_valence, 3),
            "vestibular_arousal": round(self.vestibular_arousal, 3),
            "modal_distance": round(self.modal_distance, 3),
            "modal_inconsistent": self.modal_inconsistent,
        }


# 7 类情绪标签（DeepFace 体系，中文）
EMOTION_7_CLASSES = ["开心", "中性", "悲伤", "愤怒", "惊讶", "害怕", "厌恶"]

# 7 类情绪的 V/A 坐标参考点（用于分类）
EMOTION_7_VA = {
    "开心":   (0.80,  0.60),
    "中性":   (0.00,  0.00),
    "悲伤":   (-0.70, -0.20),
    "愤怒":   (-0.60,  0.80),
    "惊讶":   (0.20,  0.90),
    "害怕":   (-0.40,  0.70),
    "厌恶":   (-0.60,  0.40),
}


class MultiModalEmotionFuser:
    """
    双模态情绪融合器（面部 + 前庭）。

    使用置信度自适应加权融合，置信度计算方式：
    - 面部：熵归一化
    - 前庭：窗口间方差
    """

    # 前庭窗口方差置信度的最大标准差参考值（根据常模 SD 的 50% 设定）
    MAX_STD_FOR_CONFIDENCE = 15.0

    # 模态一致性复核阈值（设计规范第5步）: 两模态 V-A 欧氏距离超过此值 → 需复核
    MODAL_DISTANCE_THRESHOLD = 0.5

    def __init__(self):
        pass

    def compute_facial_confidence_entropy(
        self,
        emotion_probs: Dict[str, float],
    ) -> float:
        """
        计算面部情绪的熵置信度。

        c_face = 1 - H / log(N)，其中 H = -Σ p_i * log(p_i)

        Args:
            emotion_probs: 7 类情绪概率分布字典

        Returns:
            熵置信度 [0,1]，1=完全确定，0=完全不确定
        """
        if not emotion_probs:
            return 0.0

        # 类别数固定为输入概率分布的键数（DeepFace 体系为 7 类）
        n_classes = len(emotion_probs)
        if n_classes == 0:
            return 0.0

        # 计算香农熵（过滤零概率，log(0) 无定义）
        probs = [p for p in emotion_probs.values() if p > 0]
        entropy = -sum(p * math.log(p) for p in probs)

        # 归一化到最大熵 log(N)，N 为类别总数（非零概率数）
        max_entropy = math.log(n_classes)

        if max_entropy <= 0:
            return 0.0

        return 1.0 - (entropy / max_entropy)

    def compute_vestibular_confidence_variance(
        self,
        window_results: List[Dict],
    ) -> float:
        """
        计算前庭情绪的窗口方差置信度。

        基于 E1-E12 各参数的窗口间标准差，标准差越小表示信号越稳定。

        c_vi = 1 - mean(sigma_E) / max_std

        Args:
            window_results: 每个窗口的 E1-E12 参数列表

        Returns:
            窗口方差置信度 [0,1]，1=非常稳定，0=极不稳定
        """
        if not window_results or len(window_results) < 2:
            # 窗口数不足，返回默认置信度
            return 0.5 if window_results else 0.0

        # E1-E12 参数名映射
        param_keys = [
            "aggression", "stress", "tension", "suspect",
            "balance", "charm", "energy", "self_regulation",
            "inhibition", "neuroticism", "depression", "happiness"
        ]

        stds = []
        for param in param_keys:
            values = [w.get(param, 0.0) for w in window_results]
            if values:
                # 计算标准差
                mean_val = sum(values) / len(values)
                variance = sum((v - mean_val) ** 2 for v in values) / len(values)
                std = math.sqrt(variance)
                stds.append(std)

        if not stds:
            return 0.0

        # 平均标准差
        mean_std = sum(stds) / len(stds)

        # 归一化到置信度
        confidence = 1.0 - (mean_std / self.MAX_STD_FOR_CONFIDENCE)

        return max(0.0, min(1.0, confidence))

    def classify_emotion_7class(
        self,
        valence: float,
        arousal: float,
    ) -> str:
        """
        将 V/A 坐标分类为 7 类情绪（DeepFace 体系）。

        Args:
            valence: 效价 [-1, 1]
            arousal: 唤醒度 [-1, 1]

        Returns:
            7 类情绪标签之一
        """
        best_label = "中性"
        best_dist = float('inf')

        for emotion, (v_ref, a_ref) in EMOTION_7_VA.items():
            dist = math.sqrt((valence - v_ref) ** 2 + (arousal - a_ref) ** 2)
            if dist < best_dist:
                best_dist = dist
                best_label = emotion

        return best_label

    def classify_emotion_10class(
        self,
        valence: float,
        arousal: float,
    ) -> str:
        """
        将 V/A 坐标分类为 10 类情绪（VibraImage 体系）。

        从 weights.yaml 中读取 emotion_regions 进行匹配。

        Args:
            valence: 效价 [-1, 1]
            arousal: 唤醒度 [-1, 1]

        Returns:
            10 类情绪标签之一
        """
        # 加载权重配置中的 emotion_regions
        from backend.vibraimage.mapping.emotion_mapper import EmotionMapper

        mapper = EmotionMapper()

        # 使用 mapper 进行分类
        eid, label, label_en, distances = mapper.classify_emotion(valence, arousal)

        return label

    def fuse(
        self,
        facial_result: Dict,
        vestibular_result: Dict,
    ) -> Optional[FusionResult]:
        """
        执行双模态融合。

        Args:
            facial_result: 面部情绪结果，包含:
                - facial_valence: float
                - facial_arousal: float
                - emotion_probs: Dict[str, float] (7 类概率)

            vestibular_result: 前庭情绪结果，包含:
                - valence: float
                - arousal: float
                - window_results: List[Dict] (E1-E12 时间序列，可选)
                - K_value: float (可选)

        Returns:
            FusionResult 或 None（如果任一结果为空）
        """
        # 提取面部数据
        facial_valence = facial_result.get("facial_valence", 0.0)
        facial_arousal = facial_result.get("facial_arousal", 0.0)
        emotion_probs = facial_result.get("emotion_probs", {})

        # 转换 emotion_probs 键名（中文->英文）
        va_keys_zh_to_en = {
            "开心": "happy", "中性": "neutral", "悲伤": "sad",
            "愤怒": "angry", "惊讶": "surprise", "害怕": "fear", "厌恶": "disgust"
        }
        emotion_probs_en = {}
        for k, v in emotion_probs.items():
            en_key = va_keys_zh_to_en.get(k, k)
            emotion_probs_en[en_key] = v

        # 提取前庭数据
        vestibular_valence = vestibular_result.get("valence", 0.0)
        vestibular_arousal = vestibular_result.get("arousal", 0.0)
        window_results = vestibular_result.get("window_results", [])

        # 计算置信度
        c_face = self.compute_facial_confidence_entropy(emotion_probs_en)
        c_vi = self.compute_vestibular_confidence_variance(window_results)

        # 处理置信度为零的情况
        if c_face + c_vi < 0.001:
            # 两者置信度都极低，返回中间值
            c_face = 0.5
            c_vi = 0.5

        # 计算权重
        total_conf = c_face + c_vi
        w_face = c_face / total_conf
        w_vi = c_vi / total_conf

        # 加权融合
        fused_valence = w_vi * vestibular_valence + w_face * facial_valence
        fused_arousal = w_vi * vestibular_arousal + w_face * facial_arousal

        # 融合置信度（取平均值）
        fused_conf = (c_face + c_vi) / 2

        # 分类情绪标签
        fused_emotion_7 = self.classify_emotion_7class(fused_valence, fused_arousal)
        fused_emotion_10 = self.classify_emotion_10class(fused_valence, fused_arousal)

        # 模态一致性复核（设计规范第5步）:
        # 两模态原始 V-A 预测的欧氏距离 d，超过阈值时标记"模态不一致，需复核"
        modal_distance = math.sqrt(
            (facial_valence - vestibular_valence) ** 2
            + (facial_arousal - vestibular_arousal) ** 2
        )
        modal_inconsistent = modal_distance > self.MODAL_DISTANCE_THRESHOLD

        return FusionResult(
            fused_valence=fused_valence,
            fused_arousal=fused_arousal,
            fused_conf=fused_conf,
            fused_emotion_7=fused_emotion_7,
            fused_emotion_10=fused_emotion_10,
            c_face=c_face,
            c_vi=c_vi,
            w_face=w_face,
            w_vi=w_vi,
            facial_valence=facial_valence,
            facial_arousal=facial_arousal,
            vestibular_valence=vestibular_valence,
            vestibular_arousal=vestibular_arousal,
            modal_distance=modal_distance,
            modal_inconsistent=modal_inconsistent,
        )


def create_fusion_result_for_db(
    fusion_result: FusionResult,
) -> Dict:
    """
    将融合结果转换为数据库存储格式。

    Args:
        fusion_result: FusionResult 对象

    Returns:
        适合写入数据库的字典
    """
    return {
        "fused_emotion": fusion_result.fused_emotion_10,  # 使用 10 类标签
        "fused_conf": fusion_result.fused_conf,
        "fused_valence": fusion_result.fused_valence,
        "fused_arousal": fusion_result.fused_arousal,
        "fusion_c_face": fusion_result.c_face,
        "fusion_c_vi": fusion_result.c_vi,
        "fusion_w_face": fusion_result.w_face,
        "fusion_w_vi": fusion_result.w_vi,
    }
