"""
DeepSeek LLM 接口 (保留作为备用)
================================

保留原有的DeepSeek接口，作为平台适配器的备用方案。
推荐使用 platform_adapter.py 中的 get_llm() 统一入口。
"""

from __future__ import annotations
from functools import lru_cache
from langchain_openai import ChatOpenAI
from backend.config import get_settings


@lru_cache
def get_llm(streaming: bool = False) -> ChatOpenAI:
    """获取 DeepSeek LLM 实例（备用）"""
    settings = get_settings()
    return ChatOpenAI(
        model=settings.deepseek_model,
        base_url=settings.deepseek_base_url,
        api_key=settings.deepseek_api_key,
        streaming=streaming,
        temperature=0.7,
        max_tokens=2048,
    )
