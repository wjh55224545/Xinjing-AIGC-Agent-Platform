"""
配置中心
========

集中管理所有配置，支持从环境变量和.env文件读取。

国产算力平台配置:
- AI_PLATFORM: 主推理平台 (gitee_ai / deepseek / local / custom)
- GITEE_AI_API_KEY: Gitee.AI (沐曦GPU) API密钥
- GITEE_AI_MODEL: Gitee.AI 模型名称
- DEEPSEEK_API_KEY: DeepSeek API密钥（备用）
"""

from __future__ import annotations
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # ========== 数据库 ==========
    database_url: str = "sqlite:///./data/psych.db"

    # ========== AI算力平台配置 ==========
    # 主平台选择: lingshu / gitee_ai / deepseek / local / custom
    ai_platform: str = "gitee_ai"

    # Lingshu / Qwen3-8B — moark.com 平台（OpenAI 兼容）
    lingshu_api_key: str = ""
    lingshu_base_url: str = "https://api.moark.com/v1"
    lingshu_model: str = "Lingshu-32B"
    lingshu_top_k: int = -1

    # Gitee.AI (沐曦 MetaX GPU) - 国产开源GPU算力
    gitee_ai_api_key: str = ""
    gitee_ai_base_url: str = "https://api.gitee.ai/v1"
    gitee_ai_model: str = "qwen2.5-7b-instruct"

    # DeepSeek - 国产大模型（备用）
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"

    # 本地模型
    local_base_url: str = "http://localhost:11434/v1"
    local_model: str = "qwen2.5:7b"

    # 通用API Key（当各平台独立Key未设置时使用）
    ai_api_key: str = ""

    # 备用平台列表
    ai_fallback_platforms: str = "deepseek"

    # ========== 华为云OBS ==========
    obs_endpoint: str = "https://obs.cn-north-4.myhuaweicloud.com"
    obs_bucket: str = "psych-monitor"
    obs_ak: str = ""
    obs_sk: str = ""

    # ========== 文件路径 ==========
    upload_dir: str = "./data/uploads"
    camera_dir: str = "./data/camera"

    # ========== VibraImage前庭振动引擎 ==========
    vibraimage_model_path: str = "./data/yolov8n.pt"
    vibraimage_window_frames: int = 100
    vibraimage_window_stride: int = 50
    vibraimage_freq_method: str = "zerocross"

    # ========== CORS ==========
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ========== 调度器 ==========
    inner_loop_interval_minutes: int = 15
    outer_loop_cron_hour: int = 22
    outer_loop_cron_minute: int = 0

    # ========== 服务 ==========
    service_name: str = "心镜·AIGC智能体平台"
    service_version: str = "2.0.0"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
