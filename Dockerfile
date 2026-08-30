# 心镜·AIGC智能体平台 - Dockerfile（本地预编译版）
# 前端需在本地提前编译（npm run build），产物在 static/ 目录
FROM python:3.11-slim

WORKDIR /app

# 基础工具
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 后端代码
COPY backend/ ./backend/
COPY run_backend.py .

# 前端构建产物（本地已编译完成）
COPY static/ ./static/

# 数据目录（含量表JSON、种子数据）
COPY data/ ./data/

# 运行时目录
RUN mkdir -p /app/data/uploads /app/data/camera /app/data/obs /app/logs

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

CMD ["python", "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
