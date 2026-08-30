"""
情绪数据预处理器 (EmotionDataPreprocessor)
==========================================

功能说明：
- 从数据库/OBS拉取学生7天情绪时序数据
- 计算真实统计指标（均值/方差/熵/趋势等），为LLM生成结构化分析上下文
- 风险等级规则兜底校验
- 模板建议作为LLM补充

定位：数据预处理器 → 喂给 Lingshu-32B 做真正的智能分析。
心理分析、风险识别、趋势预测等语义理解任务由LLM完成。
"""

from __future__ import annotations
import math
from datetime import datetime
from typing import Optional, List
from backend.tools.base import BaseTool, ToolResult


# 负面情绪列表
NEGATIVE_EMOTIONS = ["悲伤", "焦虑", "愤怒", "恐惧", "厌恶"]

# 正面情绪列表
POSITIVE_EMOTIONS = ["开心", "平静"]


class EmotionDataPreprocessor(BaseTool):
    """情绪数据预处理器 — 计算统计指标，为LLM分析提供结构化上下文"""

    name = "情绪数据预处理"
    description = (
        "预处理学生7天情绪时序数据，计算统计指标（稳定性、熵、趋势等），"
        "为Lingshu-32B医疗大模型提供结构化分析上下文。"
    )

    def __init__(self):
        super().__init__()
        self._analysis_count = 0

    def execute(
        self,
        student_id: int = 0,
        records: list | None = None,
        baseline: float = 0.7,
        obs_records: list | None = None,
        analysis_window_days: int = 7,
        **kwargs
    ) -> ToolResult:
        """
        预处理情绪数据，生成结构化分析上下文

        Args:
            student_id: 学生ID
            records: 情绪记录列表（当天数据）
            baseline: 历史情绪基线
            obs_records: 从OBS拉取的7天历史数据
            analysis_window_days: 分析窗口天数（默认7天）
        """
        self._analysis_count += 1

        try:
            # 步骤1: 合并当天记录和历史记录
            all_records = self._merge_records(records, obs_records)

            # 步骤2: 提取情绪时间序列
            emotion_series = self._extract_emotion_series(all_records)

            # 步骤3: 计算统计指标
            indicators = self._calculate_indicators(
                emotion_series, baseline, all_records
            )

            # 步骤4: 规则兜底风险等级判定
            risk_level, risk_reason = self._determine_risk_level(indicators)

            # 步骤5: 生成模板建议（LLM补充）
            suggestions = self._generate_suggestions(risk_level, indicators)

            # 步骤6: 计算综合评分
            overall_score = indicators.get("overall_mental_health_score", 0.5)

            return ToolResult(
                success=True,
                data={
                    # 基本统计
                    "avg_emotion": round(indicators["avg_emotion"], 3),
                    "variance": round(indicators["variance"], 4),
                    "trend": indicators["trend"],
                    "attention_score": round(1 - overall_score, 3),
                    "baseline": baseline,
                    "baseline_deviation": round(abs(indicators["avg_emotion"] - baseline), 3),

                    # 统计指标
                    "indicators": indicators,

                    # 规则兜底
                    "risk_level": risk_level,
                    "risk_reason": risk_reason,
                    "overall_score": round(overall_score, 3),

                    # 模板建议
                    "suggestions": suggestions,

                    # 情绪分布统计
                    "emotion_distribution": indicators["emotion_distribution"],
                    "negative_emotion_ratio": round(indicators["negative_emotion_ratio"], 3),
                    "positive_emotion_ratio": round(indicators["positive_emotion_ratio"], 3),

                    # 风险因素
                    "risk_factors": self._identify_risk_factors(indicators),
                    "protective_factors": self._identify_protective_factors(indicators),

                    # 元数据
                    "records_analyzed": len(all_records),
                    "analysis_window_days": analysis_window_days,
                    "analyzed_at": datetime.now().isoformat(),
                },
            )

        except Exception as e:
            return ToolResult(
                success=False,
                data={},
                error=f"数据预处理失败: {str(e)}"
            )

    def _merge_records(self, records: list | None, obs_records: list | None) -> list:
        """合并当天记录和历史记录"""
        current = records or []
        history = obs_records or []
        return current + history

    def _extract_emotion_series(self, records: list) -> list:
        """提取情绪分数时间序列"""
        series = []
        for record in records:
            score = record.get("fused_score")
            if score is not None:
                series.append({
                    "timestamp": record.get("timestamp") or record.get("recorded_at", datetime.now().isoformat()),
                    "score": score,
                    "emotion": record.get("fused_emotion", "未知"),
                    "valence": record.get("fused_valence", record.get("facial_valence", 0)),
                    "arousal": record.get("fused_arousal", record.get("facial_arousal", 0)),
                })
        return series

    def _calculate_indicators(
        self,
        emotion_series: list,
        baseline: float,
        records: list
    ) -> dict:
        """计算真实统计指标（不做任何LLM级别的分析）"""
        if not emotion_series:
            return self._default_indicators(baseline)

        scores = [s["score"] for s in emotion_series]

        # 1. 平均情绪得分
        avg_emotion = sum(scores) / len(scores) if scores else baseline

        # 2. 情绪方差
        variance = sum((s - avg_emotion) ** 2 for s in scores) / len(scores) if len(scores) > 1 else 0.01

        # 3. 情绪波动熵值 (Shannon熵)
        emotion_entropy = self._calculate_entropy(scores)

        # 4. 负面情绪累积度
        negative_count = sum(1 for s in emotion_series if s["emotion"] in NEGATIVE_EMOTIONS)
        negative_emotion_ratio = negative_count / len(emotion_series) if emotion_series else 0
        negative_accumulation = min(1.0, negative_emotion_ratio * 1.5)

        # 5. 正面情绪占比
        positive_count = sum(1 for s in emotion_series if s["emotion"] in POSITIVE_EMOTIONS)
        positive_emotion_ratio = positive_count / len(emotion_series) if emotion_series else 0

        # 6. 情绪趋势 (线性回归斜率)
        trend_slope = self._calculate_trend(scores)

        # 7. 情绪稳定性指数
        stability = max(0, 1 - math.sqrt(variance) * 2)

        # 8. 唤醒度异常指数
        arousals = [s.get("arousal", 0) for s in emotion_series]
        avg_arousal = sum(arousals) / len(arousals) if arousals else 0
        arousal_abnormality = abs(avg_arousal) if abs(avg_arousal) < 0.5 else 1.0

        # 9. 情绪恢复速度 (从负面恢复到正面的速度)
        recovery_speed = self._calculate_recovery_speed(emotion_series)

        # 10. 情绪突变检测
        abrupt_changes = self._detect_abrupt_changes(scores)

        # 11. 社交互动频次
        interaction_frequency = min(1.0, len(emotion_series) / 10)

        # 12. 综合心理健康评分 (纯统计加权)
        mental_health_score = self._compute_mental_health_score(
            stability, negative_accumulation, trend_slope, recovery_speed, positive_emotion_ratio
        )

        # 情绪分布
        emotion_distribution = {}
        for s in emotion_series:
            e = s.get("emotion", "未知")
            emotion_distribution[e] = emotion_distribution.get(e, 0) + 1

        # 趋势描述
        if trend_slope > 0.02:
            trend = "改善中"
        elif trend_slope < -0.02:
            trend = "下降中"
        else:
            trend = "稳定"

        return {
            "avg_emotion": round(avg_emotion, 3),
            "variance": round(variance, 4),
            "trend": trend,
            "trend_slope": round(trend_slope, 4),

            "emotional_stability_index": round(stability, 3),
            "emotion_fluctuation_entropy": round(emotion_entropy, 3),
            "negative_emotion_accumulation": round(negative_accumulation, 3),
            "social_interaction_frequency": round(interaction_frequency, 3),
            "daily_emotion_trend": trend,
            "arousal_abnormality_index": round(arousal_abnormality, 3),
            "emotion_recovery_speed": round(recovery_speed, 3),
            "stress_accumulation_index": round(negative_accumulation * 1.2, 3),
            "positive_emotion_ratio": round(positive_emotion_ratio, 3),
            "emotion_abrupt_change_count": abrupt_changes,
            "overall_mental_health_score": round(mental_health_score, 3),

            "emotion_distribution": emotion_distribution,
            "negative_emotion_ratio": round(negative_emotion_ratio, 3),
            "positive_emotion_ratio": round(positive_emotion_ratio, 3),

            "baseline_deviation": round(abs(avg_emotion - baseline), 3),
        }

    def _calculate_entropy(self, scores: list) -> float:
        """计算情绪波动的Shannon熵"""
        if not scores:
            return 0.0

        bins = [-0.1, 0.25, 0.45, 0.65, 0.85, 1.1]
        counts = [0] * 5

        for s in scores:
            for i in range(5):
                if bins[i] <= s < bins[i + 1]:
                    counts[i] += 1
                    break

        total = sum(counts)
        if total == 0:
            return 0.0

        entropy = 0.0
        for c in counts:
            if c > 0:
                p = c / total
                entropy -= p * math.log2(p)

        return entropy / math.log2(5)

    def _calculate_trend(self, scores: list) -> float:
        """计算情绪趋势（线性回归斜率）"""
        if len(scores) < 2:
            return 0.0

        n = len(scores)
        x = list(range(n))
        y = scores

        x_mean = sum(x) / n
        y_mean = sum(y) / n

        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def _calculate_recovery_speed(self, emotion_series: list) -> float:
        """计算情绪恢复速度"""
        if len(emotion_series) < 3:
            return 0.5

        transitions = 0
        for i in range(1, len(emotion_series)):
            prev = emotion_series[i - 1]["emotion"]
            curr = emotion_series[i]["emotion"]

            if prev in NEGATIVE_EMOTIONS and curr in POSITIVE_EMOTIONS:
                transitions += 1

        max_transitions = len(emotion_series) - 1
        return transitions / max_transitions if max_transitions > 0 else 0.5

    def _detect_abrupt_changes(self, scores: list) -> int:
        """检测情绪突变次数（分数变化超过30%为突变）"""
        if len(scores) < 2:
            return 0

        changes = 0
        for i in range(1, len(scores)):
            if scores[i - 1] > 0:
                change = abs(scores[i] - scores[i - 1]) / scores[i - 1]
                if change > 0.30:
                    changes += 1

        return changes

    def _compute_mental_health_score(
        self,
        stability: float,
        negative_accumulation: float,
        trend_slope: float,
        recovery_speed: float,
        positive_ratio: float
    ) -> float:
        """计算综合心理健康评分（统计加权，非LLM分析）"""
        score = (
            stability * 0.25 +
            (1 - negative_accumulation) * 0.20 +
            (trend_slope + 0.5) * 0.15 +
            recovery_speed * 0.20 +
            positive_ratio * 0.20
        )
        return max(0, min(1, score))

    def _determine_risk_level(self, indicators: dict) -> tuple:
        """
        规则兜底校验 — 纯if-else阈值判断。
        真正的风险分析由Lingshu-32B完成，这里只是安全网。
        """
        score = indicators.get("overall_mental_health_score", 0.5)

        red_indicators = []
        if score < 0.3:
            red_indicators.append("综合评分极低")
        if indicators.get("emotion_abrupt_change_count", 0) >= 3:
            red_indicators.append("频繁情绪突变")
        if indicators.get("negative_emotion_ratio", 0) > 0.6:
            red_indicators.append("负面情绪占比过高")

        yellow_indicators = []
        if 0.3 <= score < 0.5:
            yellow_indicators.append("综合评分偏低")
        if indicators.get("emotional_stability_index", 1) < 0.5:
            yellow_indicators.append("情绪稳定性差")
        if indicators.get("stress_accumulation_index", 0) > 0.5:
            yellow_indicators.append("压力累积")

        if red_indicators:
            return "red", "; ".join(red_indicators)
        elif len(yellow_indicators) >= 2 or score < 0.6:
            return "yellow", "; ".join(yellow_indicators) if yellow_indicators else "存在多项预警指标"
        elif score >= 0.7:
            return "green", "心理健康状态良好"
        else:
            return "yellow", "需要持续关注"

    def _generate_suggestions(self, risk_level: str, indicators: dict) -> list:
        """生成模板建议 — LLM在分析时会基于这些模板做个性化扩展"""
        suggestions = []

        if risk_level == "red":
            suggestions.append({
                "priority": "high",
                "category": "紧急干预",
                "content": "建议立即联系心理老师进行一对一访谈，密切关注学生状态变化。"
            })
            suggestions.append({
                "priority": "high",
                "category": "家校联动",
                "content": "建议与家长沟通，了解学生家庭情况，共同制定支持方案。"
            })
        elif risk_level == "yellow":
            suggestions.append({
                "priority": "medium",
                "category": "关注跟踪",
                "content": "建议班主任和心理委员密切关注该生近期的情绪变化，每周进行一次关怀性谈话。"
            })
            suggestions.append({
                "priority": "medium",
                "category": "活动引导",
                "content": "鼓励参加集体活动，增加正向情绪体验，提升社交互动频次。"
            })
        else:
            suggestions.append({
                "priority": "low",
                "category": "持续维护",
                "content": "继续保持良好的情绪管理，建议参与正向心理活动提升心理韧性。"
            })

        if indicators.get("emotion_fluctuation_entropy", 0) > 0.7:
            suggestions.append({
                "priority": "medium",
                "category": "情绪调节",
                "content": "情绪波动较大，建议学习情绪调节技巧，如深呼吸、正念冥想等。"
            })

        if indicators.get("negative_emotion_accumulation", 0) > 0.4:
            suggestions.append({
                "priority": "medium",
                "category": "压力疏导",
                "content": "存在负面情绪累积现象，建议寻求适当渠道进行情绪宣泄和压力疏导。"
            })

        if indicators.get("emotion_recovery_speed", 0) < 0.3:
            suggestions.append({
                "priority": "medium",
                "category": "恢复训练",
                "content": "情绪恢复速度较慢，建议进行情绪韧性训练，提升心理恢复能力。"
            })

        return suggestions

    def _identify_risk_factors(self, indicators: dict) -> list:
        """识别风险因素"""
        factors = []

        if indicators.get("negative_emotion_ratio", 0) > 0.4:
            factors.append("负面情绪占比偏高")

        if indicators.get("emotion_abrupt_change_count", 0) > 0:
            factors.append(f"存在{indicators['emotion_abrupt_change_count']}次情绪突变")

        if indicators.get("variance", 0) > 0.1:
            factors.append("情绪波动幅度较大")

        if indicators.get("trend_slope", 0) < -0.02:
            factors.append("情绪呈下降趋势")

        return factors if factors else ["无明显风险因素"]

    def _identify_protective_factors(self, indicators: dict) -> list:
        """识别保护因素"""
        factors = []

        if indicators.get("positive_emotion_ratio", 0) > 0.5:
            factors.append("正面情绪占比高")

        if indicators.get("emotional_stability_index", 0) > 0.7:
            factors.append("情绪稳定性良好")

        if indicators.get("emotion_recovery_speed", 0) > 0.5:
            factors.append("情绪恢复能力较强")

        if indicators.get("social_interaction_frequency", 0) > 0.6:
            factors.append("社交互动正常")

        return factors if factors else ["建议培养正向情绪体验"]

    def _default_indicators(self, baseline: float) -> dict:
        """默认指标（无数据时）"""
        return {
            "avg_emotion": baseline,
            "variance": 0.05,
            "trend": "稳定",
            "trend_slope": 0.0,
            "emotional_stability_index": 0.7,
            "emotion_fluctuation_entropy": 0.5,
            "negative_emotion_accumulation": 0.2,
            "social_interaction_frequency": 0.5,
            "daily_emotion_trend": "稳定",
            "arousal_abnormality_index": 0.3,
            "emotion_recovery_speed": 0.5,
            "stress_accumulation_index": 0.2,
            "positive_emotion_ratio": 0.6,
            "emotion_abrupt_change_count": 0,
            "overall_mental_health_score": 0.7,
            "emotion_distribution": {"中性": 10},
            "negative_emotion_ratio": 0.2,
            "positive_emotion_ratio": 0.6,
            "baseline_deviation": 0.0,
        }


# 向后兼容别名
MentalHealthAnalysisTool = EmotionDataPreprocessor
