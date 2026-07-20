# 更新日志

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
