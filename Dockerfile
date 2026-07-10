# 心镜·AIGC智能体平台 - 后端 Dockerfile
# 基于国产算力平台（沐曦MetaX GPU / Gitee.AI）

FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY backend/ ./backend/
COPY prompts/ ./prompts/
COPY parsers/ ./parsers/
COPY config/ ./config/
COPY run_backend.py .

# 创建数据目录
RUN mkdir -p /app/data/uploads /app/data/camera /app/data/obs

# 暴露端口
EXPOSE 8000

# 启动
CMD ["python", "run_backend.py"]
