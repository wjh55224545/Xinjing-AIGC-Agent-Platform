"""
可视化模块 — Vibraimage渲染。

渲染帧差分图像、频率热力图、频率直方图等。
"""

import numpy as np
import cv2
from typing import Optional, Tuple
from ..core.histogram import HistogramStats


def render_diff_heatmap(diff_frame: np.ndarray, colormap: int = cv2.COLORMAP_JET) -> np.ndarray:
    """
    将帧差分量渲染为热力图。

    VibraImage产品中的"震动图像"就是帧差分的伪彩色渲染:
        Violet (0-1Hz), Dark Blue (1-4Hz), Green (4-8Hz), Red (8-10Hz)

    Parameters
    ----------
    diff_frame : np.ndarray, shape (H, W)
        单帧差分图。
    colormap : int
        OpenCV colormap。

    Returns
    -------
    heatmap : np.ndarray, shape (H, W, 3)
        BGR彩色热力图。
    """
    # 归一化到[0, 255]
    diff_norm = diff_frame.astype(np.float32)
    if np.max(diff_norm) > 0:
        diff_norm = diff_norm / np.max(diff_norm) * 255.0
    diff_norm = np.clip(diff_norm, 0, 255).astype(np.uint8)

    heatmap = cv2.applyColorMap(diff_norm, colormap)
    return heatmap


def render_frequency_map(
    freq_map: np.ndarray,
    colormap: int = cv2.COLORMAP_JET,
    freq_range: Tuple[float, float] = (0.1, 10.0),
) -> np.ndarray:
    """
    将频率图渲染为伪彩色图像。

    Parameters
    ----------
    freq_map : np.ndarray, shape (H, W)
        逐像素主导频率 [Hz]。
    colormap : int
        OpenCV colormap。
    freq_range : tuple
        频率范围 (用于归一化)。

    Returns
    -------
    heatmap : np.ndarray, shape (H, W, 3)
    """
    freq_norm = freq_map.astype(np.float32)
    freq_norm = np.clip(freq_norm, freq_range[0], freq_range[1])
    freq_norm = (freq_norm - freq_range[0]) / (freq_range[1] - freq_range[0]) * 255.0
    freq_norm = np.clip(freq_norm, 0, 255).astype(np.uint8)

    heatmap = cv2.applyColorMap(freq_norm, colormap)
    return heatmap


def render_histogram(hist_stats: HistogramStats, width: int = 400, height: int = 300) -> np.ndarray:
    """
    渲染频率直方图为图像。

    Parameters
    ----------
    hist_stats : HistogramStats
        频率直方图统计量。
    width, height : int
        图像尺寸。

    Returns
    -------
    hist_img : np.ndarray, shape (height, width, 3)
    """
    from scipy import stats
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(width/100, height/100), dpi=100)
    ax.bar(
        hist_stats.bin_centers,
        hist_stats.histogram,
        width=hist_stats.bin_centers[1] - hist_stats.bin_centers[0] if len(hist_stats.bin_centers) > 1 else 0.1,
        alpha=0.7,
        label='实际分布',
    )

    # 叠加正态分布参考
    if hist_stats.sigma > 0:
        x = np.linspace(hist_stats.bin_centers[0], hist_stats.bin_centers[-1], 200)
        y = stats.norm.pdf(x, hist_stats.M, hist_stats.sigma)
        y_scaled = y * (np.max(hist_stats.histogram) / max(np.max(y), 1e-10))
        ax.plot(x, y_scaled, 'r-', linewidth=2, label='正态分布')

    ax.set_xlabel('频率 [Hz]')
    ax.set_ylabel('像素计数')
    ax.set_title(
        f'频率直方图 (M={hist_stats.M:.2f}Hz, σ={hist_stats.sigma:.2f}Hz)'
    )
    ax.legend()

    fig.tight_layout()
    fig.canvas.draw()

    # 转为numpy数组
    img = np.frombuffer(fig.canvas.tostring_rgb(), dtype=np.uint8)
    img = img.reshape(fig.canvas.get_width_height()[::-1] + (3,))
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

    plt.close(fig)
    return img


def combine_display(
    original: np.ndarray,
    diff_heatmap: np.ndarray,
    freq_heatmap: np.ndarray,
    hist_img: np.ndarray,
) -> np.ndarray:
    """
    组合原始帧、差分热力图、频率热力图、直方图到单张显示图。

    Parameters
    ----------
    original : np.ndarray
        原始帧 (灰度)。
    diff_heatmap : np.ndarray
        差分热力图。
    freq_heatmap : np.ndarray
        频率热力图。
    hist_img : np.ndarray
        直方图。

    Returns
    -------
    combined : np.ndarray
        组合图像。
    """
    # 统一尺寸
    target_h = 224
    target_w = 224

    def resize_to(img, h, w):
        if img.ndim == 2:
            img = cv2.cvtColor(img.astype(np.uint8), cv2.COLOR_GRAY2BGR)
        return cv2.resize(img, (w, h))

    original_rgb = resize_to(original, target_h, target_w)
    diff_rgb = resize_to(diff_heatmap, target_h, target_w)
    freq_rgb = resize_to(freq_heatmap, target_h, target_w)
    hist_rgb = resize_to(hist_img, target_h * 2, target_w * 2)

    # 上排: 原始 + 差分 + 频率
    top_row = np.hstack([original_rgb, diff_rgb, freq_rgb])

    # 下排: 直方图居中
    pad_w = (top_row.shape[1] - hist_rgb.shape[1]) // 2
    if pad_w > 0:
        hist_padded = cv2.copyMakeBorder(
            hist_rgb, 0, 0, pad_w, pad_w,
            cv2.BORDER_CONSTANT, value=[0, 0, 0],
        )
    else:
        hist_padded = hist_rgb

    combined = np.vstack([top_row, hist_padded])
    return combined
