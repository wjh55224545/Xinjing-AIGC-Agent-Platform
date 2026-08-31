# 更新日志

## v2.4.1（多模态融合 / GRM-CAT / 合成数据·信效度）— 2026-08-30

### 三模态 D-S 证据融合（升级1）
- 新增 `backend/services/fusion.py`：Dempster-Shafer 证据理论，焦点 {正性/负性/中性/未知Ω}，Ω 置信度折扣、冲突系数 K、复核机制、分歧解释
- 新增 `POST /api/fusion/three-modal`、`/api/fusion/two-modal`（main.py 注册）
- 相比旧固定权重（0.6面部+0.4前庭），消融实验提升 +1.8pp，且具备不确定性/冲突/复核可解释能力

### GRM 多级 CAT（升级2）
- `backend/services/cat.py` 新增 Samejima GRM 分级响应模型（多项似然 EAP、期望 Fisher 信息选题），`/api/scales/cat/start|next` 默认启用，保留 3PL 兼容

### 合成数据引擎 + 信效度套件（升级5）
- 新增 `backend/services/synthetic_data.py`（θ 驱动合成被试、IRT 生成作答、E1-E12 关联，is_synthetic 标记）
- `scale_stats.py` 新增 Cronbach α / 条目间相关 / 维度相关矩阵
- 新增 `GET /api/scales/validation/reliability`（合成被试信效度套件）

### 对照实验与测试
- 新增 `scripts/ablation/fusion_ablation.py` → `docs/ablation_report.md`（单/双/三模态 + 旧固定权重对比）
- 新增 `tests/test_upgrades.py` 21 项；全量 **97 passed**

### 虚拟被试教学闭环（升级5）
- 新增 `backend/services/virtual_subject.py`：6 个典型心理剖面库（健康/焦虑/抑郁/压力/严重症状）、生成器（隐藏真值）、自动批改引擎（量表等级40分+情绪30分+建议30分，相邻等级半分）
- 新增 `GET /api/virtual-subjects/profiles`、`POST /api/virtual-subjects/generate`、`POST /api/virtual-subjects/grade`
- 新增 `tests/test_virtual_subject.py` 16 项

### 自适应测验等价性验证（升级6）
- 新增 `scripts/ablation/cat_equivalence.py` → `docs/cat_equivalence_report.md`
- 7题 vs 20题：θ相关 r=0.92，省题率65%，高风险Kappa=0.77

### 情绪预测与异常检测（升级7）
- 新增 `backend/services/emotion_forecast.py`：线性趋势预测+置信区间、加权移动平均、Z-score点异常、CUSUM漂移检测
- 新增 `POST /api/emotion/forecast`
- 新增 `scripts/ablation/emotion_forecast_eval.py` → `docs/emotion_forecast_report.md`
- 预测MAE=0.042（比基线降27%），点异常召回99.8%，漂移检出100%
- 全量 **127 passed**

### 虚拟被试前端接入（升级8）
- 新增 `frontend/src/views/VirtualSubjectView.vue`：三步教学流程（选剖面→生成虚拟被试→学生诊断→自动批改），批改结果页含总分/明细/反馈/真值揭示
- 新增路由 `/virtual-subject`，侧边栏新增「🎓 虚拟被试演练」入口
- 前端构建验证通过，输出到 `static/` 由后端托管
- 端到端 API 验证：profiles/generate/grade 三端点均 200，评分逻辑正确

### 前端设计系统 v2.0（升级9）
- 全面重写 `main.css`：深色渐变侧边栏+毛玻璃顶部栏+精致卡片+渐变按钮+微交互动画+响应式三档断点
- `App.vue` 升级：侧边栏底部系统信息区（版本+运行状态），顶部栏实时时间显示
- 前端构建验证通过

### 情绪预测前端接入（升级10）
- 重写 `EmotionMonitorView.vue`：新增「趋势预测」按钮，调用预测 API
- 预测概览 4 卡片（趋势方向/步数/突变点/漂移段）+ 预测柱状图（含置信区间）+ 异常详情 + 智能风险提示

### 需求痛点文档化（升级11，文档已移至本地）
- 新增 `docs/需求痛点分析报告.md`：五大核心痛点深度分析+目标用户+优先级矩阵+差异化优势（已移至本地）
- 新增 `docs/教师需求问卷模板.md`：32题四部分问卷（基本信息/痛点评估/功能需求/使用意愿）（已移至本地）

### 方案可行性补强（升级12）
- 新增 `scripts/benchmark/performance_benchmark.py`：API响应时间+并发性能+核心算法效率基准测试
- `DEPLOY.md` 追加：Nginx反向代理+HTTPS、systemd服务管理、日志监控、数据备份
- `DEPLOY.md` 追加国产化适配：操作系统/CPU架构/数据库/中间件适配表+信创部署检查清单+性能参考

### 技术方案总结与展望（升级13，文档已移至本地）
- 新增 `docs/技术方案总结与展望.md`：技术体系总结+跨学科理论根基+应用价值+短中长期演进路线+风险应对（已移至本地）

## v2.4.0 — 2026-08

