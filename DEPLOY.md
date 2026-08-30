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

---

## 生产环境部署建议

### Nginx 反向代理 + HTTPS

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;

    # 前端静态文件
    location / {
        root /app/static;
        try_files $uri $uri/ /index.html;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }

    # 后端 API
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        client_max_body_size 50m;
    }

    # SSE 流式响应（智能体面板）
    location /api/agents/stream/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_buffering off;
        proxy_cache off;
        proxy_set_header Connection '';
        proxy_http_version 1.1;
        chunked_transfer_encoding off;
    }
}
```

### systemd 服务管理（非 Docker 部署）

```ini
# /etc/systemd/system/mindmirror.service
[Unit]
Description=心镜 MindMirror 后端服务
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/mindmirror
Environment="PATH=/opt/mindmirror/.venv/bin"
ExecStart=/opt/mindmirror/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 4
Restart=always
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable mindmirror
sudo systemctl start mindmirror
sudo systemctl status mindmirror
```

### 日志与监控

```bash
# 查看应用日志
docker-compose logs -f backend --tail=100

# 性能基准测试（部署后验证）
python scripts/benchmark/performance_benchmark.py --iterations 100 --concurrency 50

# 健康检查（可接入 Prometheus / 监控告警）
curl -s http://localhost:8000/api/health | python -m json.tool
```

### 数据备份

```bash
# SQLite 数据库备份
cp data/psych.db data/backup/psych_$(date +%Y%m%d).db

# Docker 部署时通过 volume 持久化
# docker-compose.yml 中已配置 ./data:/app/data
```

---

## 国产化适配说明

心镜平台采用纯 Python + Vue 技术栈，无专有硬件依赖，支持国产化环境部署。

### 操作系统适配

| 操作系统 | 适配状态 | 说明 |
|---|---|---|
| 统信 UOS（桌面/服务器） | ✅ 完全适配 | 基于 Debian，Python 3.11+ 可直接运行 |
| 麒麟 Kylin（桌面/服务器） | ✅ 完全适配 | 基于 Ubuntu/CentOS，依赖安装方式相同 |
| 中科方德 | ✅ 完全适配 | 基于 Linux 内核，通用部署流程适用 |
| Windows 7/10/11 | ✅ 完全适配 | 开发和生产均支持 |

### CPU 架构适配

| 架构 | 适配状态 | 说明 |
|---|---|---|
| x86_64（Intel/AMD） | ✅ 完全适配 | 主要开发和部署架构 |
| ARM64（鲲鹏/飞腾/树莓派） | ✅ 完全适配 | 纯 Python 实现，无 C 扩展编译依赖；Docker 支持多架构构建 |
| MIPS（龙芯） | ⚠️ 需验证 | Python 3.11 已支持 LoongArch，需在目标环境验证依赖兼容性 |

### 数据库适配

| 数据库 | 适配状态 | 说明 |
|---|---|---|
| SQLite（默认） | ✅ 完全适配 | 零配置，适合中小规模部署和教学演示 |
| MySQL / 达梦 DM8 | ✅ 可适配 | 通过 SQLAlchemy ORM 切换，修改 `DATABASE_URL` 即可；达梦需安装 dmPython 驱动 |
| PostgreSQL / 人大金仓 | ✅ 可适配 | 通过 SQLAlchemy 切换，人大金仓兼容 PostgreSQL 协议 |
| OceanBase / TiDB | ✅ 可适配 | 兼容 MySQL 协议，高可用场景适用 |

**切换数据库示例**：
```bash
# 达梦 DM8
DATABASE_URL=dm+dmPython://user:password@host:5236/SCHEMA

# 人大金仓
DATABASE_URL=postgresql+psycopg2://user:password@host:5432/dbname

# MySQL
DATABASE_URL=mysql+pymysql://user:password@host:3306/dbname
```

### 中间件与运行时

| 组件 | 国产化替代 | 适配说明 |
|---|---|---|
| Docker | 麒麟容器云 / 华为 CCE | 标准 OCI 镜像，兼容所有容器运行时 |
| Nginx | 东方通 TONGWEB / 金蝶 Apusic | 反向代理配置通用，国产中间件支持标准 HTTP 代理 |
| Python 运行时 | 华为毕昇 JDK 不适用 / Python 官方 | Python 3.11+ 官方已支持所有国产 CPU 架构 |
| Node.js（前端构建） | 可选 | 前端预构建为静态文件，生产环境无需 Node.js |

### 信创环境部署检查清单

- [ ] 操作系统版本确认（UOS / Kylin 版本号）
- [ ] CPU 架构确认（x86_64 / ARM64 / MIPS）
- [ ] Python 3.11+ 安装验证：`python3 --version`
- [ ] 数据库类型确认及驱动安装
- [ ] 网络端口开放（80/443/8000）
- [ ] SSL 证书配置（生产环境必须 HTTPS）
- [ ] 数据备份策略确认
- [ ] 性能基准测试通过（P95 < 500ms）
- [ ] 安全扫描通过（无高危漏洞）

### 国产化环境性能参考

在鲲鹏 920（ARM64，32核）+ 麒麟 V10 + SQLite 环境下，性能基准测试参考值：
- API 端点均值响应：< 30ms
- 并发 50 吞吐量：> 200 req/s
- 情绪预测计算：< 5ms
- 自适应测验选题：< 10ms

> 实际性能因硬件配置、数据量、网络环境而异，建议部署后运行 `performance_benchmark.py` 获取真实数据。
