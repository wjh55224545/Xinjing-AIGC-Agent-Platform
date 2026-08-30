"""
空间分析模块 — 逐行左右半区不对称性分析。

VibraImage的E2(Stress)和E6(Charm)都依赖逐行L/R比较。
这是VibraImage区别于其他情绪识别技术的关键特征之一
——利用空间不对称性衡量心理状态。

原理 (VCE.pdf p71-72, p87):
    - 将人脸ROI逐行分割为左右半区
    - 每行比较左右侧的振动振幅和频率
    - 不对称性越大 → 压力越高 / 魅力越低
"""

import numpy as np
from typing import Dict, Tuple, List
from dataclasses import dataclass


@dataclass
class PerLineStats:
    """逐行空间分析结果。"""
    A_L: np.ndarray             # 每行左侧振幅均值, shape (H,)
    A_R: np.ndarray             # 每行右侧振幅均值, shape (H,)
    F_L: np.ndarray             # 每行左侧最大频率 [Hz], shape (H,)
    F_R: np.ndarray             # 每行右侧最大频率 [Hz], shape (H,)
    W_L: np.ndarray             # 每行左侧振幅分量均值 (用于E6), shape (H,)
    W_R: np.ndarray             # 每行右侧振幅分量均值 (用于E6), shape (H,)
    C_L: np.ndarray             # 每行左侧频率分量最大值 (用于E6), shape (H,)
    C_R: np.ndarray             # 每行右侧频率分量最大值 (用于E6), shape (H,)
    n_lines: int                # 有效行数

    @property
    def A_max(self) -> float:
        """所有行的最大振幅值。"""
        all_amps = np.concatenate([self.A_L, self.A_R])
        return float(np.max(all_amps)) if len(all_amps) > 0 else 1e-6

    @property
    def F_max(self) -> float:
        """所有行的最大频率值。"""
        all_freqs = np.concatenate([self.F_L, self.F_R])
        return float(np.max(all_freqs)) if len(all_freqs) > 0 else 1e-6


class SpatialAnalyzer:
    """
    逐行左右空间分析器。

    对人脸ROI的每一行像素，比较左右半区的振动特性。

    Parameters
    ----------
    center_weight : float, default=0.1
        中线附近排除的权重 (避免鼻梁等中线结构的干扰)。
        0 = 使用全部宽度, 0.1 = 排除中线附近10%宽度。
    """

    def __init__(self, center_width: float = 0.1):
        self.center_width = center_width

    def analyze(
        self,
        freq_map: np.ndarray,
        amp_map: np.ndarray,
    ) -> PerLineStats:
        """
        执行逐行左右分析。

        Parameters
        ----------
        freq_map : np.ndarray, shape (H, W)
            每个像素的主导频率 [Hz] (来自FrequencyAnalyzer)。
        amp_map : np.ndarray, shape (H, W)
            每个像素的振动振幅 (来自FrequencyAnalyzer)。

        Returns
        -------
        stats : PerLineStats
            逐行统计量。
        """
        H, W = freq_map.shape
        mid = W // 2
        exclude = int(W * self.center_width / 2)

        # 左右半区的列索引 (排除中线附近)
        left_cols = slice(0, mid - exclude)
        right_cols = slice(mid + exclude, W)

        # 初始化
        n_lines = H
        A_L = np.zeros(H, dtype=np.float32)
        A_R = np.zeros(H, dtype=np.float32)
        F_L = np.zeros(H, dtype=np.float32)
        F_R = np.zeros(H, dtype=np.float32)
        W_L = np.zeros(H, dtype=np.float32)
        W_R = np.zeros(H, dtype=np.float32)
        C_L = np.zeros(H, dtype=np.float32)
        C_R = np.zeros(H, dtype=np.float32)

        for i in range(H):
            # 左侧
            left_amps = amp_map[i, left_cols]
            left_freqs = freq_map[i, left_cols]
            left_valid = np.isfinite(left_freqs) & (left_freqs > 0)

            if np.any(left_valid):
                A_L[i] = np.mean(left_amps[left_valid]) if np.any(left_valid) else 0.0
                F_L[i] = np.max(left_freqs[left_valid]) if np.any(left_valid) else 0.0
                W_L[i] = np.mean(left_amps[left_valid]) if np.any(left_valid) else 0.0
                C_L[i] = np.max(left_freqs[left_valid]) if np.any(left_valid) else 0.0

            # 右侧
            right_amps = amp_map[i, right_cols]
            right_freqs = freq_map[i, right_cols]
            right_valid = np.isfinite(right_freqs) & (right_freqs > 0)

            if np.any(right_valid):
                A_R[i] = np.mean(right_amps[right_valid]) if np.any(right_valid) else 0.0
                F_R[i] = np.max(right_freqs[right_valid]) if np.any(right_valid) else 0.0
                W_R[i] = np.mean(right_amps[right_valid]) if np.any(right_valid) else 0.0
                C_R[i] = np.max(right_freqs[right_valid]) if np.any(right_valid) else 0.0

        # 过滤全零行 (没有有效像素的行)
        valid_rows = np.any(
            np.stack([A_L, A_R, F_L, F_R], axis=0) > 0, axis=0
        )

        return PerLineStats(
            A_L=A_L[valid_rows],
            A_R=A_R[valid_rows],
            F_L=F_L[valid_rows],
            F_R=F_R[valid_rows],
            W_L=W_L[valid_rows],
            W_R=W_R[valid_rows],
            C_L=C_L[valid_rows],
            C_R=C_R[valid_rows],
            n_lines=int(np.sum(valid_rows)),
        )
