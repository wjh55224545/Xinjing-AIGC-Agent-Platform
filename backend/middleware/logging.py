"""
API 调用日志中间件
=================

记录每个 HTTP 请求的端点、方法、状态码、耗时、客户端 IP。
输出到 logs/api.log，同时提供内存统计供管理 API 查询。
"""

from __future__ import annotations
import os
import time
import json
import logging
from datetime import datetime, date
from collections import defaultdict
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)
API_LOG_PATH = os.path.join(LOG_DIR, "api.log")

# 内存统计（重启后清空）
_stats = {
    "total_requests": 0,
    "total_errors": 0,
    "endpoints": defaultdict(int),       # endpoint → 请求数
    "daily_counts": defaultdict(int),    # YYYY-MM-DD → 请求数
    "status_counts": defaultdict(int),   # status_code → 计数
    "recent_latency": [],                # 最近 100 条耗时(ms)
    "recent_errors": [],                 # 最近 20 条错误
}


def get_stats() -> dict:
    """获取请求统计摘要。"""
    return {
        "total_requests": _stats["total_requests"],
        "total_errors": _stats["total_errors"],
        "error_rate": round(
            _stats["total_errors"] / max(_stats["total_requests"], 1), 3
        ),
        "top_endpoints": sorted(
            [{"endpoint": k, "count": v} for k, v in _stats["endpoints"].items()],
            key=lambda x: x["count"], reverse=True
        )[:10],
        "daily_counts": dict(
            sorted(_stats["daily_counts"].items(), reverse=True)[:30]
        ),
        "avg_latency_ms": (
            round(sum(_stats["recent_latency"]) / len(_stats["recent_latency"]), 1)
            if _stats["recent_latency"] else 0
        ),
        "status_distribution": dict(_stats["status_counts"]),
        "recent_errors": _stats["recent_errors"][-10:],
    }


class APILoggingMiddleware(BaseHTTPMiddleware):
    """记录每个 API 请求的中间件。"""

    async def dispatch(self, request: Request, call_next):
        start = time.time()
        status_code = 500
        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            return response
        except Exception as e:
            status_code = 500
            _stats["recent_errors"].append({
                "endpoint": request.url.path,
                "method": request.method,
                "error": str(e)[:200],
                "time": datetime.now().isoformat(),
            })
            if len(_stats["recent_errors"]) > 20:
                _stats["recent_errors"].pop(0)
            raise
        finally:
            duration_ms = round((time.time() - start) * 1000, 1)
            endpoint = request.url.path
            method = request.method
            client_ip = request.client.host if request.client else "unknown"
            today = str(date.today())

            # 更新内存统计
            _stats["total_requests"] += 1
            _stats["endpoints"][endpoint] += 1
            _stats["daily_counts"][today] += 1
            _stats["status_counts"][str(status_code)] += 1
            if status_code >= 400:
                _stats["total_errors"] += 1
            _stats["recent_latency"].append(duration_ms)
            if len(_stats["recent_latency"]) > 100:
                _stats["recent_latency"].pop(0)

            # 写日志文件
            try:
                log_entry = {
                    "timestamp": datetime.now().isoformat(),
                    "method": method,
                    "endpoint": endpoint,
                    "status": status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                }
                with open(API_LOG_PATH, "a", encoding="utf-8") as f:
                    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
            except Exception:
                pass