### 心理量表模块（完整补齐）
- 新增 `data/scales/` 五套标准量表题库：SAS(20题)、SDS(20题)、SCL-90(90题/10维度)、PSS-10(10题)、PANAS(20题)，题目标注论文来源（Zung 1965/1971、Derogatis 1975、Cohen 1983、Watson 1988）
- 计分引擎增强：反向题、标准分公式（raw×1.25 / 总均分×100 / 维度标准分）、0-base 计分（PSS-10）、SCL-90 十维因子分与 PANAS 双维度得分
- **CAT 自适应测验引擎**（`backend/services/cat.py`）：IRT 3PL 模型、EAP 能力估计、最大信息量选题，`POST /api/scales/cat/start`、`/api/scales/cat/next`
- **量表×AI 统计检验**（`backend/services/scale_stats.py`）：Pearson r、Cohen's Kappa、灵敏度/特异度/约登指数；`GET /api/scales/validation/summary` 全库效度统计
- 前端量表页支持完整测评 + CAT 简版两种模式

### 情绪教学实验组件
- 新增 `GET /api/vibraimage/norms` 常模端点（10,266 人、Z-Score 参数、E1-E12 中文名）
- 新增 `GET /api/vibraimage/latest` 最近情绪记录端点
- 新增前端教学实验页 `/experiment`：E1-E12 参数解释卡 + 个体 vs 常模雷达图 + K 值指数 + 实验指导书
- 新增实验报告生成器（`backend/aigc/experiment_generator.py`）：`POST /api/aigc/report/experiment` 生成符合心理测量课程规范的实验报告

### 试点工具链
- `GET /api/admin/pilot/export` — 按班级/年级分组导出试点数据 CSV
- `GET /api/admin/pilot/compare` — 系统 vs 人工计分耗时对比指标
- `GET /api/admin/pilot/report` — 试点成果报告摘要（覆盖/效度/反馈）
- `scripts/calibration/run_calibration_demo.py` — 权重校正演示（Pearson r 法）
- `docs/pilot/survey_template.md` — 需求调研问卷模板

### 工程收口
- 补齐 `parsers/output_parser.py`（智能体 LLM 输出解析器，工具白名单 + 容错 JSON），使 12 项 prompt 测试可运行
- 新增 `tests/test_scales.py`（21 项量表/CAT/统计检验/实验报告测试）
- 统一版本号 v2.4.0（config / health / admin stats / AIGC capabilities）
- 种子量表数据改为按标准题库计分；更新 README 测试统计（76 通过）

### 修复（v2.4.0 内补丁）
- 教学实验页"加载实验数据"失败：修复前端常模数据结构判断 bug；`/api/vibraimage/latest` 对无 E1-E12 字段的早期记录自动生成基于常模的演示参数（`demo=true`），保证教学演示可用
- `face_detector.py` 兼容 opencv>=5.0（不再捆绑 Haar Cascade XML）：多路径查找 + 无 XML 时退化为画面中央 ROI 模式，引擎不再崩溃
- 版本/标识统一：main.py、docker-compose.yml、report_agent.py、swagger-chinese.html、run_backend.py、README 底部的旧赛事标签统一为项目名称「心镜 MindMirror」
- 新增 `.env.example` 环境变量模板；`frontend/package.json` 版本统一为 2.4.0

## v2.1.0（阶段三）— 2026-07

### 工程优化
- 添加全局异常处理中间件
- 添加 API 请求限流（IP 级别滑动窗口）
- 添加 API 调用日志中间件（JSONL 日志 + 内存统计）
- 添加 LLM 调用统计（Token 消耗、耗时、成功率）
- 统一两套 Orchestrator 到 Graph 版
- 修复 .env 加载：从 `os.getenv` 改为 pydantic Settings
- 生产模式 Dockerfile（uvicorn workers + 健康检查）

### 云端部署
- 修复 Dockerfile（移除不存在的目录引用）
- 新增 `frontend/Dockerfile`（Node build + Nginx serve）
- 新增 `frontend/nginx.conf`（反向代理 + SSE 长连接）
- 新增 `.dockerignore`
- 更新 `docker-compose.yml`（添加灵枢配置）
- 新增 `DEPLOY.md` 部署指南

### 运营数据
- 新增 `backend/middleware/logging.py` — API 请求日志
- 新增 `backend/middleware/rate_limit.py` — 简易限流
- 新增 `backend/api/routes/admin.py` — 管理 API
  - `GET /api/admin/stats` — 运营数据统计
  - `GET /api/admin/stats/llm` — LLM 调用统计
  - `GET /api/admin/stats/logs` — API 日志查询
  - `GET /api/admin/health/detail` — 深度健康检查
  - `GET /api/admin/export` — CSV 数据导出
- LLM 调用自动记录到 `logs/llm_calls.jsonl`

### 开源质量
- 新增 `CHANGELOG.md`
- 新增 `CONTRIBUTING.md`
- 新增 `DEPLOY.md`
- 更新 README — 添加阶段三特性标记

### 前端完善
- 补全侧边栏导航（AIGC报告、智能体面板）
- 前端 API 路径修复 (`/agent/` → `/agents/`)

---

## v2.0.0（阶段二）— 2026-06

### AIGC 引擎升级
- 四个生成器接入 moark.com Lingshu-32B 真实 LLM
- LLM 优先 + 模板降级双轨策略
- 新增 `backend/aigc/llm_client.py` — LLM 调用客户端

### Agent 适配
- Lingshu-32B prompt-based ReAct 循环（平台不支持 function calling）
- platform_adapter 从 pydantic Settings 读取 `.env`

### 其他
- 前端 API 路径修复
- 多个 bug 修复

---

## v1.0.0（阶段一）— 2026-05

### 核心功能
- 5 智能体多 Agent 协作架构
- LangGraph 双环状态机
- VibraImage 前庭振动引擎
- AIGC 模板生成器
- Vue 3 前端仪表盘
- Docker 部署
- 56 项自动化测试
