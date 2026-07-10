"""
心镜·AIGC智能体平台 启动脚本
==============================
第八届CCF开源创新大赛 · 国产开源GPU AI创新生态赛 任务三

使用方式:
    python run_backend.py

API文档: http://localhost:8000/docs
"""

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

# 🔑 在导入任何 backend 模块之前，先将 .env 加载到 os.environ
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("  心镜·AIGC智能体平台 v2.0.0")
    print("  第八届CCF开源创新大赛 · 任务三")
    print("  国产算力平台: 沐曦MetaX GPU / Gitee.AI")
    print("=" * 60)

    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
