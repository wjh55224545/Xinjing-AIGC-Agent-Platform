"""
心镜·AIGC智能体平台 启动脚本
==============================
面向心理健康的多模态情绪评估与智能分析平台

使用方式:
    开发模式: python run_backend.py --dev
    生产模式: python run_backend.py
    生产模式: PRODUCTION=1 python run_backend.py

API文档: http://localhost:8000/docs
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

# 🔑 在导入任何 backend 模块之前，先将 .env 加载到 os.environ
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
except ImportError:
    pass

import uvicorn

PRODUCTION = os.getenv("PRODUCTION", "0") == "1" or "--dev" not in sys.argv

if __name__ == "__main__":
    print("=" * 60)
    print("  心镜·AIGC智能体平台 v2.4.0")
    print("  面向心理健康的多模态情绪评估与智能分析平台")
    mode_str = "Production" if PRODUCTION else "Development"
    print(f"  模式: {mode_str}")
    print("  算力平台: moark.com Lingshu-32B (沐曦MetaX GPU)")
    print("=" * 60)

    kwargs = {
        "app": "backend.main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "log_level": "info",
    }
    if PRODUCTION:
        kwargs["reload"] = False
        kwargs["workers"] = 2  # 生产模式双 worker
    else:
        kwargs["reload"] = True

    uvicorn.run(**kwargs)

