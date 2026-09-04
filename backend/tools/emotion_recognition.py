"""
面部情绪识别工具 (EmotionRecognitionTool)
==========================================

基于 DeepFace 深度学习的面部表情识别，输出 7 类基本情绪：
开心、中性、悲伤、愤怒、惊讶、害怕、厌恶。

功能：
- 单帧分析 analyze_frame / analyze_image
- 视频多帧采样 + 概率平均聚合 analyze_video
- 多人脸检测 detect_faces

说明：
- DeepFace 延迟加载，模块导入不阻塞。
- 本轮仅实现面部识别，双模态（前庭振动）融合留待后续迭代。
"""

from __future__ import annotations
import os
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from backend.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)

# DeepFace 情绪映射（英文 -> 中文）
EMOTION_MAP = {
    "happy": "开心",
    "neutral": "中性",
    "sad": "悲伤",
    "angry": "愤怒",
    "surprise": "惊讶",
    "fear": "害怕",
    "disgust": "厌恶",
}

# V/A 映射（7 类情绪，效价/唤醒度 ∈ [-1, 1]）
EMOTION_VA = {
    "开心":   (0.80,  0.60),
    "中性":   (0.00,  0.00),
    "悲伤":   (-0.70, -0.20),
    "愤怒":   (-0.60,  0.80),
    "惊讶":   (0.20,  0.90),
    "害怕":   (-0.40,  0.70),
    "厌恶":   (-0.60,  0.40),
}


def compute_va_from_probs(emotion_probs: Dict[str, float]) -> Tuple[float, float]:
    """
    将 7 类情绪概率分布映射到效价-唤醒度连续空间（设计规范第 1 步）。

    V_face = Σ(p_i × V_i)，A_face = Σ(p_i × A_i)
    即 7 个情绪锚点坐标的「概率加权平均」，而非主导情绪的单一锚点。
    概率分布越分散，加权结果越接近中性原点 (0, 0)。

    Args:
        emotion_probs: 7 类情绪概率分布（英文键: happy/neutral/sad/...）

    Returns:
        (valence, arousal) ∈ [-1, 1]
    """
    if not emotion_probs:
        return 0.0, 0.0

    valence = 0.0
    arousal = 0.0
    total = 0.0
    for en_key, prob in emotion_probs.items():
        cn = EMOTION_MAP.get(en_key)
        if cn is None:
            continue
        v, a = EMOTION_VA.get(cn, (0.0, 0.0))
        valence += float(prob) * v
        arousal += float(prob) * a
        total += float(prob)

    if total <= 0:
        return 0.0, 0.0

    return valence / total, arousal / total


DEFAULT_MODEL = "DeepFace"
DEFAULT_DETECTOR_BACKEND = "opencv"


@dataclass
class FacialEmotionResult:
    """DeepFace 面部情绪分析结果。"""
    emotion: str                                   # 中文主导情绪
    confidence: float                              # 主导情绪置信度 [0,1]
    valence: float                                 # 效价 [-1,1]
    arousal: float                                 # 唤醒度 [-1,1]
    intensity: float                               # 情绪强度 [0,1]
    emotion_probs: Dict[str, float] = field(default_factory=dict)  # 7 类概率分布（英文键）
    face_count: int = 1                            # 检测到的人脸数（聚合时为有效帧数）
    face_locations: List[Tuple[int, int, int, int]] = field(default_factory=list)
    model_used: str = DEFAULT_MODEL
    processing_time_ms: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "emotion": self.emotion,
            "confidence": round(self.confidence, 3),
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "intensity": round(self.intensity, 3),
            "emotion_probs": {EMOTION_MAP.get(k, k): round(v, 3)
                             for k, v in self.emotion_probs.items()},
            "face_count": self.face_count,
            "model_used": self.model_used,
            "processing_time_ms": self.processing_time_ms,
            "error": self.error,
        }


