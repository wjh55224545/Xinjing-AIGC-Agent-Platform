"""
管理 API 路由
============

提供系统状态、运营数据、日志查询、用户反馈等管理功能。
"""

from __future__ import annotations
import os
import json
from datetime import date, datetime
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

router = APIRouter(prefix="/admin", tags=["系统管理"])

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)


# ---- 用户反馈 ----

@router.post("/feedback", summary="提交用户反馈")
async def submit_feedback(
    rating: int = Query(..., ge=1, le=5, description="评分 1-5"),
    content: str = Query("", description="反馈内容"),
):
    """接收用户反馈并记录到日志文件。"""
    feedback_path = os.path.join(LOG_DIR, "feedback.jsonl")
    entry = {
        "timestamp": datetime.now().isoformat(),
        "rating": rating,
        "content": content[:500],
    }
    try:
        with open(feedback_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存反馈失败: {e}")

    return {"success": True, "message": "感谢您的反馈！"}


# ---- 运营统计 ----

@router.get("/stats", summary="获取运营数据统计")
async def get_stats():
    """返回 API 请求统计、LLM 调用统计、用户反馈、系统运行状态。"""
    stats = {
        "service": "心镜·AIGC智能体平台",
        "version": "2.1.0",
        "collected_at": datetime.now().isoformat(),
    }

    # API 请求
    try:
        from backend.middleware.logging import get_stats as get_api_stats
        stats["api"] = get_api_stats()
    except Exception:
        stats["api"] = {"error": "暂不可用"}

    # LLM 调用
    try:
        stats["llm"] = _get_llm_stats()
    except Exception:
        stats["llm"] = {"error": "暂不可用"}

    # 用户反馈
    try:
        stats["feedback"] = _get_feedback_stats()
    except Exception:
        stats["feedback"] = {"error": "暂不可用"}

    # 平台信息
    try:
        from backend.llm.platform_adapter import get_platform_info
        stats["platform"] = get_platform_info()
    except Exception:
        stats["platform"] = {"error": "暂不可用"}

    return {"success": True, "data": stats}


@router.get("/stats/llm", summary="获取 LLM 调用统计")
async def get_llm_stats():
    return {"success": True, "data": _get_llm_stats()}


@router.get("/stats/feedback", summary="获取用户反馈统计")
async def get_feedback_stats():
    return {"success": True, "data": _get_feedback_stats()}


@router.get("/stats/logs", summary="查询 API 调用日志")
async def get_logs(
    limit: int = Query(50, ge=1, le=500, description="返回条数"),
):
    log_path = os.path.join(LOG_DIR, "api.log")
    if not os.path.exists(log_path):
        return {"success": True, "data": [], "count": 0}

    lines = []
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass

    return {"success": True, "data": lines[-limit:], "count": len(lines[-limit:])}


# ---- 健康检查 ----

@router.get("/health/detail", summary="详细健康检查（含 LLM 连通性）")
async def health_detail():
    """深度健康检查：数据库、LLM 连通性、VibraImage 引擎。"""
    checks = {}

    try:
        from backend.database import SessionLocal
        from backend.models.student import Student
        db = SessionLocal()
        student_count = db.query(Student).count()
        db.close()
        checks["database"] = {"status": "ok", "student_count": student_count}
    except Exception as e:
        checks["database"] = {"status": "error", "message": str(e)[:100]}

    try:
        from backend.aigc.llm_client import llm_generate
        result = llm_generate("你是测试助手。", "请回答: ping", max_tokens=16)
        checks["llm"] = {"status": "ok" if result else "degraded", "model": "Lingshu-32B"}
    except Exception as e:
        checks["llm"] = {"status": "error", "message": str(e)[:100]}

    try:
        from backend.config import get_settings
        settings = get_settings()
        model_path = settings.vibraimage_model_path
        model_exists = os.path.exists(os.path.abspath(model_path)) if model_path else False
        checks["vibraimage"] = {"status": "ok" if model_exists else "degraded", "model_exists": model_exists}
    except Exception as e:
        checks["vibraimage"] = {"status": "error", "message": str(e)[:100]}

    return {
        "success": True,
        "service": "心镜·AIGC智能体平台",
        "version": "2.1.0",
        "checks": checks,
        "overall": "ok" if all(c.get("status") != "error" for c in checks.values()) else "degraded",
    }


# ---- 数据导出 ----

@router.get("/export", summary="导出运营数据 CSV")
async def export_data(
    days: int = Query(7, ge=1, le=90, description="导出天数"),
):
    log_path = os.path.join(LOG_DIR, "api.log")
    if not os.path.exists(log_path):
        return PlainTextResponse("timestamp,method,endpoint,status,duration_ms\n", media_type="text/csv")

    cutoff = str(date.today())
    rows = ["timestamp,method,endpoint,status,duration_ms,client_ip"]
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("timestamp", "")[:10] >= cutoff:
                        continue
                    rows.append(
                        f"{entry.get('timestamp', '')},"
                        f"{entry.get('method', '')},"
                        f"{entry.get('endpoint', '')},"
                        f"{entry.get('status', '')},"
                        f"{entry.get('duration_ms', '')},"
                        f"{entry.get('client_ip', '')}"
                    )
                except (json.JSONDecodeError, KeyError):
                    continue
    except Exception:
        pass

    return PlainTextResponse("\n".join(rows), media_type="text/csv")


# ---- 辅助函数 ----

def _get_llm_stats() -> dict:
    llm_log_path = os.path.join(LOG_DIR, "llm_calls.jsonl")
    if not os.path.exists(llm_log_path):
        return {"total_calls": 0, "total_tokens": 0, "calls": []}

    calls = []
    total_tokens = 0
    success_count = 0
    fail_count = 0
    total_duration = 0.0

    try:
        with open(llm_log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        c = json.loads(line)
                        calls.append(c)
                        total_tokens += c.get("total_tokens", 0)
                        total_duration += c.get("duration_ms", 0)
                        if c.get("success"):
                            success_count += 1
                        else:
                            fail_count += 1
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass

    return {
        "total_calls": len(calls),
        "success_count": success_count,
        "fail_count": fail_count,
        "success_rate": round(success_count / max(len(calls), 1), 3),
        "total_tokens": total_tokens,
        "total_duration_ms": round(total_duration, 1),
        "avg_duration_ms": round(total_duration / max(len(calls), 1), 1),
        "recent_calls": calls[-20:],
    }


def _get_feedback_stats() -> dict:
    feedback_path = os.path.join(LOG_DIR, "feedback.jsonl")
    if not os.path.exists(feedback_path):
        return {"total": 0, "avg_rating": 0, "items": []}

    items = []
    ratings = []
    try:
        with open(feedback_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        item = json.loads(line)
                        items.append(item)
                        ratings.append(item.get("rating", 0))
                    except json.JSONDecodeError:
                        continue
    except Exception:
        pass

    return {
        "total": len(items),
        "avg_rating": round(sum(ratings) / max(len(ratings), 1), 1),
        "rating_distribution": {
            str(i): ratings.count(i) for i in range(1, 6)
        },
        "recent": items[-10:],
    }
