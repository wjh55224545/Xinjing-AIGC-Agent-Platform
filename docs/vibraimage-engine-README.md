# VibraImage Engine v0.2.0

基于头部微振动（head micromovement）信号的情绪识别引擎。

从视频中提取人脸区域的微小振动信号，经过**信号处理 → 情绪映射**两层流水线，输出 E1-E12 情绪参数和 10 类情绪分类。

> **v0.2.0 更新**：短视频容错修复 + 新增 L2 情绪映射层。
> 理论基础: Viktor Minkin "Vibraimage, Cybernetics and Emotions" (2020)

---

## 两层架构

```
┌─────────────────────────────────────────────────────┐
│              第一层：信号 → E1-E12 参数               │
│                                                     │
│  视频 → 人脸检测 → 帧差分 → 逐像素频率分析             │
│       → 直方图 + 空间分析 + 频谱 → E1-E12 + K值       │
│                                                     │
│  输入: .mp4 / 帧序列                                 │
│  输出: E1-E12 (12维情绪参数) + K值 + P14 Stability    │
│  方法: 经典信号处理（过零率/FFT + 统计矩）              │
│  依赖: OpenCV, NumPy, SciPy, YOLOv8                  │
└─────────────────────────────────────────────────────┘
                         │
                         ▼  12维向量
┌─────────────────────────────────────────────────────┐
│              第二层：参数 → 情绪 ★ 新增                │
│                                                     │
│  E1-E12 → Z-Score → 加权求和 → Sigmoid               │
│         → 效价 + 唤醒度 + 强度 → 10类情绪分类          │
│                                                     │
│  输入: E1-E12 (12维向量) + K值                        │
│  输出: 效价[0,1], 唤醒度[0,1], 强度[0,1], 情绪标签     │
│  方法: 线性加权 + Sigmoid压缩 + 欧氏距离最近邻          │
│  依赖: NumPy, PyYAML                                 │
└─────────────────────────────────────────────────────┘
```

---

## 快速开始

### Python API

```python
# ---- L1: 信号 → E1-E12 ----
from vibraimage.pipeline.engine import VibraImageEngine

engine = VibraImageEngine(window_frames=100, window_stride=50)
result = engine.process_video("video.mp4")

emotions = result.to_dict()['emotions']
# → {'aggression': 35.2, 'stress': 42.1, 'tension': 38.7, ...}
print(f"K值: {result.K_value:.2f}")

# ---- L2: E1-E12 → 情绪 ----
from vibraimage.mapping.emotion_mapper import EmotionMapper

mapper = EmotionMapper()
emotion = mapper.map(emotions, K=result.K_value)
print(f"效价: {emotion.valence:.2f}, 唤醒度: {emotion.arousal:.2f}")
print(f"情绪: {emotion.emotion_label}")

# 保存结果
result.to_json("output.json")
```

### CLI（仅 L1）

```bash
python -m vibraimage video.mp4 --output result.json
python -m vibraimage video.mp4 --window-frames 60 --method fft -v
```

---

## E1-E12 参数速查

### 基础参数

| 参数 | 含义 | 维度 | 核心公式 |
|------|------|------|----------|
| **E1 Aggression** | 攻击性 | 统计 | `F_max × σ / (2 × F_in) × 100%` |
| **E2 Stress** | 压力 | 空间 | `[1 − (振幅不对称 + 频率不对称)] × 100%` |
| **E3 Tension** | 紧张/焦虑 | 频域 | `P(f>3Hz) / P(total) × 100%` |

### 派生参数

| 参数 | 含义 | 数据来源 |
|------|------|----------|
| **E4 Suspect** | 可疑度 | `(E1+E2+E3)/3`，含极值钳位 |
| **E5 Balance** | 心理平衡 | 情绪参数的窗口间变异性 |
| **E6 Charm** | 魅力 | 全时段 L/R 空间对称性聚合 |
| **E7 Energy** | 活力 | 直方图峰值计数 − 标准差 |
| **E8 Self-Regulation** | 自我调节 | E5/E6 稳定性 |
| **E9 Inhibition** | 抑制/制动 | F1 频率平均周期 / 总时长 |
| **E10 Neuroticism** | 神经质 | `10 × σ(E9各窗口)` |
| **E11 Depression** | 抑郁 | `σ / (0.5 + M) × 100%` |
| **E12 Happiness** | 幸福 | `I / (I+E+ΔI+ΔE) × 100%` |

