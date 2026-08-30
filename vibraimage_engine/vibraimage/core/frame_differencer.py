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

    def compute(self, frames: np.ndarray) -> np.ndarray:
        """
        计算逐像素帧差分序列。

        Parameters
        ----------
        frames : np.ndarray, shape (N_frames, H, W)
            灰度人脸ROI帧序列，dtype为float32/uint8。
            若为uint8自动转为float32。

        Returns
        -------
        diff_seq : np.ndarray, shape (N_frames - accumulate_frames, H, W)
            差分序列，每个元素为相邻帧差的绝对值。
        """
        if frames.ndim != 3:
            raise ValueError(
                f"Expected 3D array (N, H, W), got shape {frames.shape}"
            )
        if frames.shape[0] < 2:
            raise ValueError(
                f"Need at least 2 frames, got {frames.shape[0]}"
            )

        # 确保float32
        if frames.dtype == np.uint8:
            frames = frames.astype(np.float32)

        # 逐帧差分
        diff_seq = np.abs(np.diff(frames, axis=0))

        # 噪声阈值处理
        if self.noise_threshold > 0:
            diff_seq = self._apply_threshold(diff_seq, self.noise_threshold)

        # 多帧累积
        if self.accumulate_frames > 1:
            diff_seq = self._accumulate(diff_seq, self.accumulate_frames)

        return diff_seq

    @staticmethod
    def _apply_threshold(diff: np.ndarray, threshold: float) -> np.ndarray:
        """对差分序列应用阈值，低于阈值的置零。"""
        mask = diff < threshold
        result = diff.copy()
        result[mask] = 0.0
        return result

    @staticmethod
    def _accumulate(diff: np.ndarray, n_frames: int) -> np.ndarray:
        """
        多帧累积差分。

        对连续n_frames帧的差分做移动求和。
        VibraImage产品说明书(p43)提到"frame difference accumulated
        in several video frames"。
        """
        if n_frames <= 1:
            return diff
        n_out = diff.shape[0] - n_frames + 1
        if n_out <= 0:
            return diff
        result = np.zeros((n_out,) + diff.shape[1:], dtype=diff.dtype)
        for i in range(n_out):
            result[i] = np.sum(diff[i:i + n_frames], axis=0)
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
            - mean_diff: 全局均值
            - std_diff: 全局标准差
            - activity_level: 活跃像素比例 (diff > threshold的像素占比)
            - spatial_mean_per_frame: 每帧空间均值序列
        """
        return {
            'mean_diff': float(np.mean(diff_seq)),
            'std_diff': float(np.std(diff_seq)),
            'activity_level': float(
                np.mean(diff_seq > self.noise_threshold)
            ),
            'spatial_mean_per_frame': np.mean(diff_seq, axis=(1, 2)),
        }
