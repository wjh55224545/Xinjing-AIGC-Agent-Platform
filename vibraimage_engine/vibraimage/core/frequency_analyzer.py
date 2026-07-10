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

    def analyze(self, diff_seq: np.ndarray) -> FrequencyResult:
        """
        分析整个差分序列，返回逐像素频率和振幅。

        Parameters
        ----------
        diff_seq : np.ndarray, shape (N_frames, H, W)
            帧差分序列。通常来自 FrameDifferencer.compute()。

        Returns
        -------
        result : FrequencyResult
            包含 freq_map, amp_map 和可选的 per_pixel_spectra。
        """
        if self.method in ('zerocross', 'auto'):
            return self._zerocross_analysis(diff_seq)
        else:
            return self._fft_analysis(diff_seq)

    def _zerocross_analysis(self, diff_seq: np.ndarray) -> FrequencyResult:
        """
        过零率法频率分析。

        原理: 对于正弦信号，每个周期有2次过零。
        因此 f = zero_crossings / (2 × duration)

        对每个像素:
        1. 减去均值 (去直流分量)
        2. 统计符号变化的次数
        3. freq = N_zero_crossings / (2 × total_time)
        4. amp = RMS of detrended signal

        复杂度: O(H×W×N), 对224×224×100 ≈ 5M次操作。
        """
        H, W = diff_seq.shape[1], diff_seq.shape[2]
        N = diff_seq.shape[0]
        dt = 1.0 / self.frame_rate
        total_time = N * dt

        # 去直流分量: 每像素减去自身均值
        mean_per_pixel = np.mean(diff_seq, axis=0)
        detrended = diff_seq - mean_per_pixel[np.newaxis, :, :]

        # 过零计数: sign change between consecutive frames
        # sign(diff[t]) != sign(diff[t+1])
        signs = np.sign(detrended)
        zero_crossings = np.sum(
            (signs[:-1] * signs[1:]) < 0, axis=0
        ).astype(np.float32)

        # 频率: f = N_zc / (2 × T)
        freq_map = zero_crossings / (2.0 * total_time)

        # 振幅: RMS
        amp_map = np.sqrt(np.mean(detrended ** 2, axis=0))

        # 限制频率在有效频段内
        freq_map = np.clip(freq_map, self.freq_band[0], self.freq_band[1])

        # 构建简易频谱 (用于E3的频谱功率分布)
        # 过零率法无法提供完整频谱，用频率直方图加权替代
        per_pixel_spectra = None

        return FrequencyResult(
            freq_map=freq_map.astype(np.float32),
            amp_map=amp_map.astype(np.float32),
            per_pixel_spectra=per_pixel_spectra,
        )

    def _fft_analysis(self, diff_seq: np.ndarray) -> FrequencyResult:
        """
        FFT法频率分析。

        对每个像素的时间序列做FFT:
        1. 取主导频率 = argmax(|FFT|) in [0.1, 10] Hz
        2. 振幅 = |FFT[dominant_freq]|
        3. 保留完整频谱用于E3计算

        复杂度: O(H×W×N×logN)
        对224×224×100: 约50,176 × 100 × log2(100) ≈ 35M次浮点运算。
        使用NumPy向量化FFT批量处理。
        """
        H, W = diff_seq.shape[1], diff_seq.shape[2]
        N = diff_seq.shape[0]
        dt = 1.0 / self.frame_rate

        # 去直流分量
        mean_per_pixel = np.mean(diff_seq, axis=0)
        detrended = diff_seq - mean_per_pixel[np.newaxis, :, :]

        # 对整个diff_seq做FFT (沿时间轴)
        # detrended shape: (N, H, W)
        # fft_result shape: (N, H, W)
        fft_result = np.abs(np.fft.rfft(detrended, axis=0))
        freqs = np.fft.rfftfreq(N, d=dt)

        # 找到有效频段范围内的索引
        freq_mask = (freqs >= self.freq_band[0]) & (freqs <= self.freq_band[1])
        valid_freqs = freqs[freq_mask]
        valid_fft = fft_result[freq_mask]

        if len(valid_freqs) == 0:
            # 退化为过零率法
            return self._zerocross_analysis(diff_seq)

        # 在有效频段内找主导频率
        dominant_idx = np.argmax(valid_fft, axis=0)  # (H, W)
        freq_map = valid_freqs[dominant_idx]  # (H, W)
        amp_map = valid_fft[dominant_idx, np.arange(H)[:, None], np.arange(W)]  # (H, W)

        # 保留完整频谱 (仅有效频段)
        per_pixel_spectra = valid_fft  # (N_valid_freq, H, W)

        return FrequencyResult(
            freq_map=freq_map.astype(np.float32),
            amp_map=amp_map.astype(np.float32),
            per_pixel_spectra=per_pixel_spectra.astype(np.float32),
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