### K 值 — 综合偏离度指标

| \|K\| | 含义 |
|------|------|
| < 3 | 稳定，接近常模 |
| 3-6 | 轻度偏离，建议关注 |
| ≥ 6 | 显著偏离，建议专业评估 |

---

## L2 映射层详解

### 工作流程

```
E1-E12 原始值
    │
    ▼ Z-Score 标准化（基于 VCE 10,266 人常模）
z_i = (E_i − μ_i) / σ_i
    │
    ▼ 加权求和
V_raw = Σ(z_i × w_valence_i)
A_raw = Σ(z_i × w_arousal_i)
    │
    ▼ Sigmoid 压缩 (T=2.5)
valence = 1/(1+exp(−V_raw/T))
arousal = 1/(1+exp(−A_raw/T))
    │
    ▼ 欧氏距离 → 10 类情绪最近邻
情绪标签 (10选1)
```

### 权重矩阵

| 参数 | 效价权重 | 唤醒度权重 |
|------|:--:|:--:|
| aggression | −0.8 | +0.7 |
| stress | −0.7 | +0.8 |
| tension | −0.7 | +0.7 |
| suspicious | −0.6 | +0.4 |
| balance | +0.6 | −0.3 |
| charm | +0.5 | +0.2 |
| energy | +0.3 | +0.8 |
| self_regulation | +0.6 | −0.5 |
| inhibition | −0.3 | −0.4 |
| neuroticism | −0.5 | +0.5 |
| depression | −0.7 | −0.6 |
| happiness | +0.9 | +0.2 |

初始权重基于文献先验。标注数据积累后可用 `calibrate.py` 通过 Pearson r 自动校正。

---

## 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `window_frames` | 100 | 每窗口帧数 (~3.3s @ 30fps) |
| `window_stride` | 50 | 窗口步长 (50% 重叠) |
| `freq_method` | `zerocross` | 频率法: `zerocross` / `fft` |
| `frame_rate` | 30.0 | 输入帧率 [fps] |
| `freq_band` | (0.1, 10.0) | 有效频段 [Hz] |
| `freq_bins` | 100 | 直方图 bin 数 |

短视频 (<100 帧) 自动适配：窗口缩小至可用帧数，不使用步长。

---

## v0.2.0 与 v0.1.0 差异

| 变更 | 说明 |
|------|------|
| **短视频容错修复** | `_process_windows()` 帧数不足时自动收缩窗口，不再抛异常 |
| **新增 L2 映射层** | `mapping/emotion_mapper.py` — Z-Score 标准化 + 加权 + Sigmoid + 10 类情绪分类 |
| **新依赖** | `PyYAML >= 6.0` (用于读取 `weights.yaml`) |

---

## 项目结构

```
vibraimage/
├── pipeline/
│   ├── engine.py             # 主引擎：视频 → E1-E12 (L1)
│   └── face_detector.py      # YOLOv8 人脸检测
├── core/
│   ├── frame_differencer.py   # 帧差分
│   ├── frequency_analyzer.py  # 逐像素频率分析
│   ├── histogram.py           # 频率直方图
│   ├── spatial_analyzer.py    # 空间对称性分析
│   └── spectral.py            # 频谱功率聚合
├── emotions/
│   ├── primary.py             # E1/E2/E3 基础参数
│   ├── derived.py             # E4-E12 派生参数
│   └── psychophysiological.py # P14/P15 + K值
├── mapping/          ★ 新增
│   ├── emotion_mapper.py      # L2 映射引擎
│   ├── calibrate.py           # 权重校准
│   └── weights.yaml           # 权重 + 情绪区域定义
└── utils/
    ├── constants.py           # 10,266 人常模数据
    ├── validation.py          # 参数验证
    └── visualization.py       # 可视化工具
```

---

## 参考文献

位于 `项目参考资料/` 目录：

1. **VCE.pdf** — Minkin, V. A. (2020). *Vibraimage*. 情绪参数公式（Ch4）、常模表（Tables 6-18）、相关系数矩阵（Table 1）
2. **VI_emotions_model.pdf** — 情绪模型
3. **Vibraimage_monograph.pdf** — Vibraimage 专著
4. **VI8ManualEngLite8_1产品说明书.pdf** — 产品说明书
5. **VIBRA2022_01en.pdf** — 2022 文献
6. 顾红梅 (2020) — 基于震动影像技术的在押人员情绪状态评估（K 值解释阈值）
