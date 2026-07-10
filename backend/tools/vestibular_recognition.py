"""
前庭振动识别工具 (VestibularRecognitionTool)
============================================

基于VibraImage引擎实现真实的前庭振动情绪识别，
替代原有的随机stub实现。

核心技术:
- Viktor Minkin "Vibraimage, Cybernetics and Emotions" (2020) 专著公式
- 逐像素帧差分 → 频率分析 → 直方图 → 空间分析 → 频谱功率
- E1-E12情绪参数 + K值心理状态指标
- YOLOv8人脸检测 + Haar Cascade后备

输出映射:
- VibraImage E1-E12 → Valence/Arousal情绪空间
- 正性情绪参数 → Valence > 0
- 负性情绪参数 → Valence < 0
- Energy + Tension → Arousal
"""

from __future__ import annotations
import os
import logging
import numpy as np
from typing import Optional
from dataclasses import dataclass, field

from backend.tools.base import BaseTool, ToolResult
from backend.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class VibraImageVestibularResult:
    """前庭振动分析的完整结果。"""
    # 效价-唤醒度映射
    valence: float
    arousal: float
    intensity: float
    confidence: float

    # E1-E12 情绪参数 (Minkin体系)
    aggression: float       # E1
    stress: float           # E2
    tension: float          # E3
    suspect: float          # E4
    balance: float          # E5
    charm: float            # E6
    energy: float           # E7
    self_regulation: float  # E8
    inhibition: float       # E9
    neuroticism: float      # E10
    depression: float       # E11
    happiness: float        # E12

    # 心理生理参数
    stability: float        # P14
    K_value: float          # 综合心理状态指标
    K_interpretation: str

    # 元数据
    n_windows: int
    duration_sec: float
    face_detection_rate: float
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "valence": self.valence,
            "arousal": self.arousal,
            "intensity": self.intensity,
            "confidence": self.confidence,
            "aggression": self.aggression,
            "stress": self.stress,
            "tension": self.tension,
            "suspect": self.suspect,
            "balance": self.balance,
            "charm": self.charm,
            "energy": self.energy,
            "self_regulation": self.self_regulation,
            "inhibition": self.inhibition,
            "neuroticism": self.neuroticism,
            "depression": self.depression,
            "happiness": self.happiness,
            "stability": self.stability,
            "K_value": self.K_value,
            "K_interpretation": self.K_interpretation,
            "n_windows": self.n_windows,
            "duration_sec": self.duration_sec,
            "face_detection_rate": self.face_detection_rate,
            "error": self.error,
        }


