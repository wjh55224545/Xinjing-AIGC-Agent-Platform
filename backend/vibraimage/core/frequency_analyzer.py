"""
逐像素频率分析模块。

对帧差分时间序列中的每个像素，计算其主导振动频率和振幅。
这是VibraImage计算链中最关键的一步 — 将50,000+个像素的时间序列
压缩为两个标量场: freq_map[x,y] 和 amp_map[x,y]。

两种策略:
- 过零率法 (默认): O(H×W×N), 快速，适合低频信号(0.1-10Hz)
- FFT法 (精确): O(H×W×N×logN), 计算量大但频谱信息完整
"""

import numpy as np
from typing import Tuple, Optional
from dataclasses import dataclass
from backend.vibraimage.gpu_backend import (
    get_array_module, is_gpu_available, to_gpu, to_cpu,
    rfft, rfftfreq, benchmark_context,
)


@dataclass
class FrequencyResult:
    """每个窗口的频率分析完整输出。"""
    freq_map: np.ndarray       # (H, W) 主导频率 [Hz]
    amp_map: np.ndarray        # (H, W) 振动振幅
    per_pixel_spectra: Optional[np.ndarray] = None  # (H, W, N_freq) FFT频谱


class PerPixelFrequencyAnalyzer:
    """
    逐像素振动频率分析器。

    对帧差分序列的每个像素独立计算主导频率和振幅。

    Parameters
    ----------
    frame_rate : float, default=30.0
        摄像头帧率 [fps]。
    freq_band : tuple, default=(0.1, 10.0)
        有效频段 [Hz]。超出此范围的频率视为噪声。
    method : str, default='zerocross'
        频率估计方法:
        - 'zerocross': 过零率法 (快速)
        - 'fft': FFT法 (精确，计算量大)
        - 'auto': 自动选择 (当前=zerocross)

    Examples
    --------
    >>> analyzer = PerPixelFrequencyAnalyzer(frame_rate=30.0)
    >>> diff_seq = np.random.randn(99, 224, 224).astype(np.float32)
    >>> result = analyzer.analyze(diff_seq)
    >>> result.freq_map.shape
    (224, 224)
    """

    def __init__(
        self,
        frame_rate: float = 30.0,
        freq_band: Tuple[float, float] = (0.1, 10.0),
        method: str = 'zerocross',
    ):
        self.frame_rate = frame_rate
        self.freq_band = freq_band
        self.method = method

        if method not in ('zerocross', 'fft', 'auto'):
            raise ValueError(f"Unknown method: {method}")

    def _xp(self):
        """获取当前数组模块。"""
        return get_array_module()

    def analyze(self, diff_seq: np.ndarray) -> FrequencyResult:
        """
        分析整个差分序列，返回逐像素频率和振幅。
        GPU可用时自动在GPU上执行FFT分析。
        """
        if self.method in ('zerocross', 'auto'):
            return self._zerocross_analysis(diff_seq)
        else:
            return self._fft_analysis(diff_seq)

    def _zerocross_analysis(self, diff_seq: np.ndarray) -> FrequencyResult:
        """
        过零率法频率分析（CPU/GPU通用）。
        """
        dt = 1.0 / self.frame_rate
        N = diff_seq.shape[0]
        total_time = N * dt

        with benchmark_context("频率分析(过零率)"):
            if is_gpu_available():
                xp = self._xp()
                g = to_gpu(diff_seq)
                mean_per_pixel = xp.mean(g, dim=0)
                detrended = g - mean_per_pixel.unsqueeze(0)
                signs = xp.sign(detrended)
                zero_crossings = xp.sum(
                    (signs[:-1] * signs[1:] < 0).float(), dim=0
                )
                freq_map_g = zero_crossings / (2.0 * total_time)
                freq_map_g = xp.clip(freq_map_g, self.freq_band[0], self.freq_band[1])
                amp_map_g = xp.sqrt(xp.mean(detrended ** 2, dim=0))
                freq_map = to_cpu(freq_map_g).astype(np.float32)
                amp_map = to_cpu(amp_map_g).astype(np.float32)
            else:
                mean_per_pixel = np.mean(diff_seq, axis=0)
                detrended = diff_seq - mean_per_pixel[np.newaxis, :, :]
                signs = np.sign(detrended)
                zero_crossings = np.sum((signs[:-1] * signs[1:]) < 0, axis=0).astype(np.float32)
                freq_map = (zero_crossings / (2.0 * total_time)).astype(np.float32)
                freq_map = np.clip(freq_map, self.freq_band[0], self.freq_band[1])
                amp_map = np.sqrt(np.mean(detrended ** 2, axis=0)).astype(np.float32)

        return FrequencyResult(
            freq_map=freq_map, amp_map=amp_map, per_pixel_spectra=None,
        )

    def _fft_analysis(self, diff_seq: np.ndarray) -> FrequencyResult:
        """
        FFT法频率分析。GPU可用时FFT在GPU上执行（加速最显著的操作）。
        """
        H, W = diff_seq.shape[1], diff_seq.shape[2]
        N = diff_seq.shape[0]
        dt = 1.0 / self.frame_rate

        with benchmark_context("频率分析(FFT)"):
            if is_gpu_available():
                return self._fft_analysis_gpu(diff_seq, H, W, N, dt)
            return self._fft_analysis_cpu(diff_seq, H, W, N, dt)

    def _fft_analysis_cpu(self, diff_seq, H, W, N, dt) -> FrequencyResult:
        """FFT分析CPU版。"""
        mean_per_pixel = np.mean(diff_seq, axis=0)
        detrended = diff_seq - mean_per_pixel[np.newaxis, :, :]
        fft_result = np.abs(np.fft.rfft(detrended, axis=0))
        freqs = np.fft.rfftfreq(N, d=dt)

        freq_mask = (freqs >= self.freq_band[0]) & (freqs <= self.freq_band[1])
        valid_freqs = freqs[freq_mask]
        valid_fft = fft_result[freq_mask]

        if len(valid_freqs) == 0:
            return self._zerocross_analysis(diff_seq)

        dominant_idx = np.argmax(valid_fft, axis=0)
        freq_map = valid_freqs[dominant_idx]
        amp_map = valid_fft[dominant_idx, np.arange(H)[:, None], np.arange(W)]
        per_pixel_spectra = valid_fft

        return FrequencyResult(
            freq_map=freq_map.astype(np.float32),
            amp_map=amp_map.astype(np.float32),
            per_pixel_spectra=per_pixel_spectra.astype(np.float32),
        )

    def _fft_analysis_gpu(self, diff_seq, H, W, N, dt) -> FrequencyResult:
        """FFT分析GPU版（PyTorch）。"""
        xp = self._xp()
        g = to_gpu(diff_seq)
        mean_per_pixel = xp.mean(g, dim=0)
        detrended = g - mean_per_pixel.unsqueeze(0)
        fft_result = xp.abs(rfft(detrended, axis=0))
        freqs = rfftfreq(N, d=dt)

        freq_mask = (freqs >= self.freq_band[0]) & (freqs <= self.freq_band[1])
        if hasattr(freq_mask, 'cpu'):
            valid_freqs = freqs[freq_mask]
        else:
            valid_freqs = freqs[freq_mask]
        valid_fft = fft_result[freq_mask]

        if len(valid_freqs) == 0:
            return self._zerocross_analysis(diff_seq)

        dominant_idx = xp.argmax(valid_fft, dim=0)
        # 统一在GPU上完成索引（rfftfreq已修复为GPU tensor，
        # xp.arange需显式指定device避免跨设备索引）
        device = valid_fft.device
        idx_h = xp.arange(H, device=device)[:, None]
        idx_w = xp.arange(W, device=device)
        freq_map = to_cpu(valid_freqs[dominant_idx]).astype(np.float32)
        amp_map = to_cpu(valid_fft[dominant_idx, idx_h, idx_w]).astype(np.float32)

        return FrequencyResult(
            freq_map=freq_map, amp_map=amp_map,
            per_pixel_spectra=None,  # 频谱太大，按需时才传回CPU
        )

    def compute_f1_parameter(self, diff_seq: np.ndarray) -> np.ndarray:
        """
        计算F1参数 — vibraimage变化频率。

        F1是帧差分量空间均值的时变频率，用于E9(Inhibition)计算。

        原理: 对所有像素的帧差分求空间均值 → 得到一维时间序列 →
        对此序列做频率分析。

        Returns
        -------
        f1_series : np.ndarray, shape (N_frames,)
        """
        spatial_mean = np.mean(diff_seq, axis=(1, 2))
        return spatial_mean
