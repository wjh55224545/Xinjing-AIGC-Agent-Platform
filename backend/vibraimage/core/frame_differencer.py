"""
帧差分模块 — VibraImage核心信号源。

对视频帧序列的每对连续帧做逐像素差分，生成"震动图像"。
这是VibraImage技术的基础信号，每像素的差分时间序列反映了
头部微振动在该位置的强度变化。

原理 (VCE.pdf p30-32):
    diff[t][x,y] = |frame[t][x,y] - frame[t-1][x,y]|
    帧差分正比于物体运动量。
"""

import numpy as np
from typing import Optional, Tuple
from backend.vibraimage.gpu_backend import get_array_module, is_gpu_available, to_gpu, to_cpu, benchmark_context


class FrameDifferencer:
    """
    逐像素帧差分计算器。

    对灰度人脸ROI帧序列做逐像素绝对值差分。

    Parameters
    ----------
    noise_threshold : float, default=1.0
        噪声阈值。低于此值的差分值置零，过滤传感器噪声。
    accumulate_frames : int, default=1
        累积帧数。>1时对连续多帧差分做移动平均后再输出。
        VibraImage产品说明书(p43)提到"accumulated as frame difference
        in several video frames"，默认为1（不累积）。

    Examples
    --------
    >>> differencer = FrameDifferencer(noise_threshold=1.0)
    >>> frames = np.random.randn(100, 224, 224).astype(np.float32)
    >>> diff_seq = differencer.compute(frames)
    >>> diff_seq.shape
    (99, 224, 224)
    """

    def __init__(
        self,
        noise_threshold: float = 1.0,
        accumulate_frames: int = 1,
    ):
        self.noise_threshold = noise_threshold
        self.accumulate_frames = max(1, accumulate_frames)

    def _xp(self):
        """获取当前数组模块（torch或numpy），GPU可用时优先GPU。"""
        return get_array_module()

    def compute(self, frames: np.ndarray) -> np.ndarray:
        """
        计算逐像素帧差分序列。

        GPU可用时自动在GPU上执行。

        Parameters
        ----------
        frames : np.ndarray, shape (N_frames, H, W)
            灰度人脸ROI帧序列，dtype为float32/uint8。

        Returns
        -------
        diff_seq : np.ndarray, shape (N_frames - accumulate_frames, H, W)
        """
        if frames.ndim != 3:
            raise ValueError(
                f"Expected 3D array (N, H, W), got shape {frames.shape}"
            )
        if frames.shape[0] < 2:
            raise ValueError(
                f"Need at least 2 frames, got {frames.shape[0]}"
            )

        if frames.dtype == np.uint8:
            frames = frames.astype(np.float32)

        with benchmark_context("帧差分"):
            if is_gpu_available():
                return self._compute_gpu(frames)
            return self._compute_cpu(frames)

    def _compute_cpu(self, frames: np.ndarray) -> np.ndarray:
        """CPU实现。"""
        diff_seq = np.abs(np.diff(frames, axis=0))
        if self.noise_threshold > 0:
            diff_seq = self._apply_threshold(diff_seq, self.noise_threshold)
        if self.accumulate_frames > 1:
            diff_seq = self._accumulate(diff_seq, self.accumulate_frames)
        return diff_seq

    def _compute_gpu(self, frames: np.ndarray) -> np.ndarray:
        """GPU实现（PyTorch）。"""
        xp = self._xp()
        g = to_gpu(frames)
        diff_seq = xp.abs(xp.diff(g, dim=0))
        if self.noise_threshold > 0:
            diff_seq = self._apply_threshold_gpu(diff_seq, self.noise_threshold)
        if self.accumulate_frames > 1:
            diff_seq = self._accumulate_gpu(diff_seq, self.accumulate_frames)
        return to_cpu(diff_seq)

    @staticmethod
    def _apply_threshold_gpu(diff, threshold: float):
        """GPU版阈值处理。"""
        xp = get_array_module()
        if xp.__name__ == 'numpy':
            mask = diff < threshold
            result = diff.copy()
            result[mask] = 0.0
            return result
        return diff * (diff >= threshold).float()

    @staticmethod
    def _apply_threshold(diff: np.ndarray, threshold: float) -> np.ndarray:
        """对差分序列应用阈值，低于阈值的置零（CPU版）。"""
        mask = diff < threshold
        result = diff.copy()
        result[mask] = 0.0
        return result

    @staticmethod
    def _accumulate(diff: np.ndarray, n_frames: int) -> np.ndarray:
        """多帧累积差分（CPU版）。"""
        if n_frames <= 1:
            return diff
        n_out = diff.shape[0] - n_frames + 1
        if n_out <= 0:
            return diff
        result = np.zeros((n_out,) + diff.shape[1:], dtype=diff.dtype)
        for i in range(n_out):
            result[i] = np.sum(diff[i:i + n_frames], axis=0)
        return result

    @staticmethod
    def _accumulate_gpu(diff, n_frames: int):
        """多帧累积差分（GPU版）。"""
        xp = get_array_module()
        if n_frames <= 1:
            return diff
        n_out = diff.shape[0] - n_frames + 1
        if n_out <= 0:
            return diff
        result = xp.zeros((n_out,) + diff.shape[1:], dtype=diff.dtype, device=diff.device)
        for i in range(n_out):
            result[i] = xp.sum(diff[i:i + n_frames], dim=0)
        return result

    def compute_single(self, frame_prev: np.ndarray, frame_curr: np.ndarray) -> np.ndarray:
        """
        计算单对帧的差分。

        Parameters
        ----------
        frame_prev, frame_curr : np.ndarray, shape (H, W)
            前后两帧。

        Returns
        -------
        diff : np.ndarray, shape (H, W)
        """
        if frame_prev.dtype == np.uint8:
            frame_prev = frame_prev.astype(np.float32)
        if frame_curr.dtype == np.uint8:
            frame_curr = frame_curr.astype(np.float32)

        with benchmark_context("单帧差分"):
            diff = np.abs(frame_curr - frame_prev)
        if self.noise_threshold > 0:
            diff[diff < self.noise_threshold] = 0.0
        return diff

    def compute_statistics(self, diff_seq: np.ndarray) -> dict:
        """
        计算差分序列的统计特征。

        Returns
        -------
        stats : dict
            - mean_diff, std_diff, activity_level, spatial_mean_per_frame
        """
        with benchmark_context("差分统计"):
            if is_gpu_available():
                xp = self._xp()
                g = to_gpu(diff_seq)
                mean_diff = float(xp.mean(g))
                std_diff = float(xp.std(g))
                activity_level = float(xp.mean((g > self.noise_threshold).float()))
                spatial_mean = to_cpu(xp.mean(g, dim=(1, 2)))
            else:
                mean_diff = float(np.mean(diff_seq))
                std_diff = float(np.std(diff_seq))
                activity_level = float(np.mean(diff_seq > self.noise_threshold))
                spatial_mean = np.mean(diff_seq, axis=(1, 2))

        return {
            'mean_diff': mean_diff,
            'std_diff': std_diff,
            'activity_level': activity_level,
            'spatial_mean_per_frame': spatial_mean,
        }
