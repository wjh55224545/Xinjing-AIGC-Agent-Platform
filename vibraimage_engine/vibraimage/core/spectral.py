"""
频谱功率分布模块。

计算跨所有像素的聚合频谱功率分布 P(f)，用于E3(Tension)计算。

E3的高频功率比需要全局频谱，而非单个像素的主导频率。
本模块将逐像素FFT频谱按频率对齐后求和，得到聚合功率谱。

原理 (VCE.pdf p75):
    Tension = (高频功率) / (总功率) × 100%
    P(f_i) = Σ_{x,y} |FFT_{x,y}(f_i)|² — 跨所有像素的频谱功率
"""

import numpy as np
from typing import Tuple, Optional


class SpectralPowerDistribution:
    """
    跨像素频谱功率聚合器。

    将逐像素FFT频谱按频率对齐聚合为全局功率谱。

    Parameters
    ----------
    frame_rate : float, default=30.0
        摄像头帧率 [fps]。
    freq_band : tuple, default=(0.1, 10.0)
        有效频段 [Hz]。
    high_freq_threshold : float, default=3.0
        高频分界点 [Hz]。高于此值的频率计为"高频"。
        基于专著p76描述Tension"characterizes high-frequency processes"
        和EEG类比设定。
    """

    def __init__(
        self,
        frame_rate: float = 30.0,
        freq_band: Tuple[float, float] = (0.1, 10.0),
        high_freq_threshold: float = 3.0,
    ):
        self.frame_rate = frame_rate
        self.freq_band = freq_band
        self.high_freq_threshold = high_freq_threshold

    def compute_from_freq_map(
        self,
        freq_map: np.ndarray,
        amp_map: np.ndarray,
        n_frames: int,
    ) -> np.ndarray:
        """
        从频率图和振幅图估算频谱功率分布。

        当无法获取完整逐像素FFT频谱时的近似方法:
        将振幅²按频率bin累加，等价于Σ|FFT(f)|²的直方图版本。

        Parameters
        ----------
        freq_map : np.ndarray, shape (H, W)
            逐像素主导频率 [Hz]。
        amp_map : np.ndarray, shape (H, W)
            逐像素振幅。
        n_frames : int
            帧数 (用于确定FFT频率分辨率)。

        Returns
        -------
        power_spectrum : np.ndarray, shape (n_bins,)
            聚合功率谱。
        """
        # 频率分辨率
        dt = 1.0 / self.frame_rate
        df = 1.0 / (n_frames * dt)
        n_bins = int((self.freq_band[1] - self.freq_band[0]) / df) + 1

        # 展平
        freqs = freq_map.ravel()
        amps = amp_map.ravel()
        valid = np.isfinite(freqs) & (freqs >= self.freq_band[0]) & (freqs <= self.freq_band[1])

        if not np.any(valid):
            return np.zeros(n_bins)

        freqs_valid = freqs[valid]
        amps_sq_valid = (amps[valid] ** 2).astype(np.float64)

        # 按频率bin累加功率
        power_spectrum, _ = np.histogram(
            freqs_valid,
            bins=n_bins,
            range=self.freq_band,
            weights=amps_sq_valid,
        )

        return power_spectrum.astype(np.float64)

    def compute_from_spectra(
        self,
        per_pixel_spectra: np.ndarray,
        freqs: np.ndarray,
    ) -> np.ndarray:
        """
        从逐像素FFT频谱计算聚合功率谱。

        P(f_i) = Σ_{x,y} |FFT_{x,y}(f_i)|²

        Parameters
        ----------
        per_pixel_spectra : np.ndarray, shape (N_freq, H, W) or (H, W, N_freq)
            逐像素FFT幅度谱 (有效频段内)。
        freqs : np.ndarray, shape (N_freq,)
            对应的频率轴 [Hz]。

        Returns
        -------
        power_spectrum : np.ndarray, shape (N_freq,)
            聚合功率谱 = Σ|FFT|² over all pixels。
        """
        # 确保 shape 是 (N_freq, H, W)
        if per_pixel_spectra.ndim == 3:
            if per_pixel_spectra.shape[-1] != len(freqs):
                # 可能是 (H, W, N_freq) 格式
                if per_pixel_spectra.shape[0] == len(freqs):
                    pass  # shape is (N_freq, H, W)
                else:
                    per_pixel_spectra = np.moveaxis(per_pixel_spectra, -1, 0)

        # 跨像素求和: Σ_{x,y} |FFT(f)|²
        power_spectrum = np.sum(per_pixel_spectra ** 2, axis=(1, 2))

        return power_spectrum.astype(np.float64)

    def compute_tension_ratio(self, power_spectrum: np.ndarray) -> float:
        """
        计算高频功率比 (E3核心计算)。

        E3 = (高频功率) / (总功率) × 100%

        Parameters
        ----------
        power_spectrum : np.ndarray, shape (n_bins,)
            聚合功率谱。

        Returns
        -------
        tension : float
            Tension参数 [0-100]%。
        """
        total_power = np.sum(power_spectrum)
        if total_power <= 0:
            return 0.0

        # 确定高频段的bin索引
        n_bins = len(power_spectrum)
        # bin中心频率
        bin_width = (self.freq_band[1] - self.freq_band[0]) / n_bins
        high_freq_start_bin = int(
            (self.high_freq_threshold - self.freq_band[0]) / bin_width
        )
        high_freq_start_bin = max(0, min(n_bins - 1, high_freq_start_bin))

        high_freq_power = np.sum(power_spectrum[high_freq_start_bin:])
        tension = (high_freq_power / total_power) * 100.0

        return float(np.clip(tension, 0.0, 100.0))
