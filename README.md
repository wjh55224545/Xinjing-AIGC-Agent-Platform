# 心镜·AIGC智能体平台 (MindMirror AIGC Agent Platform)

> 🏆 **第八届CCF开源创新大赛 · 国产开源GPU AI创新生态赛 任务三**
>
> 沐曦MetaX GPU国产算力 · 灵枢Lingshu-32B医疗大模型 · VibraImage前庭振动 · 多智能体AIGC协作

[![Python](https://img.shields.io/badge/Python-3.11+-green.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D.svg)](https://vuejs.org/)
[![GPU](https://img.shields.io/badge/GPU-沐曦MetaX-red.svg)](https://www.metax-tech.com/)
[![LLM](https://img.shields.io/badge/LLM-Qwen3--8B%20(moark.com)-blue.svg)](https://api.moark.com/v1)
[![VibraImage](https://img.shields.io/badge/引擎-VibraImage-purple.svg)]()

## 👥 团队信息

| 项目 | 内容 |
|------|------|
| **参赛队名** | 码到成功队 |
| **队　长** | 王建豪 |
| **联系方式** | 18928109264 |
| **组员名单** | 吴锴嘉、何柏翰 |
| **指导老师** | 刘寿强 |
| **参赛单位** | 华南师范大学 |
| **比赛名称** | 第八届CCF开源创新大赛 · 国产开源GPU AI创新生态赛 任务三 |

## 📖 项目简介

**心镜**是一个部署在智慧教室环境中的AIGC智能体系统。平台以**沐曦MetaX GPU国产算力**为底座，搭载**moark.com 平台 Qwen3-8B 大模型**作为核心推理引擎，集成**VibraImage前庭振动识别引擎**（Viktor Minkin专著公式体系），通过**5智能体协作架构**，实现从双模态情绪感知到AIGC心理内容生成的全流程智能化。

### 一句话理解

**教室里的"情绪CT机" + "AI心理报告生成器"——沐曦GPU驱动，moark.com Qwen3-8B大模型推理，VibraImage振动分析，多Agent协作，全流程AIGC。**

---

## 🎯 比赛适配说明

| 赛道要求 | 本项目实现 |
|---------|-----------|
| 基于国产算力平台 | ✅ 沐曦MetaX GPU + moark.com Qwen3-8B 大模型，全链路国产化 |
| AIGC能力 | ✅ Qwen3-8B 大模型驱动：心理报告、干预方案、家校沟通函、成长叙事（LLM直接生成，不可用时自动降级模板） |
| 多Agent协作 | ✅ 5智能体（感知→分析→报告→预警→协调），Qwen3-8B ReAct推理 |
| 产品化落地 | ✅ Web前后端 + Docker + API文档 + 56项测试全通过 |
| 开源合规 | ✅ Apache 2.0 License，完整文档 |

---

## 🏗️ 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                  前端 (Vue 3 + Vite + ECharts)               │
│  仪表盘 │ 情绪监测 │ AIGC报告 │ 预警面板 │ 智能体状态       │
└──────────────────────┬───────────────────────────────────────┘
                       │ HTTP REST + SSE 流式
┌──────────────────────▼───────────────────────────────────────┐
│               后端 (FastAPI + LangGraph)                      │
│                                                               │
│  ┌─────────────────────────────────────────────────────┐    │
│  │         多智能体协作系统 (5 Agents · 灵枢驱动)       │    │
│  │                                                      │    │
│  │  👁️ 感知智能体 ──→ 🧠 分析智能体                     │    │
│  │  双模态识别(面部+前庭)   12项指标+LSTM-Transformer    │    │
│  │       │                        │                     │    │
│  │       └────────┬───────────────┘                     │    │
│  │                ↓                                     │    │
│  │  ✨ AIGC报告智能体 ←──────→ 🔔 预警智能体            │    │
│  │  心理报告/方案/沟通函/叙事   三级预警+7渠道反馈       │    │
│  │                ↑________________↑                    │    │
│  │                    🎯 协调智能体                      │    │
│  └──────────────────────────────────────────────────────┘    │
│                                                               │
│  ┌───────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐     │
│  │ 情绪识别   │ │ VibraImage│ │ AIGC引擎 │ │ 反馈工具  │     │
│  │ (面部+前庭)│ │ 振动引擎 ★│ │ 4生成器  │ │ 7渠道    │     │
│  └───────────┘ └───────────┘ └──────────┘ └──────────┘     │
└──────────────────────┬───────────────────────────────────────┘
                       │ OpenAI 兼容 API
┌──────────────────────▼───────────────────────────────────────┐
│               国产AI算力平台                                  │
│  ┌──────────────────────┐ ┌──────────────┐ ┌──────────────┐ │
│  │ 灵枢 / Qwen3-8B      │ │ DeepSeek     │ │ 本地/自定义   │ │
│  │ ★ 主平台 · moark.com  │ │ ☆ 备用       │ │              │ │
│  │ OpenAI兼容·流式推理   │ │ 国产大模型    │ │              │ │
│  └──────────────────────┘ └──────────────┘ └──────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## ✨ 核心特性

### 🧠 moark.com Qwen3-8B 大模型 ★
- 通过 moark.com 平台 OpenAI 兼容 API 调用，支持流式推理和 reasoning
- 5个智能体的ReAct推理全部由该模型驱动
- 支持 `ExtraBodyChatOpenAI` 适配非标准API参数（如 `top_k`、`frequency_penalty`）
- AIGC 生成器优先 LLM 直接生成，不可用时自动降级模板模式
- 切换平台仅需改一行配置：`AI_PLATFORM=lingshu`

### 🔬 VibraImage前庭振动引擎 ★
- 基于Viktor Minkin "Vibraimage, Cybernetics and Emotions" (2020)专著
- 全链路：YOLOv8人脸检测 → 帧差分 → 频率分析 → E1-E12情绪参数 → K值
- E1-E12白盒算法，每个参数有明确物理含义，非黑盒神经网络
- 10,266人常模数据库，K值心理状态量化指标

### 👁️ 双模态情绪识别
- **面部微表情**：调用外部API分析面部肌肉运动单元
- **前庭振动**：VibraImage引擎分析头部微振动频率和空间分布
- 加权融合策略（面部0.6 + 前庭0.4），置信度差异>35%自动复核

### ✨ AIGC内容生成
- 📊 心理评估日报/周报
- 📋 个性化干预方案（绿/黄/红三级）
- ✉️ 家校沟通函（三级措辞，温和不引起恐慌）
- 📈 学生成长叙事

### 🚨 三级预警系统
- 🟢 绿色：看板 + APP推送
- 🟡 黄色：+ 微信班主任通知
- 🔴 红色：全渠道（微信+短信+邮件+电话），自动生成P0紧急工单

---

## 🏫 应用场景

### 智慧教室日常监测
- 部署于智慧教室环境中，通过摄像头定时采集学生面部视频
- 每15分钟自动运行内环流程，完成全班双模态情绪采集
- 每日22:00自动运行外环流程，生成全班心理健康日报

### 心理健康预警与干预
- 🟢 绿色状态：看板记录，APP推送日常情绪状态
- 🟡 黄色预警：自动通知班主任，生成干预建议方案
- 🔴 红色预警：全渠道通知（微信+短信+邮件+电话），自动生成P0紧急工单，通知心理教师立即介入

### AIGC内容生成
- **心理教师**：每日自动获取全班心理健康日报/周报，替代手工记录
- **班主任**：收到学生情绪关注通知和家校沟通函草稿
- **家长**：收到专业、温和的学生情绪状态反馈函
- **学校管理**：通过仪表盘总览全校心理健康态势

### 家校协同
- 自动生成三级措辞的家校沟通函（温和→关注→紧急）
- 红色预警时自动通知家长并安排心理教师跟进
- 长期积累的学生成长叙事可用于学期心理成长档案

### 科研数据支撑
- E1-E12前庭振动参数 + 12项心理健康指标的完整时序数据
- 支持数据导出，可用于心理学/教育学学术研究
- 10,266人常模数据库提供统计基准参考

---

## 📊 结果及其展示

### 仪表盘主页面

系统主仪表盘提供一站式心理健康管理视图：

- **核心指标卡片**：学生总数、今日平均情绪评分、活跃预警数量
- **7日情绪趋势图**：ECharts折线图展示全班情绪动态变化
- **预警分布图**：仪表盘式图表展示绿/黄/红三级预警分布
- **最近情绪记录表**：实时更新的最新10条情绪识别记录
- **系统控制面板**：手动触发实时采集和每日分析，SSE实时流式窗口

### AIGC报告生成示例

**心理评估日报**包含以下结构化内容：
1. 情绪概况段落（自然语言描述）
2. 5项关键指标表格（综合评分/情绪稳定性/积极情绪占比/负面情绪占比/情绪趋势）
3. 关键发现（情绪突变检测、主导情绪、情绪波动等）
4. 风险分析（基于12项指标和LSTM-Transformer预测）
5. 明日预测（95%置信区间）
6. 个性化建议措施

**个性化干预方案**按风险等级分为：
- 🟢 绿色方案：维护性建议，保持良好状态
- 🟡 黄色方案：包含关注跟踪计划和活动引导建议
- 🔴 红色方案：包含紧急干预步骤、家校联动方案、一对一访谈安排

### 智能体协作SSE流式展示

前端Agent面板支持通过SSE实时观看5智能体协作全过程：
1. `thought` 事件 — 协调智能体发布调度思考
2. `action` 事件 — 当前智能体开始执行任务（含工具名和输入参数）
3. `observation` 事件 — 智能体执行结果（含完整输出数据）
4. `final` 事件 — 协调智能体汇总最终结果
5. `error` 事件 — 异常信息（如有）

### 测试验证结果

| 测试模块 | 测试数量 | 通过率 | 覆盖内容 |
|---------|:------:|:-----:|---------|
| 平台适配器 | 7 | 100% | 灵枢/DeepSeek/本地平台初始化、Fallback |
| AIGC生成器 | 10 | 100% | 报告/方案/沟通函/叙事生成与格式验证 |
| 多智能体 | 9 | 100% | 智能体初始化、ReAct流程、工具调用 |
| 状态机端到端 | 30 | 100% | 内环/外环完整流程、SSE事件推送 |
| **合计** | **56** | **100%** | **全模块覆盖** |

```bash
# 运行全部测试
python -m pytest tests/ -v

# 预期输出
# tests/test_platform_adapter.py::test_xxxx PASSED  [ 1/56]
# ...
# ==================== 56 passed in 2.34s ====================
```

### 中文API文档

启动后端后访问 `http://localhost:8000/docs` 可查看完整的中文Swagger UI交互式API文档，支持在线测试所有端点。

### 数据库Schema

```
students — 学生表
  ├─ id, name, class_name, student_code, baseline_mood
  └─ school, grade, teacher_name, parent_phone

emotion_records — 情绪记录表（含VibraImage完整参数）
  ├─ 基础: student_id, image_path, recorded_at
  ├─ 面部: facial_emotion/conf/valence/arousal
  ├─ 前庭: vestibular_valence/arousal/confidence/intensity
  ├─ VibraImage: E1-E12全套参数 + K值
  ├─ 融合: fused_emotion/score/valence/arousal
  └─ 质量: confidence_diff, requires_review

daily_reports — 每日分析报告表
alerts — 预警记录表
```

---

## 🚀 快速启动

### 1. 环境准备

```bash
cd 心镜AIGC智能体平台
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

### 2. 配置灵枢 Lingshu-32B

```bash
cp .env.template .env
```

编辑 `.env`，填入灵枢配置：

```bash
AI_PLATFORM=lingshu
LINGSHU_API_KEY=你的moark平台API密钥
LINGSHU_BASE_URL=https://api.moark.com/v1
LINGSHU_MODEL=Qwen3-8B

# 备用平台（灵枢不可用时自动切换）
AI_FALLBACK_PLATFORMS=deepseek
DEEPSEEK_API_KEY=你的DeepSeek密钥
```

> 🛡️ `.env` 已在 `.gitignore` 中，不会被提交到 Git。

### 3. 启动后端

```bash
python run_backend.py
```

浏览器访问：
- 🇨🇳 **中文 API 文档**：http://localhost:8000/docs
- ✅ 健康检查：http://localhost:8000/api/health
- 🔬 VibraImage引擎状态：http://localhost:8000/api/vibraimage/health

### 4. 启动前端（需 Node.js 18+）

```bash
cd frontend
npm install
npm run dev
# 访问 http://localhost:5173
```

### 5. Docker 一键部署

```bash
docker-compose up -d
# 后端: http://localhost:8000  前端: http://localhost:5173
```

### 6. 运行测试

```bash
python -m pytest tests/ -v
# 预期: 56项测试全部通过
```

---

## 📡 API 接口

| 分类 | 端点 | 说明 |
|------|------|------|
| 系统 | `GET /api/health` | 健康检查 + 平台信息 |
| 仪表盘 | `GET /api/dashboard/summary` | 仪表盘数据 |
| 学生 | `GET /api/students` | 学生列表 |
| 预警 | `GET /api/alerts` | 预警列表 |
| 上传 | `POST /api/upload/video` | 上传视频触发采集 |
| **AIGC** | `POST /api/aigc/report/daily` | **Qwen3-8B 生成心理评估日报** |
| **AIGC** | `POST /api/aigc/plan/intervention` | **Qwen3-8B 生成干预方案** |
| **AIGC** | `POST /api/aigc/letter/parent` | **Qwen3-8B 生成家校沟通函** |
| **AIGC** | `POST /api/aigc/narrative/growth` | **Qwen3-8B 生成成长叙事** |
| 智能体 | `GET /api/agents/info` | 多智能体系统信息 |
| 智能体 | `GET /api/agents/platform` | 国产算力平台信息 |
| 智能体 | `POST /api/agents/trigger/inner` | 触发情绪采集 |
| 智能体 | `POST /api/agents/trigger/outer` | 触发每日分析 |
| **VibraImage** | `GET /api/vibraimage/health` | **引擎状态检查 ★** |
| **VibraImage** | `POST /api/vibraimage/analyze` | **视频振动分析 ★** |

---

## 📖 使用说明

### 1. 系统初始化

启动后端服务后，首先需要在系统中添加学生信息：

```bash
# 通过 Swagger UI 操作: http://localhost:8000/docs
# 方式一: 使用 /api/students 的 POST 接口逐个添加
# 方式二: 使用 /api/students/batch 批量导入学生
```

### 2. 配置AI算力平台

```bash
# 编辑 .env 文件切换AI平台
AI_PLATFORM=lingshu     # 使用 moark.com Qwen3-8B (推荐)
AI_PLATFORM=gitee_ai    # 使用 Gitee.AI 平台
AI_PLATFORM=deepseek    # 使用 DeepSeek (备用)
```

### 3. 日常使用流程

**自动模式（推荐）**：
系统启动后会自动运行定时任务：
- **每15分钟**：自动触发内环流程，对全班学生执行双模态情绪采集
- **每日22:00**：自动触发外环流程，执行深度分析→AIGC报告生成→预警分发

**手动模式**：
通过前端仪表盘或API手动触发：
```bash
# 手动触发情绪采集（内环）
curl -X POST http://localhost:8000/api/agents/trigger/inner

# 手动触发每日分析（外环，分析→报告→预警全流程）
curl -X POST http://localhost:8000/api/agents/trigger/outer

# 生成某学生的心理评估日报
curl -X POST http://localhost:8000/api/aigc/report/daily \
  -H "Content-Type: application/json" \
  -d '{"student_name": "张三", "date": "2026-07-10", "emotion_data": {}, "analysis_result": {}}'

# 生成家校沟通函
curl -X POST http://localhost:8000/api/aigc/letter/parent \
  -H "Content-Type: application/json" \
  -d '{"student_name": "张三", "class_name": "高一3班", "risk_level": "green", "emotion_summary": "情绪状态良好", "suggestions": ["保持良好作息"], "teacher_name": "李老师"}'

# 生成个性化干预方案
curl -X POST http://localhost:8000/api/aigc/plan/intervention \
  -H "Content-Type: application/json" \
  -d '{"student_name": "张三", "risk_level": "yellow", "risk_factors": ["情绪波动偏大"], "indicators": {}}'
```

### 4. 上传视频/图片触发分析

```bash
# 上传图片触发情绪识别
curl -X POST http://localhost:8000/api/upload/image \
  -F "file=@test_photo.jpg" \
  -F "student_id=1"

# 上传视频触发双模态分析
curl -X POST http://localhost:8000/api/upload/video \
  -F "file=@classroom_video.mp4" \
  -F "student_id=1"
```

### 5. 实时监控智能体协作

```bash
# 1. 启动一个触发操作，获取 run_id
# 2. 通过 SSE 端点订阅实时事件流
curl -N http://localhost:8000/api/sse/stream/{run_id}
```

前端Agent面板(`/agents`)提供可视化SSE流式窗口，实时展示多智能体的思考→行动→观察→最终结果全过程。

### 6. 查询与分析

```bash
# 查看仪表盘汇总
curl http://localhost:8000/api/dashboard/summary

# 查看预警列表
curl http://localhost:8000/api/alerts

# 查看学生详情及历史情绪记录
curl http://localhost:8000/api/students/1

# 查看多智能体系统状态
curl http://localhost:8000/api/agents/info

# 查看当前使用的算力平台
curl http://localhost:8000/api/agents/platform
```

### 7. 前端页面导航

| 路由 | 页面 | 说明 |
|------|------|------|
| `/` | 仪表盘 | 核心指标、情绪趋势图、预警分布、系统控制 |
| `/emotions` | 情绪监测 | 学生情绪实时监测详情 |
| `/alerts` | 预警面板 | 预警列表、筛选、确认操作 |
| `/students/:id` | 学生详情 | 单个学生完整心理档案 |
| `/upload` | 视频上传 | 上传视频/图片触发分析 |
| `/aigc` | AIGC报告 | AIGC报告生成与查看 |
| `/agents` | 智能体面板 | 5智能体状态 + SSE流式协作展示 |

---

## 📁 项目结构

```
心镜AIGC智能体平台/
├── backend/
│   ├── agents/              # 5智能体（灵枢ReAct推理）
│   ├── aigc/                # AIGC引擎（灵枢驱动生成）
│   ├── vibraimage/          # ★ VibraImage前庭振动引擎（18个文件）
│   │   ├── pipeline/        #    主引擎 + YOLOv8人脸检测
│   │   ├── core/            #    帧差分/频率分析/直方图/空间/频谱
│   │   ├── emotions/        #    E1-E12参数 + K值计算
│   │   └── utils/           #    10,266人常模数据
│   ├── llm/                 # AI平台适配层（moark/DeepSeek/本地）
│   ├── graph/               # LangGraph双环状态机
│   ├── tools/               # 情绪识别/VibraImage/心理分析/反馈/OBS
│   ├── api/routes/          # REST API（含VibraImage端点）
│   ├── models/              # ORM（含VibraImage E1-E12字段）
│   └── main.py              # FastAPI入口
├── data/
│   └── yolov8n.pt           # ★ YOLOv8n人脸检测模型
├── frontend/                # Vue 3 前端
├── tests/                   # 56项测试
├── docker-compose.yml
├── .env.template            # 环境变量模板（含灵枢配置）
├── requirements.txt         # 含opencv/scipy/ultralytics
└── README.md
```

---

## 🛠️ 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| **主推理引擎** | **moark.com Qwen3-8B** | **沐曦GPU · OpenAI兼容API ★** |
| 备用推理 | DeepSeek | 自动Fallback |
| 前庭振动 | VibraImage + YOLOv8n | Minkin专著公式体系 ★ |
| 后端 | FastAPI + LangGraph | 异步Web + AI编排 |
| 前端 | Vue 3 + Vite + ECharts | 响应式仪表盘 |
| 数据库 | SQLite + SQLAlchemy | 轻量级ORM |
| 部署 | Docker + docker-compose | 一键部署 |
| 通信 | SSE (Server-Sent Events) | 实时流式推送 |

---

> **比赛信息**: 第八届CCF开源创新大赛 · 沐曦国产开源GPU AI创新生态赛
>
> **任务**: 任务三 - 基于国产算力平台的AIGC与智能体开发与应用
>
> **算力支持**: 沐曦MetaX GPU + moark.com Qwen3-8B 大模型
