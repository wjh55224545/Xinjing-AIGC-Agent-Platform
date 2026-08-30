# 贡献指南

感谢你对心镜·AIGC智能体平台的关注！

## 环境搭建

```bash
git clone https://github.com/wjh55224545/Xinjing-AIGC-Agent-Platform.git
cd Xinjing-AIGC-Agent-Platform
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.template .env
```

## 开发流程

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feat/your-feature`
3. 编写代码 + 测试
4. 运行测试：`python -m pytest tests/ -v`
5. 提交 PR

## 项目结构

```
backend/
├── agents/          # 5 智能体（基类、感知、分析、报告、预警、协调）
├── aigc/            # AIGC 引擎（LLM 客户端 + 4 生成器 + 模板）
├── api/routes/      # REST API（仪表盘/学生/预警/AIGC/Agent/VibraImage/管理）
├── graph/           # LangGraph 状态机（内环/外环/7节点）
├── llm/             # 平台适配层（Lingshu/DeepSeek/本地）
├── middleware/       # 中间件（日志/限流）
├── models/          # ORM 模型
├── scheduler/       # 定时任务
├── services/        # 业务逻辑
├── tools/           # 工具层（情绪识别/心理分析/反馈/OBS/VibraImage）
└── vibraimage/      # VibraImage 引擎
```

## 添加新的 AI 平台

1. 在 `backend/llm/platform_adapter.py` → `PLATFORM_CONFIGS` 添加配置
2. 在 `Platform` 枚举添加选项
3. 在 `backend/config.py` → `Settings` 添加对应字段
4. 在 `.env.template` 添加模板配置

## 添加新的 AIGC 生成器

1. 在 `backend/aigc/` 创建生成器类
2. 实现 `_try_llm_generate()` 方法（LLM 优先）
3. 保留模板降级逻辑
4. 在 `backend/agents/report_agent.py` 注册为工具

## 代码风格

- Python：遵循 PEP 8
- 前端：Vue 3 Composition API + `<script setup>`
- 文档注释用中文
- 代码标识符用英文
