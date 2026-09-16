# 更新日志

## v2.8.0（评估闭环 / 群体对照 / 报告追问 / PDF 导出）— 2026-09-16

补齐诊断链路两端，让系统从"出报告"升级为可验证的筛查-干预-评估闭环：

### 预警-干预闭环统计（方案二）
- 新增 `InterventionCycle` 模型与服务：预警 → 干预建议 → 定时复测（默认 14 天）→ 结局判定（improved/stable/worsened）
- 统计含闭环总数/完成/逾期、好转率、干预前后均值、风险迁移矩阵
- 前端：预警面板新增「干预闭环统计」卡片与「创建闭环」「检查逾期」
- 文献：JITAI 即时自适应干预（Nahumshani et al., 2018）；闭环有效性（Bidargaddi et al., 2020）

### 经典实验群体对照（方案三）
- 新增 `ExperimentRecord` 模型：四范式统一存储，`student_id` 可空支持仅按班级聚合
- `compare_group`：班级均值 vs 全校基准、差值、画像解释、样本量提示
- 新增 `GET /api/experiments/group-comparison`；四个 analyze 端点可选 student_id/class_name 即入库
- 前端：实验完成页「保存到群体对照」+「班级 vs 全校对照」面板
- 文献：Ebert et al. (2019, Depression and Anxiety) 入学筛查分层；Han et al. (2022, Front Genet) 预警画像

### AIGC 报告多轮追问（方案四）
- 新增 `report_followup` 服务：10 类指标证据链提取；LLM 优先，降级关键词模板（风险/占比/稳定/恢复压力/兜底）
- 新增 `POST /api/aigc/report/followup`；前端日报区「对报告追问」多轮对话
- 文献：治疗性评估（Finn & Tonsager, 1997）；反馈干预理论（Kluger & DeNisi, 1996）

### 诊断报告 PDF 导出（方案五）
- 新增 `report_pdf` 服务（reportlab A4）：中文字体自动注册，风险结论色块置顶，8 行指标表，技术附注
- 新增 `GET /api/aigc/report/{student_id}/{date}/pdf`；前端「导出 PDF 诊断报告」按钮
- 文献：报告格式化四原则（Valenstein, 2008）；表格化呈现（Brick et al., 2022）

### 验证
- 新增 4 个测试文件 20 项，全量测试 **171 → 191 passed**，前端构建通过
- 修复：`models/__init__.py` 补注册 `ScaleResult`（SQLAlchemy 映射解析）；PDF 中文字体断言修正
- 版本号统一为 v2.8.0

---

## v2.7.0（AIGC 报告质量修复）— 2026-09-16

依据湖北大学心理学系熊猛教授团队盲评结果（总体 8.00/10），修复报告模块 5 类硬伤：

### 数据-结论一致性（最大失分点：信任度 7.58）
- 新增 `_check_consistency` 一致性校验（7 类矛盾检测），概览措辞随矛盾清单自动降档
- 风险等级综合判定：评分低但负面占比也低时不再误判红色（修复"积极占比 52.3% 却判高风险"）

### 指标表补全（专家 6 次提及缺项）
- 日报指标表 5 行 → 8 行：新增风险等级、情绪恢复速度、压力累积指数（数据层本就已算好）

### 共情措辞与矛盾消除（共情性 7.77）
- 风险分析改为温暖建设性措辞；关键发现消除"稳定"与"波动大"并存矛盾；明日预测全中文

### 个性化建议（专家 3 次提及普适）
- 按主导情绪（8 类）生成定制建议库 + 恢复/压力指标联动；优先级标签中文化

### LLM 生成约束强化
- prompt 增加数据一致性铁律、全中文要求、共情要求、指标表 8 行结构

### 验证
- 新增 `tests/test_report_consistency.py` 11 项，全量测试 **160 → 171 passed**
- 版本号统一为 v2.7.0

---

## v2.6.0（前端系统信息清理 / 诊断算法校准）— 2026-09-14

### 前端系统信息清理（升级25a）
- `App.vue`：移除侧边栏「系统运行中」状态块与顶栏「在线」状态点（保留版本号与时间）
- `AgentPanelView.vue`：移除「国产算力 / 当前平台」徽标及其请求逻辑、相关样式
- 界面只呈现业务内容，符合「前端不展示系统信息」约定

### 诊断算法校准（升级25b）
- 新增 `backend/services/diagnostic_calibration.py`：18 种虚拟被试 × 每剖面 N 样本批量自动诊断
- 指标：量表等级一致率 / 情绪判定一致率 / 灵敏度（阳性检出）/ 特异度（阴性正确）/ 边界案例（≥2 级差）
- 新增 API `GET /api/virtual-subjects/calibration`，前端虚拟被试页新增「诊断算法校准」卡片
- 冒烟结果（seed=42, 144 样本）：量表一致率 100%、情绪一致率 89.6%、灵敏度 100%、特异度 100%
- 新增测试 5 项，全量测试 155 → **160 passed**

---

## v2.5.0（融合策略完整对比 / 经典实验工具箱 / CI / 边界测试 / 场景映射）— 2026-09-07

### 融合策略完整消融（升级20）
- 新增 `scripts/ablation/fusion_ablation_v2.py`：9 种方法完整对比（单模态 D-S ×3 / 双模态 D-S ×3 / 实时双模态置信度加权 / 三模态 D-S / 旧固定权重）
- 合成被试 N=500：单模态最佳 79.0% → 实时双模态 81.0%（+3.4%）→ 三模态 D-S 81.4%；相对旧固定权重 +1.8%
- README 消融数字与实际可复现值对齐（原不可复现的 +12.3%/+8.7% 已修正）

### 经典实验工具箱（升级21）
- `backend/services/classic_experiments.py` 新增 Flanker（Eriksen & Eriksen, 1974）/ Go-NoGo（Donders, 1868; Newman & Kosson, 1986）/ IAT（Greenwald et al., 1998/2003）
- 新增 8 个 API 端点（生成试次 + 分析）
- 新增前端页面 `ClassicExperimentsView.vue`：四实验页签 + 逐题作答 + 自动分析 + 结果导出

### CI 自动化（升级22）
- 新增 `.github/workflows/ci.yml`：push/PR 自动跑后端全量测试（Python 3.11 + requirements-ci.txt）+ 前端构建（Node 20 + npm ci）

### 边界测试补齐（升级23）
- 新增 `tests/test_upgrades20_24.py` 28 项（多模态融合置信度/权重/复核、实验空数据/极端输入、风险分级边界、18 剖面自动诊断）
- 全量测试 **155 passed**（127 → 155）

### 场景-功能-证据映射（升级24）
- 新增 `docs/application_mapping.md`：4 个应用场景 × 功能模块 × 量化证据对照表，含数据与伦理边界说明

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

### 工程化部署补强（升级12）
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
