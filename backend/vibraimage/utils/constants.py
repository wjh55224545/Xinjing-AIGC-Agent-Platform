"""
VibraImage常量定义。

所有统计常模、参数范围、已知相关系数均来自：
- VCE.pdf (Minkin, 2020) Table 6-18, Table 1
- 顾红梅 (2020) "基于震动影像技术的在押人员情绪状态评估"

数据来源说明:
- "All"列: 联合数据库10,266次测试的全群体统计
- "Med"列: VibraMed程序 (自由状态测试, N=4994)
- "MI"列: VibraMI程序 (刺激反应测试, N=3521)
- "PA"列: PsyAccent程序 (性格特征测试, N=1751)
- "ND": 正态分布理论值 (Normal Distribution)
"""

# ============================================================================
# 频率分析参数
# ============================================================================

FREQ_BAND = (0.1, 10.0)        # VibraImage有效频段 (Hz)
DEFAULT_FRAME_RATE = 30          # 默认摄像头帧率
DEFAULT_WINDOW_FRAMES = 100      # 默认每窗口帧数 (~3.3s @ 30fps)
DEFAULT_WINDOW_STRIDE = 50       # 窗口步长 (50%重叠)
FREQ_BINS = 100                  # 频率直方图bin数
FACE_ROI_SIZE = (224, 224)       # 人脸ROI缩放尺寸

# E3高频阈值 — 专著p76描述Tension"characterizes high-frequency processes
# of movement with a frequency of 30 Hz"，但由于有效频段为0.1-10Hz，
# 且EEG类比中使用f_max/2作为高频分界，默认取频段中位值3Hz
TENSION_HIGH_FREQ_THRESHOLD = 3.0

# E11的病理偏移常数 (p108: "coefficient of 0.5 Hz in the denominator
# of the calculation, as a threshold value of vibration frequency SD,
# values above which can indicate various types of psychophysiological
# pathology")
DEPRESSION_SIGMA_OFFSET = 0.5

# 帧差分噪声阈值 — 低于此值的差分视为传感器噪声置零
DIFF_NOISE_THRESHOLD = 1.0

# ============================================================================
# 参数常模值 (NORMAL_NORMS)
# 来源: VCE.pdf Table 6-18 "All"列 (联合数据库, N=10,266)
# 更新时间: 2020
# ============================================================================

NORMAL_NORMS = {
    # 负性情绪参数
    'aggression': 40.51,         # E1 — Table 6 (p63), M for All
    'stress': 31.17,             # E2 — Table 8 (p73), M for All
    'tension': 30.46,            # E3 — Table 9 (p77), M for All
    'suspicious': 28.33,         # E4 — Table 10 (p81), M for All

    # 正性情绪参数
    'balance': 61.64,            # E5 — Table 11 (p85), M for All
    'charm': 56.42,              # E6 — Table 12 (p89), M for All
    'energy': 46.11,             # E7 — Table 13 (p93), M for All
    'self_regulation': 55.25,    # E8 — Table 14 (p97), M for All

    # 生理情绪参数
    'inhibition': 24.87,         # E9 — Table 15 (p101), M for All
    'neuroticism': 31.34,        # E10 — Table 16 (p106), M for All
    'depression': 31.17,         # E11 — Table 17 (p110), M for All
    'happiness': 49.81,          # E12 — Table 18 (p114), M for All
}

# 参数标准差 (来自VCE.pdf各Table的SD)
NORMAL_SDS = {
    'aggression': 7.25,          # Table 6
    'stress': 7.54,              # Table 8
    'tension': 8.53,             # Table 9
    'suspicious': 6.28,          # Table 10
    'balance': 10.58,            # Table 11
    'charm': 13.09,              # Table 12
    'energy': 14.56,             # Table 13
    'self_regulation': 14.37,    # Table 14
    'inhibition': 11.33,         # Table 15
    'neuroticism': 12.80,        # Table 16
    'depression': 8.05,          # Table 17
    'happiness': 9.68,           # Table 18
}

