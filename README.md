# 心镜 MindMirror

> 面向学生心理健康的智能评估与诊断平台 — 多模态情绪识别 + 自适应测验 + 虚拟被试合成数据 + 情绪预测预警

[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D.svg)](https://vuejs.org/)
[![VibraImage](https://img.shields.io/badge/引擎-VibraImage-purple.svg)]()
[![License](https://img.shields.io/badge/License-Apache%202.0-orange.svg)](LICENSE)

---

## 项目简介

**心镜 MindMirror** 是一个面向学生心理健康的智能评估与诊断平台。平台集成**多模态情绪识别**、**IRT 自适应测验**、**情绪预测与预警**、**焦虑抑郁风险分级筛查**四大核心技术，打造"量表高效施测、情绪多维融合、风险分级预警、筛查结果可复现"的智能心理评估闭环。

平台以**心理测量学理论**为基础（IRT 项目反应理论、Dempster-Shafer 证据理论、经典测量理论），以**AI 多模态融合**为技术支撑（面部情绪 + 前庭振动 + 心理量表），以**虚拟被试合成数据**为验证手段，解决学生心理健康筛查中真实数据隐私敏感难获取、量表施测耗时、单一模态可信度低、筛查结果无法验证等核心痛点。

### 一句话理解

**学生心理健康的"智能诊断台" — 多模态情绪识别 + 自适应测验 + 情绪预测预警 + 风险分级筛查，无需真实数据即可完成诊断算法验证与流程演示。**

---

## 核心特性

### 👁️ 三模态证据融合
- **面部情绪**：OpenCV 人脸检测 + 面部区域像素特征提取
- **前庭振动**：VibraImage 引擎分析头部微振动，E1-E12 情绪参数 + K 值
- **心理量表**：SAS/SDS/SCL-90/PSS-10/PANAS 标准化量表
- **D-S 证据理论融合**：替代固定权重，三类证据 mass 函数融合 + 冲突检测，冲突证据自动标记需人工复核
- 消融实验：三模态融合比最佳单模态准确率 **+12.3%**，比固定权重 **+8.7%**

### 🎯 分级响应模型自适应测验（GRM）
- 基于 IRT 3PL + 分级响应模型（GRM），直接建模多级评分（1-4 分）
- 最大信息量逐题推送 + EAP 能力估计，仅需全量表 **30-40%** 题量
- 等价性验证：7 题 vs 20 题，θ 相关 r=**0.92**，省题率 **65%**，高风险一致性 Kappa=**0.77**

### 🎓 虚拟被试合成数据引擎
- **18 种典型心理剖面**：健康对照/轻度焦虑/中度焦虑/抑郁倾向/考前压力/严重症状/社交焦虑/强迫症倾向/睡眠障碍/学习倦怠/人际敏感/惊恐发作倾向/躯体化障碍/自卑倾向/完美主义/情绪调节困难/创伤后应激倾向/进食障碍倾向
- 参数化生成完整量表作答 + E1-E12 前庭参数 + K 值，**隐藏真值**
- **用途一（核心）**：为诊断算法提供可复现的合成数据源——消融实验、信效度验证、等价性验证均基于此
- **用途二**：在无真实数据时演示完整诊断流程，保证系统可演示、结果可复现
- 所有虚拟被试标记 is_virtual=True，与真实学生数据严格隔离

### 📈 情绪预测与异常检测
- **趋势预测**：最小二乘线性趋势拟合 + 置信区间外推，MAE=**0.042**（比恒定基线降低 **27.3%**）
- **异常检测**：滑动窗口 Z-score（点异常，召回率 **99.8%**）+ CUSUM 累积和（漂移异常，检出率 **100%**）
- 前端可视化：预测曲线 + 置信区间 + 异常标记 + 智能风险提示

### 🔬 VibraImage 前庭振动引擎
- 基于 Viktor Minkin "Vibraimage, Cybernetics and Emotions" (2020) 专著
- 全链路：人脸检测 → 帧差分 → 频率分析 → E1-E12 情绪参数 → K 值
- E1-E12 白盒算法，每个参数有明确物理含义
- 支持 GPU 加速（MUSA / CUDA），自动探测降级

### 📋 心理量表自评
- **八种标准化量表**：SAS（焦虑，20 题）、SDS（抑郁，20 题）、SCL-90（症状，90 题/10 维度）、PSS-10（知觉压力，10 题）、PANAS（正负性情绪，20 题）、PHQ-9（抑郁筛查，9 题）、GAD-7（焦虑筛查，7 题）、BFI-10（大五人格，10 题）
- **自动计分引擎**：支持反向题、标准分公式、维度标准分
- 完整测评 + CAT 简版两种模式

### ✨ AIGC 内容生成
- 心理评估日报/周报
- 个性化干预方案（绿/黄/红三级）
- 家校沟通函（三级措辞）
- 学生成长叙事
- LLM 直接生成，不可用时自动降级模板模式

### 🧬 Agent 自进化引擎
- 反馈驱动进化：每次生成后自动记录经验（学生数据 + 生成结果 + 用户评分）
- 历史成功案例注入：生成时自动检索同类别高分案例注入 prompt
- 评分趋势追踪 + 低分自动标记
- 零外部依赖，仅 JSONL 文件 + prompt 注入

---

## 系统架构

![系统架构图](系统架构图.jpg)

心镜平台采用三层架构：

- **感知层**：面部情绪识别 + VibraImage 前庭振动分析（E1-E12 参数）+ 心理量表
- **融合层**：Dempster-Shafer 证据理论三模态融合 + IRT 自适应测验 + 情绪预测与异常检测
- **应用层**：Web 前端（9 个功能页面）+ 多智能体 AIGC + 虚拟被试合成数据 + 风险分级筛查

---

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+（仅前端开发时需要，生产部署使用预构建静态文件）
- （可选）GPU 支持：MUSA / CUDA

### 1. 克隆与安装

```bash
git clone https://github.com/wjh55224545/Xinjing-AIGC-Agent-Platform.git
cd Xinjing-AIGC-Agent-Platform

# 后端依赖
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# .venv\Scripts\activate    # Windows
pip install -r requirements.txt

# 前端依赖（仅开发时需要）
cd frontend
npm install
cd ..
```

### 2. 配置环境变量

```bash
cp .env.template .env
# 编辑 .env，填入 API Key（可选，不填则 AIGC 降级模板模式）
```

### 3. 构建前端（生产部署）

```bash
cd frontend
npm run build
cd ..
# 构建产物输出到 static/ 目录，后端自动托管
```

### 4. 启动后端

```bash
python run_backend.py
# 开发模式（热重载）：python run_backend.py --dev
```

### 5. 访问

- 前端页面：http://localhost:8000
- API 文档：http://localhost:8000/docs

---

## 功能页面

| 页面 | 路径 | 说明 |
|---|---|---|
| 仪表盘 | `/` | 系统概览、统计数据、快捷入口 |
| 情绪监测 | `/emotions` | 实时情绪监测、趋势预测、异常检测 |
| 预警面板 | `/alerts` | 情绪预警管理、干预记录 |
| 视频上传 | `/upload` | 视频上传、VibraImage 分析 |
| AIGC 报告 | `/aigc` | 心理报告、干预方案、沟通函生成 |
| 智能体面板 | `/agents` | 多智能体协作、ReAct 推理、SSE 流式 |
| 心理量表 | `/scales` | 八种标准化量表自评 + CAT 自适应 |
| 经典实验 | `/experiment` | 经典心理学实验（Stroop）、数据加载、实验演示 |
| 虚拟被试 | `/virtual-subject` | 虚拟被试合成数据、诊断流程演示、结果分析 |

---

## 项目结构

```
Xinjing/
├── backend/                    # 后端
│   ├── main.py                 # FastAPI 入口
│   ├── api/routes/             # API 路由
│   ├── services/               # 核心服务
│   │   ├── fusion.py           # 三模态证据融合（D-S）
│   │   ├── cat.py              # 自适应测验（IRT + GRM）
│   │   ├── virtual_subject.py  # 虚拟被试教学
│   │   ├── emotion_forecast.py # 情绪预测与异常检测
│   │   └── ...
│   └── models/                 # 数据模型
├── frontend/                   # 前端（Vue 3 + Vite）
│   ├── src/
│   │   ├── views/              # 页面组件
│   │   ├── components/         # 通用组件
│   │   ├── router/             # 路由
│   │   └── assets/styles/      # 设计系统
│   └── vite.config.js
├── static/                     # 前端构建产物（后端托管）
├── scripts/                    # 脚本
│   ├── ablation/               # 消融对照实验
│   ├── benchmark/              # 性能基准测试
│   └── ...
├── docs/                       # 技术文档
│   ├── ablation_report.md      # 消融对照实验报告
│   ├── cat_equivalence_report.md  # 自适应测验等价性报告
│   ├── emotion_forecast_report.md # 情绪预测与异常检测报告
│   └── ...
├── tests/                      # 测试（127 项）
├── data/                       # 数据（SQLite、常模）
├── run_backend.py              # 启动脚本
├── requirements.txt            # Python 依赖
├── DEPLOY.md                   # 部署指南
├── DEVELOPMENT_LOG.md          # 开发日志
├── CHANGELOG.md                # 变更日志
└── README.md
```

---

## 测试

```bash
# 运行全部测试
python -m pytest tests/ -v

# 预期：127 passed
```

测试覆盖：
- 量表计分引擎（SAS/SDS/SCL-90/PSS-10/PANAS）
- 自适应测验（IRT + GRM）
- 三模态证据融合
- 虚拟被试合成数据引擎
- 情绪预测与异常检测
- API 端点
- 合成数据与信效度验证

---

## 性能基准

```bash
python scripts/benchmark/performance_benchmark.py --iterations 50 --concurrency 50
```

参考性能（普通 PC）：
- API 端点均值响应：< 10ms
- 并发 10 吞吐量：> 700 req/s
- 情绪预测计算：< 5ms
- IRT θ 估计：< 10ms

---

## 文档

| 文档 | 说明 |
|---|---|
| [部署指南](DEPLOY.md) | 本地/Docker/云平台部署、Nginx 配置、国产化适配 |
| [开发日志](DEVELOPMENT_LOG.md) | 全部功能升级的完整记录（技术背景、改动、验证） |
| [变更日志](CHANGELOG.md) | 版本变更记录 |
| [消融对照实验报告](docs/ablation_report.md) | 三模态融合消融实验方法与结果 |
| [自适应测验等价性报告](docs/cat_equivalence_report.md) | CAT 与全量表等价性验证 |
| [情绪预测与异常检测报告](docs/emotion_forecast_report.md) | 预测/异常检测算法验证 |

---

## 技术栈

**后端**
- Python 3.11+ / FastAPI / Uvicorn
- SQLAlchemy ORM / SQLite（可切换 MySQL/PostgreSQL/达梦）
- NumPy / SciPy（IRT 计算、统计分析）
- OpenCV / PyTorch（VibraImage 引擎，支持 MUSA/CUDA GPU）

**前端**
- Vue 3 + Vite + Vue Router + Pinia
- ECharts（数据可视化）
- Axios（HTTP 客户端）
- 设计系统 v2.0（深色渐变 + 毛玻璃 + 微交互）

**算法理论**
- IRT 项目反应理论（3PL + GRM 分级响应模型）
- Dempster-Shafer 证据理论
- 经典测量理论（Cronbach's α、效标效度）
- 时间序列分析（线性趋势、Z-score、CUSUM）

---

## 国产化适配

平台采用纯 Python + Vue 技术栈，无专有硬件依赖，支持国产化环境：

- **操作系统**：统信 UOS / 麒麟 Kylin / 中科方德 / Windows
- **CPU 架构**：x86_64 / ARM64（鲲鹏/飞腾）/ MIPS（龙芯，需验证）
- **数据库**：SQLite / MySQL / 达梦 DM8 / PostgreSQL / 人大金仓 / OceanBase
- **GPU**：沐曦 MetaX（MUSA）/ NVIDIA（CUDA）/ CPU 降级
- **中间件**：Docker / 麒麟容器云 / Nginx / 东方通 TONGWEB

详见 [部署指南](DEPLOY.md) 国产化适配章节。

---

## License

Apache License 2.0
