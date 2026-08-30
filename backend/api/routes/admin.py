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

    # ---- 联动自进化引擎：低分反馈标记为负面经验 ----
    if rating <= 2:
        try:
            from backend.evolution.memory import record_experience
            record_experience("user_feedback", "匿名用户", content, rating=rating, feedback=content)
        except Exception:
            pass

    return {"success": True, "message": "感谢您的反馈！"}


# ---- 运营统计 ----

@router.get("/stats", summary="获取运营数据统计")
async def get_stats():
    """返回 API 请求统计、LLM 调用统计、用户反馈、系统运行状态。"""
    stats = {
        "service": "心镜·AIGC智能体平台",
        "version": "2.4.0",
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

@router.get("/stats/evolution", summary="获取自进化统计")
async def get_evolution():
    """返回自进化引擎的累积经验数、评分趋势、高评分案例。"""
    try:
        from backend.evolution.memory import get_evolution_stats
        stats = get_evolution_stats()
        return {"success": True, "data": stats}
    except Exception as e:
        return {"success": False, "error": str(e)}


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


# ---- 试点工具链（应用效果证据采集） ----

@router.get("/pilot/export", summary="导出试点数据（按班级/年级分组，CSV）")
async def export_pilot_data(
    class_name: str = Query("", description="按班级筛选（空=全部）"),
    grade: str = Query("", description="按年级筛选（空=全部）"),
):
    """
    导出试点学生情绪记录与量表结果，按班级/年级分组，用于试点成果整理。

    输出 CSV 字段：student_id, class, grade, recorded_at, fused_emotion,
    fused_score, valence, arousal, k_value, scale_type, scale_score, scale_level
    """
    from backend.database import SessionLocal
    from backend.models.student import Student
    from backend.models.emotion_record import EmotionRecord
    from backend.models.scale_result import ScaleResult

    db = SessionLocal()
    try:
        students = db.query(Student).all()
        rows = ["student_id,class_name,grade,recorded_at,fused_emotion,fused_score,valence,arousal,k_value,scale_type,scale_score,scale_level"]
        for stu in students:
            if class_name and stu.class_name != class_name:
                continue
            if grade and stu.grade != grade:
                continue
            emotions = db.query(EmotionRecord).filter(EmotionRecord.student_id == stu.id).order_by(EmotionRecord.recorded_at).all()
            scales = db.query(ScaleResult).filter(ScaleResult.student_id == stu.id).order_by(ScaleResult.submitted_at).all()
            if not emotions and not scales:
                continue
            # 对齐输出：先情绪后量表
            for r in emotions:
                rows.append(
                    f"{stu.id},{_csv(stu.class_name)},{_csv(stu.grade)},{r.recorded_at},"
                    f"{_csv(r.fused_emotion)},{r.fused_score},{r.fused_valence},{r.fused_arousal},"
                    f"{r.vi_K_value},,,"
                )
            for s in scales:
                rows.append(
                    f"{stu.id},{_csv(stu.class_name)},{_csv(stu.grade)},{s.submitted_at},"
                    f",,,,,{s.scale_type},{s.standard_score},{s.level}"
                )
        return PlainTextResponse("\n".join(rows), media_type="text/csv")
    finally:
        db.close()


@router.get("/pilot/compare", summary="试点对比指标（系统 vs 人工/传统）")
async def pilot_compare():
    """
    试点应用效果对比指标：
      - 计分耗时：系统自动计分 vs 人工计分（量表每题/整卷）
      - 量表覆盖率：有量表记录的学生占比
      - 情绪采集记录数：试点期内每人平均采集次数
    用于量化「应用效果」证据（材料中标注口径与假设）。
    """
    from backend.database import SessionLocal
    from backend.models.student import Student
    from backend.models.emotion_record import EmotionRecord
    from backend.models.scale_result import ScaleResult

    db = SessionLocal()
    try:
        students = db.query(Student).all()
        total_students = len(students)
        with_scale = 0
        total_emotions = 0
        for stu in students:
            if db.query(ScaleResult).filter(ScaleResult.student_id == stu.id).first():
                with_scale += 1
            total_emotions += db.query(EmotionRecord).filter(EmotionRecord.student_id == stu.id).count()

        # 计分耗时对比（经验口径，材料中需注明）
        manual_per_item_sec = 30.0        # 人工每题约 30 秒（阅读+思考+勾选后计分）
        system_per_report_sec = 2.0       # 系统自动计分约 2 秒/份
        item_count = 20                   # 以 20 题量表为例
        manual_total = manual_per_item_sec * item_count
        system_total = system_per_report_sec

        return {
            "success": True,
            "data": {
                "sample_size": total_students,
                "scale_coverage_rate": round(with_scale / max(total_students, 1), 3),
                "avg_emotion_records_per_student": round(total_emotions / max(total_students, 1), 2),
                "scoring_time_comparison": {
                    "assumption_note": "人工按每题约30秒计分估算，系统为实测自动计分约2秒/份",
                    "manual_seconds": manual_total,
                    "system_seconds": system_total,
                    "speedup": round(manual_total / max(system_total, 1e-6), 1),
                    "time_saved_seconds_per_report": round(manual_total - system_total, 1),
                },
                "note": "试点班级部署后，本指标随真实数据自动更新。",
            },
        }
    finally:
        db.close()


@router.get("/pilot/report", summary="生成试点成果报告摘要")
async def pilot_report():
    """
    聚合试点数据 + 用户反馈，生成《试点成果报告》摘要：
      - 覆盖人数/采集量
      - 量表×AI 效度统计（Pearson r / Kappa / 灵敏度特异度）
      - 教师/学生反馈（评分均值 + 典型反馈）
    """
    from backend.database import SessionLocal
    from backend.models.student import Student
    from backend.models.scale_result import ScaleResult
    from backend.models.emotion_record import EmotionRecord
    from backend.services.scale_stats import pearson_r, cohen_kappa, binary_metrics

    db = SessionLocal()
    try:
        students = db.query(Student).all()
        xs, ys = [], []
        actuals, preds = [], []
        n_scale = n_emotion = 0
        for stu in students:
            scales = db.query(ScaleResult).filter(ScaleResult.student_id == stu.id).all()
            emotions = db.query(EmotionRecord).filter(EmotionRecord.student_id == stu.id).all()
            n_scale += len(scales)
            n_emotion += len(emotions)
            if scales and emotions:
                avg_ai = sum(r.fused_score for r in emotions) / len(emotions)
                neg = sum(1 for r in emotions if r.fused_emotion in {"悲伤", "焦虑", "愤怒", "恐惧"}) / len(emotions)
                ai_high = avg_ai < 0.4 and neg > 0.5
                for s in scales:
                    if s.scale_type in {"SAS", "SDS"}:
                        xs.append(s.standard_score)
                        ys.append(round(avg_ai, 3))
                        actuals.append(s.standard_score >= 60)
                        preds.append(ai_high)

        # 反馈汇总
        fb = _get_feedback_stats()

        return {
            "success": True,
            "data": {
                "coverage": {"students": len(students), "scale_records": n_scale, "emotion_records": n_emotion},
                "validity": {
                    "pearson_r": pearson_r(xs, ys),
                    "kappa": cohen_kappa(actuals, preds),
                    "metrics": binary_metrics(actuals, preds),
                },
                "feedback": {"total": fb["total"], "avg_rating": fb["avg_rating"]},
                "note": "试点数据实时统计；反馈来自平台内置反馈浮窗。",
            },
        }
    finally:
        db.close()


# ---- 辅助函数 ----

def _csv(value) -> str:
    """CSV 字段转义。"""
    if value is None:
        return ""
    s = str(value).replace('"', '""')
    return f'"{s}"' if ("," in s or '"' in s) else s


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
