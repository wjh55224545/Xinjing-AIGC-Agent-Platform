"""
情绪预测与异常检测服务
======================

升级项：主攻应用效果（情绪时序从「只记录」升级为「可预测、可预警」）。

解决痛点：原系统情绪时序只有记录和趋势展示，无预测能力、无异常预警，
无法及时发现情绪突然恶化（如考前焦虑骤升、抑郁倾向加重）。

模块：
  1. 趋势预测器：线性趋势 + 加权移动平均，输出未来 N 步预测 + 置信区间
  2. 异常检测器：滑动窗口 Z-score（点异常）+ CUSUM 累积和（漂移异常）
  3. 合成时序验证：带趋势+周期+噪声+注入突变点的时序，测预测 MAE / 检出率 / 误报率

设计原则：纯 Python 实现，不依赖 prophet/sklearn 等外部库，保证 Docker 部署轻量；
所有方法可解释（线性趋势、Z-score、CUSUM 都是教学中可讲解的经典方法）。
"""

from __future__ import annotations
import math
from dataclasses import dataclass, field


@dataclass
class ForecastResult:
    """预测结果。"""
    forecast: list[float] = field(default_factory=list)       # 未来 N 步预测值
    lower: list[float] = field(default_factory=list)          # 置信区间下界
    upper: list[float] = field(default_factory=list)          # 置信区间上界
    trend_slope: float = 0.0                                  # 趋势斜率（每步变化量）
    trend_intercept: float = 0.0                              # 趋势截距
    residual_std: float = 0.0                                 # 残差标准差
    method: str = "linear_trend"                              # 使用的预测方法
    confidence: float = 0.95                                  # 置信水平


@dataclass
class AnomalyResult:
    """异常检测结果。"""
    point_anomalies: list[int] = field(default_factory=list)  # 点异常索引（Z-score 超阈值）
    drift_anomalies: list[int] = field(default_factory=list)  # 漂移异常起始索引（CUSUM 超阈值）
    z_scores: list[float] = field(default_factory=list)       # 各点 Z-score
    cusum_positive: list[float] = field(default_factory=list) # CUSUM 正向累积
    cusum_negative: list[float] = field(default_factory=list) # CUSUM 负向累积
    point_threshold: float = 2.0                               # 点异常 Z-score 阈值
    cusum_threshold: float = 3.0                               # CUSUM 漂移阈值


# ==================== 趋势预测 ====================

def linear_trend_forecast(history: list[float], steps: int = 5,
                          confidence: float = 0.95) -> ForecastResult:
    """
    线性趋势预测：最小二乘拟合历史趋势，外推未来 steps 步。

    history: 历史情绪得分序列（按时间顺序，值 ∈ [0,1]，越高越积极）
    steps:   预测未来步数
    返回: ForecastResult
    """
    n = len(history)
    if n < 2:
        return ForecastResult(forecast=[history[-1]] * steps if history else [0.5] * steps,
                               lower=[0.0] * steps, upper=[1.0] * steps,
                               method="constant_fallback")

    # 最小二乘：y = a + b*x
    xs = list(range(n))
    x_mean = sum(xs) / n
    y_mean = sum(history) / n
    sxx = sum((x - x_mean) ** 2 for x in xs)
    sxy = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, history))
    if sxx <= 1e-12:
        slope = 0.0
    else:
        slope = sxy / sxx
    intercept = y_mean - slope * x_mean

    # 残差标准差
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, history)]
    resid_std = math.sqrt(sum(r * r for r in residuals) / max(n - 2, 1))

    # 外推
    forecast = []
    lower = []
    upper = []
    # 置信区间 z 值（简化：0.95→1.96, 0.90→1.645, 0.99→2.576）
    z = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}.get(confidence, 1.96)
    for step in range(1, steps + 1):
        x_new = n - 1 + step
        y_hat = intercept + slope * x_new
        # 预测区间随步数扩大（含外推不确定性）
        se = resid_std * math.sqrt(1 + 1 / n + (x_new - x_mean) ** 2 / max(sxx, 1e-12))
        forecast.append(round(min(max(y_hat, 0.0), 1.0), 4))
        lower.append(round(min(max(y_hat - z * se, 0.0), 1.0), 4))
        upper.append(round(min(max(y_hat + z * se, 0.0), 1.0), 4))

    return ForecastResult(
        forecast=forecast, lower=lower, upper=upper,
        trend_slope=round(slope, 6), trend_intercept=round(intercept, 4),
        residual_std=round(resid_std, 4), method="linear_trend", confidence=confidence,
    )


def weighted_moving_average_forecast(history: list[float], steps: int = 5,
                                      window: int = 5, decay: float = 0.7) -> ForecastResult:
    """
    加权移动平均预测：近期数据权重更高（指数衰减），适合无明显趋势的平稳序列。
    作为线性趋势的对照/备选方法。
    """
    n = len(history)
    if n < 2:
        return ForecastResult(forecast=[history[-1]] * steps if history else [0.5] * steps,
                               method="wma_fallback")
    w = min(window, n)
    recent = history[-w:]
    weights = [decay ** (w - 1 - i) for i in range(w)]
    wma = sum(v * wt for v, wt in zip(recent, weights)) / sum(weights)
    # 简单外推：保持 WMA 不变（平稳假设）
    forecast = [round(min(max(wma, 0.0), 1.0), 4)] * steps
    resid_std = math.sqrt(sum((v - wma) ** 2 for v in recent) / max(w - 1, 1))
    return ForecastResult(
        forecast=forecast,
        lower=[round(min(max(wma - 1.96 * resid_std, 0.0), 1.0), 4)] * steps,
        upper=[round(min(max(wma + 1.96 * resid_std, 0.0), 1.0), 4)] * steps,
        residual_std=round(resid_std, 4), method="weighted_moving_average",
    )


