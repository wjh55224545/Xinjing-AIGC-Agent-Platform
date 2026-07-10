"""
频率直方图模块。

将逐像素频率图(freq_map)聚合为频率分布直方图。
这是VibraImage最核心的中间表示——几乎所有情绪参数(E1, E7, E11, P14)
都直接或间接依赖频率直方图的统计特性。

直方图构建 (VCE.pdf p59-61):
    - 对所有像素的主导频率做直方图
    - bin范围: 0.1-10 Hz (VibraImage有效频段)
    - 提取M(均值), σ(标准差), F_max(峰值频率), count_max(峰值计数)
"""

import numpy as np
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from scipy import stats


@dataclass
class HistogramStats:
    """频率直方图的统计特性。"""
    histogram: np.ndarray       # 直方图计数数组, shape (n_bins,)
    bin_edges: np.ndarray       # 直方图bin边界, shape (n_bins + 1,)
    bin_centers: np.ndarray     # 直方图bin中心频率, shape (n_bins,)

    # 统计量
    F_max: float                # 直方图峰值对应的频率 [Hz]
    M: float                    # 均值频率 [Hz]
    sigma: float                # 频率标准差 [Hz]
    count_max: float            # 直方图最大计数 (用于E7)
    total_pixels: int           # 有效像素总数

    # 额外统计
    skewness: float = 0.0       # 偏度
    kurtosis: float = 0.0       # 峰度

    def to_dict(self) -> dict:
        """转为字典方便序列化。"""
        return {
            'F_max': float(self.F_max),
            'M': float(self.M),
            'sigma': float(self.sigma),
            'count_max': float(self.count_max),
            'total_pixels': self.total_pixels,
            'skewness': float(self.skewness),
            'kurtosis': float(self.kurtosis),
        }


class FrequencyHistogram:
    """
    跨像素频率直方图构建器。

    输入 freq_map (每个像素的主导频率) → 输出直方图统计。

    Parameters
    ----------
    freq_band : tuple, default=(0.1, 10.0)
        有效频段 [Hz]。
    n_bins : int, default=100
        直方图bin数量。
    """

    def __init__(
        self,
        freq_band: Tuple[float, float] = (0.1, 10.0),
        n_bins: int = 100,
    ):
        self.freq_band = freq_band
        self.n_bins = n_bins

    def build(self, freq_map: np.ndarray) -> HistogramStats:
        """
        从逐像素频率图构建频率直方图并计算统计量。

        Parameters
        ----------
        freq_map : np.ndarray, shape (H, W)
            每个像素的主导频率 [Hz]。

        Returns
        -------
        stats : HistogramStats
            直方图及其统计量。
        """
        # 展平为1D，只保留有效频段内的像素
        freqs = freq_map.ravel()

        # 过滤无效值 (NaN, inf, 频段外)
        valid_mask = (
            np.isfinite(freqs) &
            (freqs >= self.freq_band[0]) &
            (freqs <= self.freq_band[1])
        )
        valid_freqs = freqs[valid_mask]

        if len(valid_freqs) == 0:
            return self._empty_stats()

        # 构建直方图
        histogram, bin_edges = np.histogram(
            valid_freqs,
            bins=self.n_bins,
            range=self.freq_band,
        )
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0

        # 统计量
        M = float(np.mean(valid_freqs))
        sigma = float(np.std(valid_freqs))
        count_max = float(np.max(histogram))
        F_max_idx = int(np.argmax(histogram))
        F_max = float(bin_centers[F_max_idx])
        total_pixels = len(valid_freqs)

        # 高阶矩
        skewness = float(stats.skew(valid_freqs)) if len(valid_freqs) > 2 else 0.0
        kurtosis = float(stats.kurtosis(valid_freqs)) if len(valid_freqs) > 2 else 0.0

        return HistogramStats(
            histogram=histogram,
            bin_edges=bin_edges,
            bin_centers=bin_centers,
            F_max=F_max,
            M=M,
            sigma=sigma,
            count_max=count_max,
            total_pixels=total_pixels,
            skewness=skewness,
            kurtosis=kurtosis,
        )

    def compute_normal_fit(self, hist_stats: HistogramStats) -> float:
        """
        计算频率直方图与正态分布的拟合度 (用于P14 Stability)。

        方程(16), VCE.pdf p122:
            P14 = K × 100%
            K = Σ y'(x) / Σ y(x)
        其中 y'(x) 为N(M, σ²)正态分布密度, y(x)为实际频率分布。

        Returns
        -------
        stability : float
            稳定性参数 [0-100]%。
            接近100% = 高度稳定 (频率分布接近正态)。
        """
        x = hist_stats.bin_centers
        y_actual = hist_stats.histogram.astype(np.float64)

        if np.sum(y_actual) == 0:
            return 0.0

        # 正态分布密度 N(M, σ²)
        y_normal = stats.norm.pdf(x, loc=hist_stats.M, scale=max(hist_stats.sigma, 0.01))
        # 缩放到与实际直方图相同的总和
        y_normal_scaled = y_normal * (np.sum(y_actual) / max(np.sum(y_normal), 1e-10))

        # K = Σ y'(x) / Σ y(x)
        # 实际实现: P14 = (1 - KS距离) * 100
        # 用归一化的L1距离衡量拟合度
        l1_distance = np.sum(np.abs(y_actual - y_normal_scaled)) / max(np.sum(y_actual), 1e-10)
        stability = max(0.0, min(100.0, (1.0 - l1_distance) * 100.0))

        return stability

    def _empty_stats(self) -> HistogramStats:
        """返回空的统计量。"""
        bin_edges = np.linspace(self.freq_band[0], self.freq_band[1], self.n_bins + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2.0
        return HistogramStats(
            histogram=np.zeros(self.n_bins),
            bin_edges=bin_edges,
            bin_centers=bin_centers,
            F_max=0.0,
            M=0.0,
            sigma=0.0,
            count_max=0.0,
            total_pixels=0,
        )