class DeepFaceAnalyzer:
    """基于 DeepFace 的面部表情分析器（延迟加载）。"""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        enforce_detection: bool = False,
        align: bool = True,
        detector_backend: str = DEFAULT_DETECTOR_BACKEND,
    ):
        self.model_name = model_name
        self.enforce_detection = enforce_detection
        self.align = align
        self.detector_backend = detector_backend
        self._deepface_imported = False
        self._deepface_module = None
        self._load_deepface()

    def _load_deepface(self) -> None:
        """延迟加载 DeepFace 模块。"""
        try:
            from deepface import DeepFace
            self._deepface_module = DeepFace
            self._deepface_imported = True
            logger.info(
                f"DeepFace 加载成功，模型：{self.model_name}，检测后端：{self.detector_backend}"
            )
        except ImportError as e:
            logger.warning(f"DeepFace 未安装：{e}")
            self._deepface_imported = False

    @property
    def available(self) -> bool:
        """DeepFace 是否可用（已成功导入）。"""
        return self._deepface_imported

    def analyze_frame(self, frame: np.ndarray) -> Optional[FacialEmotionResult]:
        """
        分析单帧图像的面部表情。

        Args:
            frame: BGR 格式的 numpy 图像数组

        Returns:
            FacialEmotionResult 或 None（未检测到人脸 / 模块未加载）
        """
        if frame is None or frame.size == 0:
            return None

        if not self._deepface_imported:
            return None

        start_time = time.time()

        try:
            result = self._deepface_module.analyze(
                img_path=frame,
                actions=["emotion"],
                enforce_detection=self.enforce_detection,
                silent=True,
                align=self.align,
                detector_backend=self.detector_backend,
            )

            if not result:
                return None
            if isinstance(result, list):
                if len(result) == 0:
                    return None
                face_result = result[0]
                face_count = len(result)
            else:
                face_result = result
                face_count = 1

            if not isinstance(face_result, dict):
                return None

            emotion_probs = face_result.get("emotion") or {}
            if emotion_probs:
                # DeepFace 返回百分制分数（总和≈100），归一化为概率（总和=1），
                # 否则下游熵置信度 / 融合权重 / fused_conf 全部错乱。
                _total = sum(float(v) for v in emotion_probs.values())
                if _total > 1.0:
                    emotion_probs = {
                        k: float(v) / _total for k, v in emotion_probs.items()
                    }
                dominant = face_result.get("dominant_emotion") or max(
                    emotion_probs, key=emotion_probs.get
                )
                emotion_en = str(dominant).lower()
                confidence = float(emotion_probs.get(emotion_en, 0.0))
            else:
                emotion_en = "neutral"
                confidence = 0.0

            emotion_cn = EMOTION_MAP.get(emotion_en, "中性")
            # 效价/唤醒度 = 7 类概率加权平均（设计规范第1步），而非主导情绪单一锚点
            valence, arousal = compute_va_from_probs(emotion_probs)
            processing_time = int((time.time() - start_time) * 1000)

            return FacialEmotionResult(
                emotion=emotion_cn,
                confidence=float(confidence),
                valence=valence,
                arousal=arousal,
                intensity=float(confidence),
                emotion_probs=emotion_probs,
                face_count=face_count,
                model_used=self.model_name,
                processing_time_ms=processing_time,
            )

        except Exception as e:
            logger.warning(f"DeepFace 分析失败：{e}")
            return FacialEmotionResult(
                emotion="中性",
                confidence=0.0,
                valence=0.0,
                arousal=0.0,
                intensity=0.0,
                error=str(e),
            )

    def analyze_image(self, image_path: str) -> Optional[FacialEmotionResult]:
        """从图片文件路径分析单张图片的面部表情。"""
        if not image_path or not os.path.exists(image_path):
            logger.warning(f"图片文件不存在：{image_path}")
            return None
        frame = cv2.imread(image_path)
        if frame is None or frame.size == 0:
            logger.warning(f"无法读取图片：{image_path}")
            return None
        return self.analyze_frame(frame)

    def detect_faces(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """检测图像中所有人脸位置（兼容 list[dict] 与 DataFrame 返回）。"""
        if not self._deepface_imported:
            return []

        try:
            detected = self._deepface_module.detect_faces(
                img_path=frame,
                detector_backend=self.detector_backend,
                enforce_detection=False,
                align=self.align,
            )
            if detected is None:
                return []

            boxes: List[Tuple[int, int, int, int]] = []

            def _to_box(area) -> Tuple[int, int, int, int]:
                x, y, w, h = int(area["x"]), int(area["y"]), int(area["w"]), int(area["h"])
                return (x, y, x + w, y + h)

            # 兼容 list[dict] 和 DataFrame 两种返回类型
            if isinstance(detected, list):
                for item in detected:
                    if not isinstance(item, dict):
                        continue
                    area = item.get("facial_area") or item
                    if isinstance(area, dict):
                        boxes.append(_to_box(area))
            elif hasattr(detected, 'iterrows'):  # DataFrame
                for _, row in detected.iterrows():
                    if "facial_area" in row and isinstance(row["facial_area"], dict):
                        boxes.append(_to_box(row["facial_area"]))
                    elif all(k in row for k in ("x", "y", "w", "h")):
                        boxes.append(_to_box(row))
            return boxes

        except Exception as e:
            logger.warning(f"人脸检测失败：{e}")
            return []


def aggregate_frames(
    results: List[Optional[FacialEmotionResult]],
) -> Optional[FacialEmotionResult]:
    """
    聚合多帧面部情绪结果，返回平滑后的单个聚合结果。

    对多帧的 emotion_probs（7 类 dict）做逐键概率平均（dict-aware，不用 np.mean），
    取平均概率最大的情绪为最终结果；辅助统计各帧 argmax 标签的众数用于交叉校验。

    新增：熵置信度计算 c_face = 1 - H / log(7)
    """
    import math
    valid = [r for r in results if r is not None and r.error == ""]
    if not valid:
        return None

    # 逐键概率平均
    all_keys: set = set()
    for r in valid:
        all_keys.update(r.emotion_probs.keys())
    avg_probs: Dict[str, float] = {}
    for key in all_keys:
        values = [r.emotion_probs.get(key, 0.0) for r in valid]
        avg_probs[key] = float(sum(values) / len(values))

    if avg_probs:
        dominant_en = max(avg_probs, key=avg_probs.get)
        emotion_cn = EMOTION_MAP.get(dominant_en, "中性")
        confidence = avg_probs[dominant_en]
    else:
        emotion_cn = "中性"
        confidence = 0.0

    # 众数交叉校验（仅日志）
    vote_counts: Dict[str, int] = {}
    for r in valid:
        vote_counts[r.emotion] = vote_counts.get(r.emotion, 0) + 1
    majority_cn = max(vote_counts, key=vote_counts.get)
    if majority_cn != emotion_cn:
        logger.info(f"帧间情绪众数({majority_cn})与概率均值({emotion_cn})不一致")

    # 效价/唤醒度 = 7 类概率加权平均（设计规范第1步）
    valence, arousal = compute_va_from_probs(avg_probs)
    total_time = sum(r.processing_time_ms for r in valid)

    return FacialEmotionResult(
        emotion=emotion_cn,
        confidence=float(confidence),
        valence=valence,
        arousal=arousal,
        intensity=float(confidence),
        emotion_probs=dict(avg_probs),
        face_count=len(valid),
        face_locations=list(valid[0].face_locations),
        model_used=valid[0].model_used,
        processing_time_ms=int(total_time),
    )


def compute_facial_confidence_entropy(emotion_probs: Dict[str, float]) -> float:
    """
    计算面部情绪的熵置信度。

    c_face = 1 - H / log(N)，其中 H = -Σ p_i * log(p_i)

    Returns:
        熵置信度 [0,1]，1=完全确定，0=完全不确定
    """
    import math
    n_classes = len(emotion_probs)
    if n_classes == 0:
        return 0.0

    max_entropy = math.log(n_classes)
    entropy = -sum(p * math.log(p) for p in emotion_probs.values() if p > 0)

    return 1 - (entropy / max_entropy) if max_entropy > 0 else 0.0


class EmotionRecognitionTool(BaseTool):
    """
    面部情绪识别工具。

    基于 DeepFace 深度学习的面部表情识别，提供单帧与视频两种入口。
    输出键对齐调用方：facial_emotion / facial_conf / facial_valence / facial_arousal。
    """

    name = "面部情绪识别"
    description = (
        "基于 DeepFace 深度学习的面部表情识别。"
        "输入：图片路径或视频路径。输出：情绪类别、置信度、效价、唤醒度。"
    )

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        detector_backend: str = DEFAULT_DETECTOR_BACKEND,
    ):
        super().__init__()
        self.model_name = model_name
        self.detector_backend = detector_backend
        self._analyzer: Optional[DeepFaceAnalyzer] = None

    def _get_analyzer(self) -> DeepFaceAnalyzer:
        if self._analyzer is None:
            self._analyzer = DeepFaceAnalyzer(
                model_name=self.model_name,
                detector_backend=self.detector_backend,
            )
        return self._analyzer

    def analyze_frame(self, frame: np.ndarray) -> Optional[FacialEmotionResult]:
        """分析单帧图像的情绪。"""
        return self._get_analyzer().analyze_frame(frame)

    def analyze_image(self, image_path: str) -> Optional[FacialEmotionResult]:
        """从图片文件路径分析单张图片。"""
        return self._get_analyzer().analyze_image(image_path)

    def analyze_video(
        self,
        video_path: str,
        sample_fps: int = 5,
    ) -> Tuple[Optional[FacialEmotionResult], int, int]:
        """分析视频，返回 (聚合结果, 抽帧总数, 有效帧数)。"""
        if not os.path.exists(video_path):
            logger.error(f"视频文件不存在：{video_path}")
            return None, 0, 0

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            logger.error(f"无法打开视频：{video_path}")
            return None, 0, 0

        total_fps = cap.get(cv2.CAP_PROP_FPS)
        if total_fps <= 0:
            total_fps = 30.0
        frame_interval = max(1, int(total_fps / sample_fps))

        results: List[Optional[FacialEmotionResult]] = []
        frame_idx = 0
        sampled = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                results.append(self.analyze_frame(frame))
                sampled += 1
            frame_idx += 1

        cap.release()

        valid = [r for r in results if r is not None and r.error == ""]
        return aggregate_frames(results), sampled, len(valid)

    def execute(self, video_path: str = "", **kwargs) -> ToolResult:
        """
        执行面部情绪识别（BaseTool 接口）。

        支持两种输入：
        - image_path: 单张图片路径
        - video_path: 视频路径（多帧聚合）
        """
        image_path = kwargs.get("image_path", "")

        if not video_path and not image_path:
            return ToolResult(success=False, data={}, error="缺少 image_path 或 video_path 参数")

        # 文件存在性检查
        if image_path:
            if not os.path.exists(image_path):
                return ToolResult(success=False, data={}, error=f"图片文件不存在：{image_path}")
        else:
            if not os.path.exists(video_path):
                return ToolResult(success=False, data={}, error=f"视频文件不存在：{video_path}")

        # DeepFace 可用性检查
        analyzer = self._get_analyzer()
        if not analyzer.available:
            return ToolResult(
                success=False, data={},
                error="DeepFace 未安装，请运行：pip install deepface tensorflow",
            )

        try:
            if image_path:
                result = analyzer.analyze_image(image_path)
                frame_count = 1
                valid_frames = 1 if result is not None else 0
            else:
                result, frame_count, valid_frames = self.analyze_video(video_path)

            if result is None:
                return ToolResult(success=False, data={}, error="未检测到有效的人脸情绪")
            if result.error:
                return ToolResult(success=False, data={}, error=f"面部情绪识别失败：{result.error}")

            return ToolResult(
                success=True,
                data={
                    "facial_emotion": result.emotion,
                    "facial_conf": round(float(result.confidence), 3),
                    "facial_valence": round(float(result.valence), 3),
                    "facial_arousal": round(float(result.arousal), 3),
                    "face_count": result.face_count,
                    "frame_count": frame_count,
                    "valid_frames": valid_frames,
                    "model_used": result.model_used,
                    "emotion_probs": {
                        EMOTION_MAP.get(k, k): round(v, 3)
                        for k, v in result.emotion_probs.items()
                    },
                    "confidence_entropy": round(
                        float(compute_facial_confidence_entropy(result.emotion_probs)), 3
                    ),
                    "processing_time_ms": result.processing_time_ms,
                },
            )

        except Exception as e:
            logger.exception("情绪识别失败")
            return ToolResult(success=False, data={}, error=f"情绪识别失败：{str(e)}")


_analyzer: Optional[DeepFaceAnalyzer] = None


def get_analyzer() -> DeepFaceAnalyzer:
    """获取全局 DeepFace 分析器单例。"""
    global _analyzer
    if _analyzer is None:
        _analyzer = DeepFaceAnalyzer()
    return _analyzer