# ==================== 异常检测 ====================

def detect_anomalies(series: list[float], window: int = 7,
                     point_threshold: float = 3.0,
                     cusum_threshold: float = 3.0) -> AnomalyResult:
    """
    异常检测：滑动窗口 Z-score（点异常）+ CUSUM 累积和（漂移异常）。

    series: 情绪得分时序
    window: 滑动窗口大小
    point_threshold: 点异常 Z-score 阈值（默认 2.0）
    cusum_threshold: CUSUM 漂移阈值（默认 3.0，即约 3σ 持续偏移）
    """
    n = len(series)
    result = AnomalyResult(point_threshold=point_threshold, cusum_threshold=cusum_threshold)
    if n < 2:
        return result

    # 全局标准差（窗口标准差为0时的兜底）
    global_mean = sum(series) / n
    global_sd = math.sqrt(sum((v - global_mean) ** 2 for v in series) / n)
    min_sd = max(global_sd, 0.01)

    # 1. 滑动窗口 Z-score
    z_scores = []
    for i in range(n):
        start = max(0, i - window)
        window_vals = series[start:i] + series[i + 1:i + 1]  # 排除当前点
        if not window_vals:
            window_vals = series[max(0, i - window):i]
        if len(window_vals) < 2:
            z_scores.append(0.0)
            continue
        m = sum(window_vals) / len(window_vals)
        sd = math.sqrt(sum((v - m) ** 2 for v in window_vals) / len(window_vals))
        if sd <= 1e-9:
            sd = min_sd  # 窗口全相同时用全局标准差兜底
        z_scores.append(round((series[i] - m) / sd, 4))
    result.z_scores = z_scores
    result.point_anomalies = [i for i, z in enumerate(z_scores) if abs(z) > point_threshold]

    # 2. CUSUM（基于全局均值的标准化残差累积）
    mean = sum(series) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in series) / n)
    if sd <= 1e-9:
        result.cusum_positive = [0.0] * n
        result.cusum_negative = [0.0] * n
        return result
    cusum_pos, cusum_neg = 0.0, 0.0
    drift_started = False
    for i, v in enumerate(series):
        z = (v - mean) / sd
        cusum_pos = max(0.0, cusum_pos + z - 0.5)   # 正向漂移（情绪升高）
        cusum_neg = max(0.0, cusum_neg - z - 0.5)   # 负向漂移（情绪降低/恶化）
        result.cusum_positive.append(round(cusum_pos, 4))
        result.cusum_negative.append(round(cusum_neg, 4))
        if (cusum_pos > cusum_threshold or cusum_neg > cusum_threshold) and not drift_started:
            result.drift_anomalies.append(i)
            drift_started = True
            # 重置后继续检测下一段漂移
            cusum_pos, cusum_neg = 0.0, 0.0
            drift_started = False

    return result


# ==================== 综合接口 ====================

def analyze_emotion_series(series: list[float], forecast_steps: int = 5) -> dict:
    """
    综合分析：预测 + 异常检测，供 API 端点调用。

    返回: {forecast, anomalies, summary}
    """
    forecast = linear_trend_forecast(series, steps=forecast_steps)
    anomalies = detect_anomalies(series)

    # 趋势方向解读
    if forecast.trend_slope > 0.005:
        trend_dir = "上升（情绪改善）"
    elif forecast.trend_slope < -0.005:
        trend_dir = "下降（情绪恶化）"
    else:
        trend_dir = "平稳"

    # 风险提示
    warnings = []
    if forecast.trend_slope < -0.01:
        warnings.append("情绪呈持续下降趋势，建议关注")
    if forecast.forecast and forecast.forecast[-1] < 0.35:
        warnings.append("预测未来情绪得分偏低，可能进入负性状态")
    if anomalies.point_anomalies:
        warnings.append(f"检测到 {len(anomalies.point_anomalies)} 个情绪突变点")
    if anomalies.drift_anomalies:
        warnings.append(f"检测到 {len(anomalies.drift_anomalies)} 段情绪漂移")

    return {
        "forecast": {
            "values": forecast.forecast,
            "lower": forecast.lower,
            "upper": forecast.upper,
            "trend_slope": forecast.trend_slope,
            "trend_direction": trend_dir,
            "residual_std": forecast.residual_std,
            "method": forecast.method,
            "confidence": forecast.confidence,
        },
        "anomalies": {
            "point_anomalies": anomalies.point_anomalies,
            "drift_anomalies": anomalies.drift_anomalies,
            "z_scores": anomalies.z_scores,
            "cusum_positive": anomalies.cusum_positive,
            "cusum_negative": anomalies.cusum_negative,
        },
        "summary": {
            "n_points": len(series),
            "trend_direction": trend_dir,
            "warnings": warnings,
        },
    }