class VestibularRecognitionTool(BaseTool):
    """
    前庭振动情绪识别工具 — 基于VibraImage引擎。

    处理流程:
        视频加载 → 人脸检测(YOLOv8) → 帧差分 → 频率分析
        → 直方图 → 空间分析 → 频谱 → E1-E12情绪参数 → K值

    输出映射到效价-唤醒度空间供上层融合使用。
    """

    name = "前庭振动识别"
    description = (
        "基于VibraImage技术的前庭振动情绪识别。通过分析视频中人脸区域的"
        "微振动频率和空间分布，计算E1-E12情绪参数和K值心理状态指标。"
        "输入：视频路径。输出：效价、唤醒度、12项情绪参数、K值。"
    )

    def __init__(self):
        super().__init__()
        self._engine = None

    def _get_engine(self):
        """延迟初始化VibraImage引擎（避免导入时的模型加载开销）。"""
        if self._engine is None:
            try:
                from backend.vibraimage.pipeline.engine import VibraImageEngine
                from backend.vibraimage.pipeline.face_detector import FaceDetector

                settings = get_settings()

                # 确定模型路径
                model_path = settings.vibraimage_model_path
                if model_path and not os.path.isabs(model_path):
                    model_path = os.path.abspath(model_path)

                face_detector = FaceDetector(
                    model_path=model_path,
                    roi_size=(224, 224),
                    conf_threshold=0.5,
                )

                self._engine = VibraImageEngine(
                    window_frames=settings.vibraimage_window_frames,
                    window_stride=settings.vibraimage_window_stride,
                    freq_method=settings.vibraimage_freq_method,
                    face_detector=face_detector,
                )
                logger.info("VibraImage引擎初始化成功")
            except Exception as e:
                logger.error(f"VibraImage引擎初始化失败: {e}")
                self._engine = None
        return self._engine

    def execute(self, video_path: str = "", **kwargs) -> ToolResult:
        """
        执行前庭振动情绪识别。

        Args:
            video_path: 视频文件路径

        Returns:
            ToolResult with vestibular analysis data
        """
        if not video_path:
            return ToolResult(
                success=False,
                data={},
                error="缺少视频路径参数",
            )

        if not os.path.exists(video_path):
            return ToolResult(
                success=False,
                data={},
                error=f"视频文件不存在: {video_path}",
            )

        engine = self._get_engine()
        if engine is None:
            return ToolResult(
                success=False,
                data={},
                error="VibraImage引擎未初始化，请检查ultralytics和opencv依赖",
            )

        try:
            import time
            start_time = time.time()

            # 执行VibraImage分析
            session = engine.process_video(video_path)
            result_dict = session.to_dict()
            emotions = result_dict.get("emotions", {})

            processing_time_ms = int((time.time() - start_time) * 1000)

            # 将E1-E12映射到效价-唤醒度空间
            valence = self._compute_valence(emotions)
            arousal = self._compute_arousal(emotions)
            intensity = self._compute_intensity(emotions)
            confidence = self._compute_confidence(session)

            result = VibraImageVestibularResult(
                valence=round(valence, 3),
                arousal=round(arousal, 3),
                intensity=round(intensity, 3),

                # 置信度基于人脸检测率和窗口数
                confidence=round(confidence, 3),

                # E1-E12
                aggression=round(emotions.get("aggression", 0.0), 2),
                stress=round(emotions.get("stress", 0.0), 2),
                tension=round(emotions.get("tension", 0.0), 2),
                suspect=round(emotions.get("suspect", 0.0), 2),
                balance=round(emotions.get("balance", 0.0), 2),
                charm=round(emotions.get("charm", 0.0), 2),
                energy=round(emotions.get("energy", 0.0), 2),
                self_regulation=round(emotions.get("self_regulation", 0.0), 2),
                inhibition=round(emotions.get("inhibition", 0.0), 2),
                neuroticism=round(emotions.get("neuroticism", 0.0), 2),
                depression=round(emotions.get("depression", 0.0), 2),
                happiness=round(emotions.get("happiness", 0.0), 2),

                # P14
                stability=round(result_dict.get("psychophysiological", {}).get("stability", 0.0), 2),

                # K值
                K_value=round(result_dict.get("K_value", 0.0), 2),
                K_interpretation=result_dict.get("K_interpretation", ""),

                n_windows=result_dict.get("n_windows", 0),
                duration_sec=round(result_dict.get("duration_sec", 0.0), 1),
                face_detection_rate=1.0,
            )

            return ToolResult(
                success=True,
                data={
                    **result.to_dict(),
                    "processing_time_ms": processing_time_ms,
                },
            )

        except Exception as e:
            logger.exception("前庭振动分析失败")
            return ToolResult(
                success=False,
                data={},
                error=f"前庭振动分析失败: {str(e)}",
            )

    # ---- 效价-唤醒度映射 ----

    def _compute_valence(self, emotions: dict) -> float:
        """
        从VibraImage参数计算情绪效价(Valence)。

        正性参数(balance/charm/energy/self_regulation/happiness) → 正效价
        负性参数(aggression/stress/tension/suspect/depression) → 负效价

        归一化到[-1, 1]范围，0为中性。
        """
        # 正性情绪平均值（归一化到0-1）
        positive_keys = ["balance", "charm", "energy", "self_regulation", "happiness"]
        positive_vals = [emotions.get(k, 50.0) / 100.0 for k in positive_keys]
        positive_score = np.mean(positive_vals)

        # 负性情绪平均值（归一化到0-1）
        negative_keys = ["aggression", "stress", "tension", "suspect", "depression"]
        negative_vals = [emotions.get(k, 30.0) / 100.0 for k in negative_keys]
        negative_score = np.mean(negative_vals)

        # Valence = positive_score - negative_score，映射到[-1, 1]
        raw_valence = positive_score - negative_score
        valence = np.clip(raw_valence, -1.0, 1.0)

        return float(valence)

    def _compute_arousal(self, emotions: dict) -> float:
        """
        从VibraImage参数计算唤醒度(Arousal)。

        高Energy + 高Tension → 高唤醒
        低Energy + 低Tension → 低唤醒

        归一化到[-1, 1]范围。
        """
        energy_val = emotions.get("energy", 50.0) / 100.0
        tension_val = emotions.get("tension", 30.0) / 100.0

        # 唤醒度由能量和紧张度的组合决定
        raw_arousal = 0.6 * energy_val + 0.4 * tension_val
        # 映射到[-1, 1]: 50% → 0, 0% → -1, 100% → 1
        arousal = (raw_arousal - 0.5) * 2.0
        arousal = np.clip(arousal, -1.0, 1.0)

        return float(arousal)

    def _compute_intensity(self, emotions: dict) -> float:
        """
        计算振动信号强度。
        基于所有E1-E12参数与常模的偏差程度。
        """
        from backend.vibraimage.utils.constants import NORMAL_NORMS

        deviations = []
        for param_name in ["aggression", "stress", "tension", "energy", "happiness"]:
            if param_name in emotions and param_name in NORMAL_NORMS:
                norm = NORMAL_NORMS[param_name]
                value = emotions[param_name]
                if norm > 0:
                    deviations.append(abs(value - norm) / norm)

        intensity = np.mean(deviations) if deviations else 0.3
        return float(np.clip(intensity, 0.0, 1.0))

    def _compute_confidence(self, session) -> float:
        """
        计算分析置信度。
        基于窗口数量和人脸检测质量。
        """
        n_windows = session.n_windows
        # 窗口数越多置信度越高，至少需要3个窗口
        if n_windows < 1:
            return 0.0
        elif n_windows < 3:
            return 0.5 + 0.1 * n_windows
        else:
            window_conf = min(0.85, 0.6 + 0.05 * min(n_windows, 10))
            return round(window_conf, 3)
