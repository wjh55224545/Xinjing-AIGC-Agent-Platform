"""
简易请求限流中间件
=================

基于内存的 IP 级别滑动窗口限流。
保护后端和 moark.com API 不被滥用。
"""

from __future__ import annotations
import time
from collections import defaultdict
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# 配置
MAX_REQUESTS_PER_MINUTE = 60  # 每 IP 每分钟最多 60 次请求
LLM_MAX_REQUESTS_PER_MINUTE = 10  # LLM 端点每 IP 每分钟最多 10 次

# 滑动窗口记录: {ip: [timestamp1, timestamp2, ...]}
_request_windows: dict[str, list[float]] = defaultdict(list)
_llm_windows: dict[str, list[float]] = defaultdict(list)

LLM_ENDPOINTS = {"/api/aigc/report/daily", "/api/aigc/plan/intervention",
                 "/api/aigc/letter/parent", "/api/aigc/narrative/growth",
                 "/api/agents/trigger/inner", "/api/agents/trigger/outer"}


def _check_rate_limit(
    ip: str,
    windows: dict[str, list[float]],
    max_per_minute: int,
) -> bool:
    """检查是否超限。返回 True 表示允许，False 表示限流。"""
    now = time.time()
    window = windows[ip]

    # 清理超过 60 秒的记录
    while window and window[0] < now - 60:
        window.pop(0)

    if len(window) >= max_per_minute:
        return False

    window.append(now)
    return True


class RateLimitMiddleware(BaseHTTPMiddleware):
    """简易限流中间件。"""

    async def dispatch(self, request: Request, call_next):
        ip = request.client.host if request.client else "unknown"
        endpoint = request.url.path

        # LLM 端点更严格的限制
        if endpoint in LLM_ENDPOINTS:
            allowed = _check_rate_limit(ip, _llm_windows, LLM_MAX_REQUESTS_PER_MINUTE)
        else:
            allowed = _check_rate_limit(ip, _request_windows, MAX_REQUESTS_PER_MINUTE)

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "success": False,
                    "error": "请求过于频繁，请稍后再试",
                    "retry_after_seconds": 10,
                },
            )

        return await call_next(request)