# 标准化因子 (用于K值计算: m = 1/SD)
STANDARDIZATION_FACTORS = {
    'aggression': 1 / 7.25,
    'stress': 1 / 7.54,
    'tension': 1 / 8.53,
    'suspicious': 1 / 6.28,
    'balance': 1 / 10.58,
    'charm': 1 / 13.09,
    'energy': 1 / 14.56,
    'self_regulation': 1 / 14.37,
    'inhibition': 1 / 11.33,
    'neuroticism': 1 / 12.80,
    'depression': 1 / 8.05,
    'happiness': 1 / 9.68,
}

# ============================================================================
# 参数间Pearson相关系数矩阵 (VCE.pdf Table 1, p35-49)
# 仅收录 |r| > 0.4 的显著相关对
# ============================================================================

CORRELATION_MATRIX = {
    # 负性情绪 vs 正性/生理
    ('aggression', 'happiness'): -0.79,
    ('happiness', 'aggression'): -0.79,

    ('stress', 'charm'): -0.78,
    ('charm', 'stress'): -0.78,

    ('tension', 'suspicious'): 0.64,
    ('suspicious', 'tension'): 0.64,

    ('tension', 'neuroticism'): -0.53,
    ('neuroticism', 'tension'): -0.53,

    ('balance', 'depression'): -0.43,
    ('depression', 'balance'): -0.43,

    ('energy', 'depression'): -0.50,
    ('depression', 'energy'): -0.50,

    ('inhibition', 'neuroticism'): 0.52,
    ('neuroticism', 'inhibition'): 0.52,
}

# ============================================================================
# 情绪参数分组 (VCE.pdf p34, p117)
# ============================================================================

# Group 1: 负性情绪 (r > 0.4 between all members)
NEGATIVE_EMOTIONS = ['aggression', 'stress', 'tension', 'suspicious']

# Group 2: 正性情绪 (r > 0.4 between all members)
POSITIVE_EMOTIONS = ['balance', 'charm', 'energy', 'self_regulation']

# Group 3: 生理情绪参数 (E9-E12)
PHYSIOLOGICAL_EMOTIONS = ['inhibition', 'neuroticism', 'depression', 'happiness']

# Group 4: 心理生理参数 (r < 0.4 between all members)
PSYCHOPHYSIOLOGICAL_PARAMS = ['extraversion', 'stability', 'satisfaction']

# 完整参数列表
ALL_EMOTION_PARAMS = (
    NEGATIVE_EMOTIONS + POSITIVE_EMOTIONS + PHYSIOLOGICAL_EMOTIONS
)

# E4 Suspect 极值关闭算法参数 (p82)
# "additional to equation 6) that sets this value for Suspect level
# at abnormally high values based on Aggression-Stress pair
# and high Aggression level"
SUSPECT_ABNORMAL_THRESHOLD = 80.0  # 80%处有明显分布凸起

# ============================================================================
# 顾红梅论文中的K值解释阈值
# ============================================================================

K_INTERPRETATION = {
    (-float('inf'), 3): "稳定 — 接近常模，无明显异常",
    (3, 6): "轻度偏离 — 建议关注",
    (6, float('inf')): "显著偏离 — 建议专业评估",
}

# ============================================================================
# 情绪参数的中文名称映射
# ============================================================================

PARAM_NAMES_ZH = {
    'aggression': '攻击性',
    'stress': '压力',
    'tension': '紧张/焦虑',
    'suspicious': '可疑度',
    'balance': '平衡',
    'charm': '魅力',
    'energy': '活力',
    'self_regulation': '自我调节',
    'inhibition': '抑制',
    'neuroticism': '神经质',
    'depression': '抑郁',
    'happiness': '幸福',
    'stability': '稳定性',
    'extraversion': '外向性',
    'satisfaction': '满意度',
}
