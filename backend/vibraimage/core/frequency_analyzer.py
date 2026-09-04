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
                # 零过零像素(无振动)置 NaN，不混入直方图(避免 0.1Hz 假低频)
                freq_map_g[zero_crossings == 0] = float('nan')
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
                # 零过零像素(无振动)置 NaN，不混入直方图(避免 0.1Hz 假低频)
                freq_map[zero_crossings == 0] = np.nan
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

    def compute_f1_frequency(self, diff_seq: np.ndarray) -> float:
        """
        估计 F1 参数 —— vibraimage 变化频率 (真 F1)。

        F1 是「头部重心位移前庭图 (vestibulogram)」的时间频率，
        即帧差分空间均值的一维时间序列的主频 (VCE.pdf 方程(11), p99)。
        与 _zerocross_analysis 相同口径: f = N_zc / (2 × duration)。

        Parameters
        ----------
        diff_seq : np.ndarray, shape (N_frames, H, W)
            帧差分序列。

        Returns
        -------
        f1 : float
            前庭图时间频率 [Hz]。零过零 (信号恒定) 时返回 0.0。
        """
        if diff_seq.ndim != 3 or diff_seq.shape[0] < 2:
            return 0.0

        spatial_mean = np.mean(diff_seq, axis=(1, 2))  # (N,)
        N = spatial_mean.shape[0]
        total_time = N / self.frame_rate

        # 去直流分量
        detrended = spatial_mean - np.mean(spatial_mean)

        # 过零计数: 相邻采样点符号变化
        signs = np.sign(detrended)
        zero_crossings = int(np.sum((signs[:-1] * signs[1:]) < 0))

        if zero_crossings == 0 or total_time <= 0:
            return 0.0

        f1 = zero_crossings / (2.0 * total_time)
        return float(f1)


# ============================================================================
# 参考实现: 泄露 VibraImage 源码的「低层频率定义」逐行翻译
# ============================================================================
# 来源: C:\Users\Lenovo\Desktop\VibraImage-Github-pirated (ELSYS 泄露源码)
# 用途: 与本模块的过零率/FFT 口径对齐，供 E1/E3 标定时的数值对照。
# 结论: 泄露源码的「频率」既不是过零率、也不是 FFT，而是「变化计数」。
# ============================================================================


def make_aura_color_a_1d(
    delta_values: np.ndarray,
    change_threshold: float = 1.0,
) -> float:
    """
    ELSYS VibraImage `MakeAuraColorA` 的逐像素翻译。

    源: viEngineThread.cpp:1853-1885，函数体完整，逐行核对如下:

        int CVIEngineThread::MakeAuraColorA(int nSum, int x, int y)
        {
            int n0 = m_pBase->m_arrDelta.front().n;   // 最新帧号
            int n  = m_pBase->m_cfg.GetI1(m_summ[nSum].id);  // 窗口长度
            int nLast = n0 - n + 1; if (nLast < 0) nLast = 0;
            float dl = 0; int dn = 0, cnt = 0;
            for (每个 delta 帧, 从最旧到最新):
                float v  = delta.i[y][x];      // 该像素的帧差值
                float dv = fabs(v - dl);       // 相邻两帧「帧差值」的变化
                if (dv > 1.0f) ++dn;           // 变化超过噪声阈值 → 计一次
                dl = v; ++cnt;
                if (delta.n == nLast) break;   // 只取最近 n 帧
            if (!cnt) return 0;
            return dn * 255 / cnt;             // 归一化到 [0, 255]
        }

    与本项目口径的语义差异 (标定时必须区分):
      - 本项目过零率法: 对「去均值后的帧差信号」数符号翻转，f = N_zc/(2T)，
        度量信号围绕 0 的正负交替。
      - 泄露源码: 数「相邻两帧的帧差值本身变化 > 1.0」的次数 dn，
        再 dn*255/cnt 归一化，度量帧差信号幅值跳变的频繁程度(抖动)。
      两者都是「频率」的近似，但数学定义不同，数值不可互通。

    Parameters
    ----------
    delta_values : np.ndarray, shape (n_frames,)
        单个像素的帧差分时间序列 (帧差, 非原始灰度)。
    change_threshold : float, default=1.0
        判定「变化」的幅值阈值，对应源码里的硬编码 1.0f。

    Returns
    -------
    color : float
        dn * 255 / cnt，范围 [0, 255]。
        注: 源码里 dn*255/cnt 是 int 截断除法，这里返回 float，
        与源码差 < 1.0，不影响直方图统计。
    """
    if delta_values is None or len(delta_values) == 0:
        return 0.0

    v = np.asarray(delta_values, dtype=np.float64)
    # dl 初始为 0，故第一帧与 0 比较 (|v[0]-0|)，此后与前一帧比较
    prev = np.concatenate(([0.0], v[:-1]))
    dv = np.abs(v - prev)
    dn = int(np.sum(dv > change_threshold))
    cnt = int(v.shape[0])
    if cnt == 0:
        return 0.0
    return dn * 255.0 / cnt


