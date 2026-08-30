"""
情绪预测与异常检测测试
=======================
覆盖：线性趋势预测、加权移动平均、异常检测（点异常/漂移）、综合接口、API 端点。
"""

import pytest
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.services.emotion_forecast import (
    linear_trend_forecast, weighted_moving_average_forecast,
    detect_anomalies, analyze_emotion_series,
)


class TestForecast:
    def test_linear_trend_up(self):
        """上升趋势 → 预测值应递增"""
        history = [0.3 + 0.02 * i for i in range(15)]
        r = linear_trend_forecast(history, steps=5)
        assert r.trend_slope > 0
        assert r.forecast[-1] > r.forecast[0]
        assert all(0 <= v <= 1 for v in r.forecast)
        assert len(r.forecast) == 5

    def test_linear_trend_down(self):
        """下降趋势 → 预测值应递减"""
        history = [0.8 - 0.02 * i for i in range(15)]
        r = linear_trend_forecast(history, steps=5)
        assert r.trend_slope < 0
        assert r.forecast[-1] < r.forecast[0]

    def test_confidence_interval(self):
        """置信区间：lower <= forecast <= upper"""
        history = [0.5, 0.52, 0.48, 0.51, 0.49, 0.53, 0.47, 0.5]
        r = linear_trend_forecast(history, steps=3)
        for lo, f, hi in zip(r.lower, r.forecast, r.upper):
            assert lo <= f <= hi

    def test_short_history_fallback(self):
        """历史不足 2 点 → 恒定回退"""
        r = linear_trend_forecast([0.6], steps=3)
        assert r.method == "constant_fallback"
        assert r.forecast == [0.6, 0.6, 0.6]

    def test_wma(self):
        """加权移动平均"""
        history = [0.5, 0.55, 0.6, 0.65, 0.7]
        r = weighted_moving_average_forecast(history, steps=3)
        assert r.method == "weighted_moving_average"
        assert len(r.forecast) == 3


class TestAnomalyDetection:
    def test_point_anomaly_detected(self):
        """注入一个明显突变 → 应被检出"""
        series = [0.5] * 10 + [0.9] + [0.5] * 5
        r = detect_anomalies(series, window=5)
        assert 10 in r.point_anomalies

    def test_no_anomaly_normal_series(self):
        """平稳序列 → 无点异常"""
        series = [0.5 + 0.01 * (i % 3) for i in range(20)]
        r = detect_anomalies(series, window=5)
        # 允许少量误报，但不应大量
        assert len(r.point_anomalies) <= 3

    def test_drift_detected(self):
        """注入持续漂移 → CUSUM 应检出"""
        series = [0.5] * 8 + [0.7] * 10 + [0.5] * 5
        r = detect_anomalies(series, window=5, cusum_threshold=2.0)
        assert len(r.drift_anomalies) >= 1

    def test_z_scores_length(self):
        """Z-score 长度应与序列一致"""
        series = [0.5, 0.6, 0.55, 0.58, 0.52]
        r = detect_anomalies(series)
        assert len(r.z_scores) == len(series)
        assert len(r.cusum_positive) == len(series)
        assert len(r.cusum_negative) == len(series)


class TestAnalyzeSeries:
    def test_comprehensive_analysis(self):
        series = [0.6, 0.58, 0.55, 0.52, 0.5, 0.48, 0.45, 0.42, 0.4, 0.38]
        r = analyze_emotion_series(series, forecast_steps=3)
        assert "forecast" in r
        assert "anomalies" in r
        assert "summary" in r
        assert r["forecast"]["trend_slope"] < 0
        assert "下降" in r["forecast"]["trend_direction"]

    def test_warnings_on_decline(self):
        """持续下降 → 应有风险提示"""
        series = [0.7 - 0.03 * i for i in range(15)]
        r = analyze_emotion_series(series)
        assert len(r["summary"]["warnings"]) >= 1


class TestForecastAPI:
    def test_forecast_endpoint(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        resp = client.post("/api/emotion/forecast", json={
            "series": [0.6, 0.58, 0.55, 0.52, 0.5, 0.48, 0.45, 0.42],
            "steps": 3,
        })
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["forecast"]["values"]) == 3
        assert "anomalies" in data

    def test_forecast_short_series_400(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        resp = client.post("/api/emotion/forecast", json={"series": [0.5, 0.6], "steps": 3})
        assert resp.status_code == 400

    def test_forecast_invalid_value_400(self):
        from fastapi.testclient import TestClient
        from backend.main import app
        client = TestClient(app)
        resp = client.post("/api/emotion/forecast", json={"series": [0.5, 1.5, 0.6, 0.7, 0.8], "steps": 3})
        assert resp.status_code == 400
