# 心镜·AIGC智能体平台 - Dockerfile
# 阶段1: 构建前端
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci --registry=https://registry.npmmirror.com 2>/dev/null || npm install --registry=https://registry.npmmirror.com
COPY frontend/ .
RUN npm run build

# 阶段2: 后端 + 前端静态文件
FROM python:3.11-slim
WORKDIR /app

# 基础工具
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 后端代码
COPY backend/ ./backend/
COPY run_backend.py .

# 前端构建产物
COPY --from=frontend-builder /app/frontend/dist ./static

# 数据目录
RUN mkdir -p /app/data/uploads /app/data/camera /app/data/obs /app/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
