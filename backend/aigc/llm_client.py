"""
AIGC LLM 客户端
===============

为 AIGC 生成器提供统一的 LLM 调用接口。
使用 OpenAI 兼容协议直接调用 moark.com 平台模型。
如果 LLM 不可用则返回 None，生成器自动降级到模板模式。
"""

from __future__ import annotations
import logging
from functools import lru_cache
from openai import OpenAI

from backend.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_openai_client() -> OpenAI | None:
    """获取 OpenAI 兼容客户端（缓存），配置失败返回 None。"""
    settings = get_settings()
    api_key = settings.lingshu_api_key
    if not api_key:
        logger.warning("灵枢 API Key 未配置，AIGC 将使用模板模式")
        return None
    try:
        return OpenAI(
            base_url=settings.lingshu_base_url,
            api_key=api_key,
        )
    except Exception as e:
        logger.warning(f"创建 OpenAI 客户端失败，降级到模板模式: {e}")
        return None


def llm_generate(
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2048,
) -> str | None:
    """
    调用 LLM 生成内容。

    Args:
        system_prompt: 系统提示词
        user_prompt: 用户提示词
        temperature: 采样温度
        max_tokens: 最大输出 token 数

    Returns:
        LLM 生成的文本，如果调用失败则返回 None（上层应降级到模板）
    """
    client = _get_openai_client()
    if client is None:
        return None

    settings = get_settings()
    try:
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=settings.lingshu_model,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=1.0,
            extra_body={"top_k": -1},
            frequency_penalty=0.0,
        )
        content = response.choices[0].message.content
        if content:
            # 移除 moark.com 模型返回的 <think>...</think> 推理标记
            # （降级处理：部分模型可能将 reasoning_content 放入 content）
            import re
            content = re.sub(r'<\s*think\s*>.*?<\s*/\s*think\s*>', '', content, flags=re.DOTALL)
            content = content.strip()
            logger.info(
                f"LLM 生成成功，模型={response.model}，"
                f"长度={len(content)} 字符"
            )
            return content
        else:
            logger.warning("LLM 返回空内容")
            return None
    except Exception as e:
        logger.warning(f"LLM 调用失败，降级到模板模式: {e}")
        return None
