"""
AIGC LLM 客户端
===============

为 AIGC 生成器提供统一的 LLM 调用接口。
使用 OpenAI 兼容协议直接调用 moark.com 平台模型。
如果 LLM 不可用则返回 None，生成器自动降级到模板模式。
"""

from __future__ import annotations
import os
import time
import json
import logging
import threading
from functools import lru_cache
from openai import OpenAI

from backend.config import get_settings

logger = logging.getLogger(__name__)

# LLM 并发控制（最多 3 个并发请求，保护 moark.com 不被限流）
_llm_lock = threading.Semaphore(3)

# 缓存 moark.com 返回头中的 GPU 厂商信息（首次调用后填充）
GPU_VENDOR_CACHED: str = ""

LLM_LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(LLM_LOG_DIR, exist_ok=True)
LLM_LOG_PATH = os.path.join(LLM_LOG_DIR, "llm_calls.jsonl")


def _log_llm_call(
    success: bool, model: str, duration_ms: float,
    prompt_tokens: int = 0, completion_tokens: int = 0,
    error: str = "", gpu: str = "",
) -> None:
    """记录 LLM 调用到 JSONL 日志文件。"""
    global GPU_VENDOR_CACHED
    if gpu and not GPU_VENDOR_CACHED:
        GPU_VENDOR_CACHED = gpu
    try:
        entry = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "model": model,
            "gpu": gpu or GPU_VENDOR_CACHED or None,
            "success": success,
            "duration_ms": round(duration_ms, 1),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "error": error[:200] if error else "",
        }
        with open(LLM_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def get_gpu_vendor() -> str:
    """返回缓存的 GPU 厂商信息（首次 LLM 调用后可用）。"""
    return GPU_VENDOR_CACHED


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
    t_start = time.time()

    # 并发控制：最多 3 个并发 LLM 请求
    acquired = _llm_lock.acquire(timeout=30)
    if not acquired:
        logger.warning("LLM 并发已满，请求被跳过")
        return None
    try:
        # 使用 with_raw_response 捕获 HTTP 响应头（含 GPU 厂商信息）
        raw_resp = client.chat.completions.with_raw_response.create(
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
        duration_ms = (time.time() - t_start) * 1000

        # 提取 GPU 厂商信息（moark.com 返回 x-vendor: metax）
        gpu_vendor = raw_resp.headers.get("x-vendor", "")
        compute_time = raw_resp.headers.get("x-compute-time", "")
        response = raw_resp.parse()

        content = response.choices[0].message.content
        usage = response.usage
        pt = usage.prompt_tokens if usage else 0
        ct = usage.completion_tokens if usage else 0

        if content:
            import re
            content = re.sub(r'<\s*think\s*>.*?<\s*/\s*think\s*>', '', content, flags=re.DOTALL)
            content = content.strip()
            meta = f"GPU={gpu_vendor}" if gpu_vendor else ""
            if compute_time:
                meta += f" compute={compute_time}s"
            _log_llm_call(True, settings.lingshu_model, duration_ms, pt, ct, gpu=gpu_vendor)
            logger.info(
                f"LLM 生成成功，模型={response.model}，"
                f"长度={len(content)} 字符，耗时={duration_ms:.0f}ms"
                + (f"，{meta}" if meta else "")
            )
            return content
        else:
            _log_llm_call(False, settings.lingshu_model, duration_ms, pt, ct, "空内容", gpu=gpu_vendor)
            logger.warning("LLM 返回空内容")
            return None
    except Exception as e:
        duration_ms = (time.time() - t_start) * 1000
        _log_llm_call(False, settings.lingshu_model, duration_ms, 0, 0, str(e))
        logger.warning(f"LLM 调用失败，降级到模板模式: {e}")
        return None
    finally:
        _llm_lock.release()
