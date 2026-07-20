# 🚀 部署指南

心镜·AIGC智能体平台 支持三种部署方式：本地开发、Docker 容器、云平台。

---

## 前置条件

- Python 3.11+
- Node.js 18+（仅本地前端开发）
- Docker & Docker Compose（容器部署）
- moark.com API Key（LLM 推理，可选，无 Key 时降级模板模式）

---

## 方式一：本地开发部署

### 1. 后端

```bash
# 克隆仓库
git clone https://github.com/wjh55224545/Xinjing-AIGC-Agent-Platform.git
cd Xinjing-AIGC-Agent-Platform

# 虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境
cp .env.template .env
# 编辑 .env 填入 API Key（可选，不填则降级模板模式）

# 启动后端
python run_backend.py
# 访问 http://localhost:8000/docs
```

### 2. 前端（可选，后端自带 Swagger UI）

```bash
cd frontend
npm install --registry=https://registry.npmmirror.com
npm run dev
# 访问 http://localhost:5173
```

---

## 方式二：Docker 部署

```bash
# 配置环境变量
cp .env.template .env
# 编辑 .env

# 构建并启动
docker-compose up -d

# 查看状态
docker-compose ps

# 查看日志
docker-compose logs -f backend

# 停止
docker-compose down
```

服务端口：
- 前端：`http://localhost:80`
- 后端 API：`http://localhost:8000`
- API 文档：`http://localhost:8000/docs`

---

## 方式三：云平台部署

### Railway

[![Deploy on Railway](https://railway.app/button.svg)](https://railway.app/)

1. Fork 本仓库到你的 GitHub
2. 在 [Railway](https://railway.app/) 创建新项目 → "Deploy from GitHub repo"
3. 添加环境变量：`LINGSHU_API_KEY`、`LINGSHU_BASE_URL`、`LINGSHU_MODEL`
4. Railway 自动识别 `Dockerfile` 并部署

### Render

1. 在 [Render](https://render.com/) 创建 "Web Service"
2. 连接 GitHub 仓库
3. 构建命令：留空（使用 Dockerfile）
4. 环境变量同上

### 自建服务器

```bash
# 安装 Docker
curl -fsSL https://get.docker.com | sh

# 克隆并部署
git clone https://github.com/wjh55224545/Xinjing-AIGC-Agent-Platform.git
cd Xinjing-AIGC-Agent-Platform
cp .env.template .env
# 编辑 .env

# 使用 docker-compose
docker-compose up -d

# 或仅后端（通过 systemd 管理）
docker build -t mindmirror .
docker run -d --name mindmirror -p 8000:8000 \
  -e LINGSHU_API_KEY=your_key \
  -v $(pwd)/data:/app/data \
  mindmirror
```

---

## 环境变量说明

| 变量 | 必填 | 默认值 | 说明 |
|------|:--:|--------|------|
| `AI_PLATFORM` | 否 | `lingshu` | 主平台：lingshu/gitee_ai/deepseek |
| `LINGSHU_API_KEY` | 否 | — | moark.com API Key（不填则 AIGC 降级模板） |
| `LINGSHU_BASE_URL` | 否 | `https://api.moark.com/v1` | moark.com API 地址 |
| `LINGSHU_MODEL` | 否 | `Lingshu-32B` | 模型名称 |
| `DEEPSEEK_API_KEY` | 否 | — | DeepSeek API Key（备用） |
| `AI_FALLBACK_PLATFORMS` | 否 | `deepseek` | 主平台不可用时的备用平台 |
| `DATABASE_URL` | 否 | `sqlite:///./data/psych.db` | 数据库路径 |
| `CORS_ORIGINS` | 否 | `["http://localhost:5173","http://localhost:3000"]` | CORS 允许源 |

---

## 验证部署

```bash
# 健康检查
curl http://localhost:8000/api/health

# 详细健康检查（含 LLM 连通性）
curl http://localhost:8000/api/admin/health/detail

# 运营数据
curl http://localhost:8000/api/admin/stats
```

---

## 常见问题

### Q: Docker 容器内无法调用 LLM
A: 确保 `.env` 中 `LINGSHU_API_KEY` 正确，并在 `docker-compose.yml` 的环境变量中引用

### Q: 前端页面空白
A: 检查后端 CORS 配置，确保 `CORS_ORIGINS` 包含前端地址

### Q: 数据库在哪里
A: `data/psych.db`（SQLite），Docker 部署时通过 volume 挂载
