"""
VibraImage 主引擎。

端到端流水线:
    视频加载 → 人脸检测 → 帧差分 → 频率分析 → 直方图 → 空间分析
    → 频谱分布 → 情绪参数计算 → 结果输出

滑动窗口模式:
    - 每 window_frames 帧为一个处理窗口
    - stride 控制窗口重叠
    - 窗口间统计用于计算时间依赖参数(E5, E8, E10)

参考: VCE.pdf 第2-4章, VibraLite产品说明书 p43 (100帧处理窗口)
"""

import cv2
import numpy as np
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
import logging

from ..core.frame_differencer import FrameDifferencer
from ..core.frequency_analyzer import PerPixelFrequencyAnalyzer, FrequencyResult
from ..core.histogram import FrequencyHistogram, HistogramStats
from ..core.spatial_analyzer import SpatialAnalyzer, PerLineStats
from ..core.spectral import SpectralPowerDistribution
from ..emotions.primary import compute_primary_emotions
from ..emotions.derived import (
    compute_suspect, compute_balance, compute_charm,
    compute_energy, compute_self_regulation,
    compute_inhibition, compute_neuroticism,
    compute_depression, compute_happiness,
    compute_information_efficiency, compute_energy_characteristic,
)
from ..emotions.psychophysiological import (
    compute_stability, compute_k_value, interpret_k,
)
from ..utils.constants import (
    FREQ_BAND, DEFAULT_FRAME_RATE, DEFAULT_WINDOW_FRAMES,
    DEFAULT_WINDOW_STRIDE, FACE_ROI_SIZE, FREQ_BINS,
    TENSION_HIGH_FREQ_THRESHOLD, DEPRESSION_SIGMA_OFFSET,
    NORMAL_NORMS, STANDARDIZATION_FACTORS, PARAM_NAMES_ZH,
)
from .face_detector import FaceDetector

logger = logging.getLogger(__name__)


@dataclass
class WindowResult:
    """单个时间窗口的分析结果。"""
    timestamp_sec: float
    window_id: int

    # 基础参数 E1-E3
    aggression: float
    stress: float
    tension: float

    # 派生参数 (每窗口计算的值)
    suspect: float          # E4 = (E1+E2+E3)/3
    energy: float           # E7 (可从单窗口直方图计算)
    depression: float       # E11 (可从单窗口直方图计算)

    # 频率直方图统计
    hist_stats: HistogramStats = field(repr=False)

    # 空间分析
    per_line_stats: Optional[PerLineStats] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {
            'window_id': self.window_id,
            'timestamp_sec': self.timestamp_sec,
            'aggression': self.aggression,
            'stress': self.stress,
            'tension': self.tension,
            'suspect': self.suspect,
            'energy': self.energy,
            'depression': self.depression,
            'hist_M': self.hist_stats.M,
            'hist_sigma': self.hist_stats.sigma,
            'hist_F_max': self.hist_stats.F_max,
            'hist_count_max': self.hist_stats.count_max,
        }