def make_aura_color_map(
    diff_seq: np.ndarray,
    change_threshold: float = 1.0,
) -> np.ndarray:
    """
    `MakeAuraColorA` 的全图向量化版本 — 与 freq_map 同形，便于对照。

    对 diff_seq (N, H, W) 的每个像素独立执行 make_aura_color_a_1d，
    返回 (H, W) 的「变化计数频率图」，范围 [0, 255]。

    Parameters
    ----------
    diff_seq : np.ndarray, shape (N, H, W)
        帧差分序列。
    change_threshold : float, default=1.0
        幅值变化阈值，对应源码 1.0f。

    Returns
    -------
    color_map : np.ndarray, shape (H, W)
        逐像素变化计数频率 [0, 255]，可直接与
        PerPixelFrequencyAnalyzer 输出的 freq_map 对照。
    """
    if diff_seq.ndim != 3 or diff_seq.shape[0] == 0:
        return np.zeros((0, 0), dtype=np.float64)

    N = diff_seq.shape[0]
    # dl 初始为 0: 第一帧与 0 比较
    prev = np.concatenate(
        (np.zeros((1, *diff_seq.shape[1:]), dtype=diff_seq.dtype), diff_seq[:-1]),
        axis=0,
    )
    dv = np.abs(diff_seq.astype(np.float64) - prev.astype(np.float64))
    dn = np.sum(dv > change_threshold, axis=0)  # (H, W)
    return dn * 255.0 / N


# ============================================================================
# 参考: F6/F7/F8/F9 分频带通滤波 —— 泄露源码中「实现缺失」，仅能还原接口
# ============================================================================
# 源: viEngineBase.cpp:47 构造函数初始化列表
#     m_procF6(this,
#              VI_VAR_STAT_RES_F6,      // 输出: F6 结果
#              VI_VAR_STAT_RES_F8,      // 输出: F8 结果
#              VI_VAR_STAT_RES_F7,      // 输出: F7 结果
#              VI_FILTER_BWT_F6_HI,     // 带通上截止频率
#              VI_FILTER_BWT_F6_LO,     // 带通下截止频率
#              VI_FILTER_F6_N,          // 滤波器阶数/窗口长度
#              VI_VAR_STAT_RES_F9)      // 输出: F9 结果
#
# 类型 CVIEngineProcDT 定义于 VIEngineProcDT.h (viEngineBase.h:21 #include)，
# 但该 .h/.cpp 不在泄露仓库中 —— 与 VIEngineConfig.cpp 被掏空同源，
# 是这份泄露被「挑着删」的又一处证据。
#
# 结论: F6→F7/F8/F9 的真实滤波算法在这份泄露里【不存在】，无法翻译。
# 这里不给可执行代码，避免用自造实现冒充「泄露源码翻译」。
#
# 能确定的只有三件事:
#   1. 存在一个「把 F6 频段拆成 F7/F8/F9 三个子带」的带通处理对象;
#   2. 截止频率由 VI_FILTER_BWT_F6_HI / VI_FILTER_BWT_F6_LO 提供，
#      阶数由 VI_FILTER_F6_N 提供;
#   3. 这与 VCE p76 的 5Hz/30Hz 分频思想同源 —— F6 是总频段，
#      F7/F8/F9 是切分后的子带 (低频/中频/高频)。
#
# 若要实现，正确的参照路径是:
#   - 把 freq_map/功率谱按 (0.1, 5) / (5, 30) / (30, +∞) 切三段,
#     对应 VCE 的 Aggression(5Hz) / 中频 / Anxiety(30Hz) 分界;
#   - BWT_F6_HI/LO 的具体数值要回到未泄露的配置数据里找，不能猜。
# ============================================================================
