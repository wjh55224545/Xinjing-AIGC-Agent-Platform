from __future__ import annotations
from typing import TypedDict, List
from typing_extensions import NotRequired


class InnerLoopState(TypedDict):
    """内环状态定义 - 实时情绪采集"""
    student_id: int
    video_path: str
    trigger_type: str

    # 面部微表情识别结果
    facial_emotion: NotRequired[str]
    facial_conf: NotRequired[float]
    facial_valence: NotRequired[float]
    facial_arousal: NotRequired[float]

    # 前庭振动识别结果
    vestibular_valence: NotRequired[float]
    vestibular_arousal: NotRequired[float]
    vestibular_confidence: NotRequired[float]
    vestibular_intensity: NotRequired[float]

    # VibraImage E1-E12 + K值参数
    vi_aggression: NotRequired[float]
    vi_stress: NotRequired[float]
    vi_tension: NotRequired[float]
    vi_suspect: NotRequired[float]
    vi_balance: NotRequired[float]
    vi_charm: NotRequired[float]
    vi_energy: NotRequired[float]
    vi_self_regulation: NotRequired[float]
    vi_inhibition: NotRequired[float]
    vi_neuroticism: NotRequired[float]
    vi_depression: NotRequired[float]
    vi_happiness: NotRequired[float]
    vi_stability: NotRequired[float]
    vi_K_value: NotRequired[float]
    vi_K_interpretation: NotRequired[str]
    vi_n_windows: NotRequired[int]
    vi_duration_sec: NotRequired[float]

    # 融合结果
    fused_emotion: NotRequired[str]
    fused_score: NotRequired[float]
    fused_valence: NotRequired[float]
    fused_arousal: NotRequired[float]

    # 质量指标
    confidence_diff: NotRequired[float]
    requires_review: NotRequired[bool]
    baseline_deviation: NotRequired[float]
    estimated_accuracy: NotRequired[float]
    processing_time_ms: NotRequired[int]

    # 存储结果
    record_id: NotRequired[int]
    stored: NotRequired[bool]
    obs_key: NotRequired[str]
    obs_full_path: NotRequired[str]
    error: NotRequired[str]


class OuterLoopState(TypedDict):
    """外环状态定义 - 心理健康评估"""
    target_date: str
    student_ids: List[int]

    # 数据聚合结果
    daily_records: NotRequired[dict]

    # 分析结果（包含12项指标和LSTM-Transformer分析）
    analysis_results: NotRequired[dict]

    # 生成的预警
    alerts_generated: NotRequired[list]

    # 反馈发送结果
    feedback_sent: NotRequired[dict]

    # 错误信息
    error: NotRequired[str]


class AlertState(TypedDict):
    """预警状态"""
    alert_id: int
    student_id: int
    severity: str  # green/yellow/red
    student_name: str
    content: str
    risk_level: str
    risk_reason: str
    overall_score: float
    created_at: str


class MentalHealthIndicators(TypedDict):
    """12项心理健康指标"""
    # 基础统计
    avg_emotion: float
    variance: float
    trend: str
    trend_slope: float

    # 12项核心指标
    emotional_stability_index: float  # 情绪稳定性指数
    emotion_fluctuation_entropy: float  # 情绪波动熵值
    negative_emotion_accumulation: float  # 负面情绪累积度
    social_interaction_frequency: float  # 社交互动频次
    daily_emotion_trend: str  # 日间情绪趋势
    arousal_abnormality_index: float  # 唤醒度异常指数
    emotion_recovery_speed: float  # 情绪恢复速度
    sleep_quality_prediction: float  # 睡眠质量预测
    stress_accumulation_index: float  # 压力累积指数
    positive_emotion_ratio: float  # 积极情绪占比
    emotion_abrupt_change_count: int  # 情绪突变检测
    overall_mental_health_score: float  # 综合心理健康评分

    # 情绪分布
    emotion_distribution: dict
    negative_emotion_ratio: float
    positive_emotion_ratio: float
    baseline_deviation: float