@dataclass
class SessionResult:
    """完整会话的分析结果 (所有窗口的聚合)。"""
    window_results: List[WindowResult]

    # 时间聚合参数
    inhibition: float       # E9 (基于所有窗口的F1平均周期)
    neuroticism: float      # E10 = 10 × σ(E9各窗口)

    # 全时段参数
    balance: float          # E5 (基于所有窗口的情绪参数变异性)
    charm: float            # E6 (基于所有窗口的空间分析聚合)
    self_regulation: float  # E8 (基于E5和E6的稳定性)
    happiness: float        # E12 (基于全时段信息效能和能量)

    # 心理生理参数
    stability: float        # P14

    # K值
    K_value: float

    # 叠加统计
    duration_sec: float
    n_windows: int

    def to_dict(self) -> dict:
        windows = [w.to_dict() for w in self.window_results]
        return {
            'n_windows': self.n_windows,
            'duration_sec': self.duration_sec,
            'emotions': {
                'aggression': float(np.mean([w.aggression for w in self.window_results])),
                'stress': float(np.mean([w.stress for w in self.window_results])),
                'tension': float(np.mean([w.tension for w in self.window_results])),
                'suspect': float(np.mean([w.suspect for w in self.window_results])),
                'balance': self.balance,
                'charm': self.charm,
                'energy': float(np.mean([w.energy for w in self.window_results])),
                'self_regulation': self.self_regulation,
                'inhibition': self.inhibition,
                'neuroticism': self.neuroticism,
                'depression': float(np.mean([w.depression for w in self.window_results])),
                'happiness': self.happiness,
            },
            'psychophysiological': {
                'stability': self.stability,
            },
            'K_value': self.K_value,
            'K_interpretation': interpret_k(self.K_value),
            'windows': windows,
        }

    def to_json(self, path: str):
        """保存结果为JSON。"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)


class VibraImageEngine:
    """
    VibraImage主引擎。

    完整流水线:
    1. 加载视频
    2. 人脸检测 + ROI裁剪
    3. 滑动窗口处理:
       a. 帧差分
       b. 逐像素频率分析
       c. 频率直方图
       d. 空间分析
       e. 频谱功率分布
       f. E1-E12参数计算
    4. 窗口间聚合统计
    5. 返回SessionResult

    Parameters
    ----------
    window_frames : int, default=100
        每个分析窗口的帧数 (约3.3秒@30fps)。
    window_stride : int, default=50
        窗口滑动步长 (50%重叠)。
    frame_rate : float, default=30.0
        输入帧率 [fps]。
    freq_method : str, default='zerocross'
        频率分析方法 ('zerocross' or 'fft')。
    face_detector : FaceDetector or None
        人脸检测器。None则自动创建。
    """

    def __init__(
        self,
        window_frames: int = DEFAULT_WINDOW_FRAMES,
        window_stride: int = DEFAULT_WINDOW_STRIDE,
        frame_rate: float = DEFAULT_FRAME_RATE,
        freq_method: str = 'zerocross',
        face_detector: Optional[FaceDetector] = None,
    ):
        self.window_frames = window_frames
        self.window_stride = window_stride
        self.frame_rate = frame_rate

        # 初始化核心模块
        self.frame_differencer = FrameDifferencer()
        self.freq_analyzer = PerPixelFrequencyAnalyzer(
            frame_rate=frame_rate,
            freq_band=FREQ_BAND,
            method=freq_method,
        )
        self.histogram = FrequencyHistogram(
            freq_band=FREQ_BAND,
            n_bins=FREQ_BINS,
        )
        self.spatial_analyzer = SpatialAnalyzer()
        self.spectral = SpectralPowerDistribution(
            frame_rate=frame_rate,
            freq_band=FREQ_BAND,
            high_freq_threshold=TENSION_HIGH_FREQ_THRESHOLD,
        )

        # 人脸检测
        self.face_detector = face_detector or FaceDetector()

    def process_video(
        self,
        video_path: str,
        start_time: float = 0.0,
        duration: Optional[float] = None,
    ) -> SessionResult:
        """
        处理视频文件，返回完整情绪分析结果。

        Parameters
        ----------
        video_path : str
            视频文件路径。
        start_time : float
            开始时间 [s] (跳过前N秒)。
        duration : float or None
            处理时长 [s]。None表示处理全部。

        Returns
        -------
        result : SessionResult
            完整的分析结果。
        """
        # 1. 加载视频
        frames, actual_fps = self._load_video(video_path, start_time, duration)
        if actual_fps > 0:
            self.frame_rate = actual_fps
            self.freq_analyzer.frame_rate = actual_fps

        logger.info(f"加载视频: {video_path}, {len(frames)}帧, {actual_fps}fps")

        if len(frames) < self.window_frames:
            logger.warning(
                f"视频帧数({len(frames)})少于窗口大小({self.window_frames})，"
                f"将使用全部帧"
            )

        # 2. 人脸检测 + ROI裁剪
        face_frames, bboxes = self.face_detector.detect_faces_in_video(frames)
        logger.info(f"人脸检测完成: {sum(1 for b in bboxes if b is not None)}/{len(bboxes)} 帧检测到人脸")

        # 3. 滑动窗口处理
        window_results = self._process_windows(face_frames)

        if not window_results:
            raise ValueError("未生成任何窗口结果")

        # 4. 时间聚合分析
        session = self._aggregate_results(window_results)

        logger.info(f"分析完成: {session.n_windows}个窗口, 时长{session.duration_sec:.1f}s")
        logger.info(f"K值: {session.K_value:.2f} — {interpret_k(session.K_value)}")

        return session

    def process_frames(
        self,
        frames: np.ndarray,
    ) -> SessionResult:
        """
        直接处理帧数组 (跳过视频加载和人脸检测)。

        Parameters
        ----------
        frames : np.ndarray, shape (N, H, W)
            灰度人脸ROI帧序列。

        Returns
        -------
        result : SessionResult
        """
        window_results = self._process_windows(frames)
        if not window_results:
            raise ValueError("未生成任何窗口结果")
        return self._aggregate_results(window_results)

    def _load_video(
        self,
        video_path: str,
        start_time: float = 0.0,
        duration: Optional[float] = None,
    ) -> Tuple[np.ndarray, float]:
        """加载视频帧。"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise IOError(f"无法打开视频: {video_path}")

        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        # 跳帧
        if start_time > 0:
            start_frame = int(start_time * actual_fps)
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

        # 读取帧
        frames = []
        max_frames = int(duration * actual_fps) if duration else None

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frames.append(frame)
            if max_frames and len(frames) >= max_frames:
                break

        cap.release()
        return np.array(frames), actual_fps

    def _process_windows(self, frames: np.ndarray) -> List[WindowResult]:
        """滑动窗口处理。"""
        results = []
        n_frames = len(frames)
        window_id = 0

        for start in range(0, n_frames - self.window_frames + 1, self.window_stride):
            end = start + self.window_frames
            window_frames = frames[start:end]

            try:
                result = self._process_single_window(window_frames, window_id)
                result.timestamp_sec = start / self.frame_rate
                results.append(result)
                window_id += 1
            except Exception as e:
                logger.warning(f"窗口{window_id} (帧{start}-{end}) 处理失败: {e}")
                continue

        return results

    def _process_single_window(
        self,
        frames: np.ndarray,
        window_id: int,
    ) -> WindowResult:
        """处理单个窗口。"""
        # a. 帧差分
        diff_seq = self.frame_differencer.compute(frames)

        # b. 逐像素频率分析
        freq_result = self.freq_analyzer.analyze(diff_seq)

        # c. 频率直方图
        hist_stats = self.histogram.build(freq_result.freq_map)

        # d. 空间分析
        per_line = self.spatial_analyzer.analyze(
            freq_result.freq_map,
            freq_result.amp_map,
        )

        # e. 频谱功率分布
        power_spectrum = self.spectral.compute_from_freq_map(
            freq_result.freq_map,
            freq_result.amp_map,
            frames.shape[0],
        )

        # f. 计算基础情绪参数
        e1, e2, e3 = compute_primary_emotions(
            hist_stats, per_line, power_spectrum,
            frame_rate=self.frame_rate,
            high_freq_threshold=TENSION_HIGH_FREQ_THRESHOLD,
            freq_band=FREQ_BAND,
        )

        # g. 窗口内可计算的派生参数
        e4 = compute_suspect(e1, e2, e3)

        F_ps = hist_stats.F_max if hist_stats.F_max > 0 else FREQ_BAND[1]
        e7 = compute_energy(hist_stats.count_max, hist_stats.sigma, F_ps)

        e11 = compute_depression(
            hist_stats.sigma, hist_stats.M,
            offset=DEPRESSION_SIGMA_OFFSET,
        )

        return WindowResult(
            timestamp_sec=0.0,
            window_id=window_id,
            aggression=e1,
            stress=e2,
            tension=e3,
            suspect=e4,
            energy=e7,
            depression=e11,
            hist_stats=hist_stats,
            per_line_stats=per_line,
        )

    def _aggregate_results(self, window_results: List[WindowResult]) -> SessionResult:
        """聚合所有窗口结果，计算时间依赖参数。"""
        n = len(window_results)

        # 各参数的时间序列
        e1_series = np.array([w.aggression for w in window_results])
        e2_series = np.array([w.stress for w in window_results])
        e3_series = np.array([w.tension for w in window_results])
        e4_series = np.array([w.suspect for w in window_results])
        e7_series = np.array([w.energy for w in window_results])
        e11_series = np.array([w.depression for w in window_results])

        # E6 Charm — 基于全时段空间分析
        # 聚合所有窗口的逐行数据
        all_W_L = np.concatenate([w.per_line_stats.W_L for w in window_results if w.per_line_stats is not None])
        all_W_R = np.concatenate([w.per_line_stats.W_R for w in window_results if w.per_line_stats is not None])
        all_C_L = np.concatenate([w.per_line_stats.C_L for w in window_results if w.per_line_stats is not None])
        all_C_R = np.concatenate([w.per_line_stats.C_R for w in window_results if w.per_line_stats is not None])
        total_lines = sum(w.per_line_stats.n_lines for w in window_results if w.per_line_stats is not None)

        if total_lines > 0 and len(all_W_L) == total_lines:
            charm = compute_charm(all_W_L, all_W_R, all_C_L, all_C_R, total_lines)
        else:
            charm = 50.0

        # E5 Balance — 各参数变异系数之和
        # 取E1,E2,E3,E7,E11的窗口间变异性 (这5个参数可逐窗口计算)
        param_names = ['E1', 'E2', 'E3', 'E7', 'E11']
        param_series = [e1_series, e2_series, e3_series, e7_series, e11_series]

        variability_sum = 0.0
        for name, series in zip(param_names, param_series):
            mean_val = np.mean(series)
            if mean_val > 0.01:
                variability_sum += np.std(series) / mean_val

        balance = compute_balance(variability_sum)

        # E8 Self-Regulation
        e5_range = float(np.max(e1_series) - np.min(e1_series))  # 用E1波动近似ΔE5
        e6_series = np.ones(n) * charm  # Charm暂时用标量
        e6_range = 0.0

        # 更合理的E5/E6变化范围
        e5_actual_range = float(np.ptp(e1_series)) if n > 1 else 0.0
        e6_actual_range = 0.0  # Charm在整个会话中只有一个值
        self_regulation = compute_self_regulation(
            balance, e5_actual_range,
            charm, e6_actual_range,
        )

        # E9 Inhibition — 基于F1平均周期
        # F1 ≈ 帧差分量均值的变化周期
        # 简化: 用过零率计算F1的主导周期
        f1_samples = []
        for w in window_results:
            if w.hist_stats.F_max > 0:
                f1_samples.append(1.0 / max(w.hist_stats.F_max, 0.1))
        T_m = np.mean(f1_samples) if f1_samples else 0.1
        T_total = n * self.window_frames / self.frame_rate  # 总时长
        inhibition = compute_inhibition(T_m, T_total)

        # E10 Neuroticism
        e9_per_window = []
        for w in window_results:
            if w.hist_stats.F_max > 0:
                e9_per_window.append(1.0 / max(w.hist_stats.F_max, 0.1) / T_total * 100.0)
        e9_std = np.std(e9_per_window) if len(e9_per_window) > 1 else 0.0
        neuroticism = compute_neuroticism(e9_std)

        # E12 Happiness
        avg_sigma = np.mean([w.hist_stats.sigma for w in window_results])
        I = compute_information_efficiency(avg_sigma)
        avg_e7 = float(np.mean(e7_series))
        E_val = compute_energy_characteristic(avg_e7)
        delta_I = np.std([compute_information_efficiency(w.hist_stats.sigma) for w in window_results]) if n > 1 else 0.0
        delta_E_val = np.std([compute_energy_characteristic(w.energy) for w in window_results]) if n > 1 else 0.0
        happiness = compute_happiness(I, E_val, delta_I, delta_E_val)

        # P14 Stability — 基于全时段频率直方图的聚合
        all_freqs = np.concatenate([w.hist_stats.histogram for w in window_results])
        stability = 0.0
        if len(window_results) > 0:
            # 用第一个窗口的直方图结构和最后窗口的对比
            first_hist = window_results[0].hist_stats
            last_hist = window_results[-1].hist_stats
            avg_M = (first_hist.M + last_hist.M) / 2
            avg_sigma = (first_hist.sigma + last_hist.sigma) / 2
            if avg_sigma > 0:
                stability = compute_stability(first_hist)

        # K值
        emotion_averages = {
            'aggression': float(np.mean(e1_series)),
            'stress': float(np.mean(e2_series)),
            'tension': float(np.mean(e3_series)),
            'suspicious': float(np.mean(e4_series)),
            'balance': balance,
            'charm': charm,
            'energy': float(np.mean(e7_series)),
            'self_regulation': self_regulation,
            'inhibition': inhibition,
            'neuroticism': neuroticism,
            'depression': float(np.mean(e11_series)),
            'happiness': happiness,
        }

        K = compute_k_value(emotion_averages, NORMAL_NORMS, STANDARDIZATION_FACTORS)

        # 计算时长
        duration_sec = n * self.window_frames / self.frame_rate

        return SessionResult(
            window_results=window_results,
            inhibition=inhibition,
            neuroticism=neuroticism,
            balance=balance,
            charm=charm,
            self_regulation=self_regulation,
            happiness=happiness,
            stability=stability,
            K_value=K,
            duration_sec=duration_sec,
            n_windows=n,
        )
