"""
心镜·AIGC智能体平台 — FastAPI 主入口
=======================================

基于国产算力平台（沐曦MetaX GPU / Gitee.AI）的AIGC智能体系统。
为第八届全球校园人工智能算法精英大赛·算法创新赛·赛题5「AI+学科交叉」设计。

启动方式:
    python run_backend.py
    或
    uvicorn backend.main:app --host 0.0.0.0 --port 8000

API文档:
    http://localhost:8000/docs
    http://localhost:8000/redoc
"""

from __future__ import annotations
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_settings
from backend.models.scale_result import ScaleResult  # noqa: F401 预注册避免Student关系引用失败

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def seed_data():
    """预种演示数据：3个学生 + 7天历史情绪记录 + 预警"""
    import random, json
    from datetime import datetime, timedelta
    from backend.database import engine, Base, SessionLocal
    from backend.models.student import Student
    from backend.models.emotion_record import EmotionRecord

    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        if db.query(Student).count() == 0:
            db.add_all([
                Student(
                    name="张三", class_name="计算机科学2024",
                    student_code="2024-CS-001", baseline_mood=0.72,
                    school="示范中学", grade="大一"
                ),
                Student(
                    name="李四", class_name="计算机科学2024",
                    student_code="2024-CS-002", baseline_mood=0.55,
                    school="示范中学", grade="大一"
                ),
                Student(
                    name="王五", class_name="计算机科学2024",
                    student_code="2024-CS-003", baseline_mood=0.81,
                    school="示范中学", grade="大一"
                ),
            ])
            db.commit()
            logger.info("已创建3个种子学生")

        if db.query(EmotionRecord).count() == 0:
            students = db.query(Student).all()
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

            EMOTION_VA = {
                "开心": (0.8, 0.6), "平静": (0.3, -0.3), "中性": (0.0, 0.0),
                "焦虑": (-0.4, 0.7), "悲伤": (-0.7, -0.2), "愤怒": (-0.6, 0.8),
                "惊讶": (0.2, 0.9),
            }
            POSITIVE = ["开心", "平静", "中性"]
            NEGATIVE = ["焦虑", "悲伤"]
            OTHER = ["愤怒", "惊讶"]

            records_batch = []
            for day_offset in range(6, 0, -1):
                day = today - timedelta(days=day_offset)
                for student in students:
                    baseline = student.baseline_mood
                    for hour in range(8, 21):
                        minute = random.randint(0, 59)
                        ts = f"{day.strftime('%Y-%m-%d')}T{hour:02d}:{minute:02d}:00"

                        r = random.random()
                        if r < baseline * 0.75:
                            emotion = random.choice(POSITIVE)
                        elif r < baseline * 0.75 + (1 - baseline) * 0.55:
                            emotion = random.choice(NEGATIVE)
                        else:
                            emotion = random.choice(OTHER)

                        va = EMOTION_VA[emotion]
                        valence = va[0] + random.uniform(-0.15, 0.15)
                        arousal = va[1] + random.uniform(-0.15, 0.15)
                        conf = round(0.70 + random.uniform(0, 0.25), 3)
                        score = round(max(0, min(1, 0.5 + valence * 0.25 + arousal * 0.25 + random.uniform(-0.05, 0.05))), 3)

                        records_batch.append(EmotionRecord(
                            student_id=student.id,
                            image_path=f"seed_day{day_offset}_s{student.id}_{hour:02d}{minute:02d}.mp4",
                            facial_emotion=emotion, facial_conf=conf,
                            facial_valence=round(valence, 3),
                            facial_arousal=round(arousal, 3),
                            vestibular_valence=round(valence + random.uniform(-0.1, 0.1), 3),
                            vestibular_arousal=round(arousal + random.uniform(-0.1, 0.1), 3),
                            vestibular_confidence=round(conf - random.uniform(0, 0.1), 3),
                            vestibular_intensity=round(random.uniform(0.3, 0.9), 3),
                            fused_emotion=emotion, fused_score=score,
                            fused_valence=round(valence, 3),
                            fused_arousal=round(arousal, 3),
                            confidence_diff=round(random.uniform(0.02, 0.15), 3),
                            requires_review=0,
                            estimated_accuracy=round(0.90 + random.uniform(0, 0.07), 2),
                            is_manual=0, recorded_at=ts,
                        ))

            db.add_all(records_batch)
            db.commit()
            logger.info(f"已预种 {len(records_batch)} 条历史情绪记录（6天 × 3学生）")

    finally:
        db.close()

    # 预种预警数据：确保绿/黄/红各一条
    from backend.database import SessionLocal as _SL
    from backend.models.alert import Alert as _Alert
    _db = _SL()
    try:
        if _db.query(_Alert).count() == 0:
            severities = ["green", "yellow", "red"]
            reasons = {
                "green": "近期情绪状态稳定，各项指标正常，保持良好状态",
                "yellow": "情绪存在轻度波动，负面情绪占比略高，建议适度关注",
                "red": "近期情绪波动明显，负面情绪累积，建议安排一对一访谈",
            }
            for s, sev in zip(sorted(_db.query(Student).all(), key=lambda x: x.baseline_mood, reverse=True), severities):
                ch = ["看板","APP"] if sev=="green" else (["看板","APP","微信(班主任)"] if sev=="yellow" else ["看板","APP","微信(班主任)","微信(家长)","短信","邮件","紧急电话"])
                _db.add(_Alert(
                    student_id=s.id,
                    severity=sev, risk_level=sev,
                    alert_reason=reasons[sev], risk_reason=reasons[sev],
                    overall_score={"green":0.82,"yellow":0.58,"red":0.31}[sev],
                    feedback_channel=",".join(ch),
                    feedback_content=f"[{sev.upper()}] {s.name}: {reasons[sev]}",
                    sent_channels=json.dumps(ch),
                    triggered_at=datetime.now().isoformat(),
                ))
            _db.commit()
            logger.info("已预种 3 条预警记录（绿/黄/红各一）")
    finally:
        _db.close()

    # 预种量表测评数据
    from backend.models.scale_result import ScaleResult as _SR
    from backend.api.routes.scales import _load_scale as _load_scale_def, _score_scale as _score_scale_def
    _db2 = _SL()
    try:
        if _db2.query(_SR).count() == 0:
            import random as _rnd
            _rnd.seed(42)
            all_students = _db2.query(Student).all()
            seeded_count = 0
            for student in all_students:
                for scale_code in ("SAS", "SDS"):
                    scale_def = _load_scale_def(scale_code)
                    n_items = len(scale_def["questions"])
                    answers = [_rnd.randint(1, 4) for _ in range(n_items)]
                    scoring = _score_scale_def(scale_def, answers)
                    _db2.add(_SR(
                        student_id=student.id, scale_type=scale_code,
                        raw_score=scoring["raw_score"], standard_score=scoring["standard_score"],
                        level=scoring["level"],
                        dimension_scores=json.dumps(scoring["dimension_scores"], ensure_ascii=False),
                        answers=json.dumps(answers),
                        submitted_at=datetime.now().isoformat(),
                    ))
                    seeded_count += 1

            _db2.commit()
            logger.info(f"已预种 {seeded_count} 条量表测评记录（按标准题库计分）")
    finally:
        _db2.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    settings = get_settings()
    os.makedirs(settings.upload_dir, exist_ok=True)
    os.makedirs(settings.camera_dir, exist_ok=True)
    os.makedirs("data/obs", exist_ok=True)

    # 初始化数据库
    seed_data()

    # 启动定时调度器
    try:
        from backend.scheduler.jobs import start_scheduler
        start_scheduler()
        logger.info("定时调度器已启动")
    except Exception as e:
        logger.warning(f"调度器启动失败(非关键): {e}")

    # 打印平台信息
    try:
        from backend.llm.platform_adapter import PlatformAdapter
        platforms = PlatformAdapter.list_platforms()
        configured = [p["name"] for p in platforms if p["is_configured"]]
        logger.info(f"已配置的AI平台: {', '.join(configured) if configured else '无(使用模拟模式)'}")
    except Exception:
        pass

    # 打印 GPU 信息
    try:
        from backend.vibraimage.gpu_backend import detect_gpu
        gpu_info = detect_gpu()
        if gpu_info["available"]:
            _mb = gpu_info.get("memory_mb", 0)
            _mem = f"{_mb // 1024}GB" if _mb >= 1024 else f"{_mb}MB"
            logger.info(f"GPU检测: {gpu_info['vendor']} {gpu_info['model']} ({_mem}), 后端={gpu_info['backend']}")
        else:
            logger.info("GPU检测: 未检测到GPU，VibraImage将使用CPU(numpy)")
    except Exception:
        logger.info("GPU检测: 检测失败，使用CPU兜底")
        pass

    logger.info(f"心镜·AIGC智能体平台 v{settings.service_version} 已启动")
    logger.info(f"Lingshu-32B running on moark.com (沐曦 MetaX GPU)")
    logger.info(f"API文档: http://localhost:8000/docs")

    yield

    logger.info("服务正在关闭...")


app = FastAPI(
    title="心镜·AIGC智能体平台",
    description=(
        "基于国产算力平台（沐曦MetaX GPU / Gitee.AI）的AIGC智能体系统。\n\n"
        "**第八届全球校园人工智能算法精英大赛 · 算法创新赛 赛题5「AI+学科交叉」**\n\n"
        "核心特性:\n"
        "- 🧠 多智能体协作架构（感知→分析→报告→预警→协调）\n"
        "- ✨ AIGC内容生成（心理报告、干预方案、家校沟通函、成长叙事）\n"
        "- 🇨🇳 国产算力平台适配（沐曦GPU / Gitee.AI）\n"
        "- 📊 实时情绪监测与深度心理健康分析\n"
        "- 🔔 三级预警与多渠道反馈"
    ),
    version="2.2.0",
    lifespan=lifespan,
    docs_url=None,   # 禁用默认英文 Swagger，改用下方自定义中文页面
    redoc_url="/redoc",
)

# ---- 中间件注册（注意：Starlette 按注册逆序执行） ----
settings = get_settings()

# 3. CORS（最外层）
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. 限流
from backend.middleware.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# 1. API 日志（最内层，记录所有请求）
from backend.middleware.logging import APILoggingMiddleware
app.add_middleware(APILoggingMiddleware)

# ---- 全局异常处理 ----
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"未处理异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "服务器内部错误",
            "detail": str(exc)[:200] if settings.ai_platform != "lingshu" else "内部错误",
        },
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    return JSONResponse(
        status_code=422,
        content={"success": False, "error": "请求参数验证失败", "detail": str(exc)},
    )

# 注册路由
from backend.api.routes.upload import router as upload_router
from backend.api.routes.sse import router as sse_router
from backend.api.routes.dashboard import router as dashboard_router
from backend.api.routes.students import router as students_router
from backend.api.routes.alerts import router as alerts_router
from backend.api.routes.aigc import router as aigc_router
from backend.api.routes.agents import router as agents_router
from backend.api.routes.vibraimage import router as vibraimage_router
from backend.api.routes.scales import router as scales_router
from backend.api.routes.admin import router as admin_router
from backend.api.routes.fusion import router as fusion_router
from backend.api.routes.virtual_subject import router as virtual_subject_router
from backend.api.routes.emotion_forecast import router as emotion_forecast_router
from backend.api.routes.risk_assessment import router as risk_assessment_router
from backend.api.routes.classic_experiments import router as classic_experiments_router

app.include_router(upload_router, prefix="/api")
app.include_router(sse_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(students_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(aigc_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(vibraimage_router)
app.include_router(scales_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(fusion_router, prefix="/api")
app.include_router(virtual_subject_router, prefix="/api")
app.include_router(emotion_forecast_router, prefix="/api")
app.include_router(risk_assessment_router, prefix="/api")
app.include_router(classic_experiments_router, prefix="/api")

# 注册 GPU 状态 API
from backend.gpu import register_gpu_routes
register_gpu_routes(app)


@app.get("/api/health")
def health():
    """健康检查 + 平台信息"""
    platform_info = "未知"
    model_info = ""
    try:
        from backend.config import get_settings
        s = get_settings()
        platform_map = {
            "lingshu": "moark.com Lingshu-32B (沐曦MetaX GPU)",
            "gitee_ai": "沐曦MetaX GPU / Gitee.AI",
            "deepseek": "DeepSeek",
            "local": "本地模型",
            "custom": "自定义平台",
        }
        platform_info = platform_map.get(s.ai_platform, s.ai_platform)
        if s.ai_platform == "lingshu":
            model_info = s.lingshu_model
    except Exception:
        pass

    return {
        "status": "ok",
        "service": "心镜·AIGC智能体平台",
        "version": "2.4.0",
        "platform": platform_info,
        "model": model_info,
        "competition": "第八届全球校园人工智能算法精英大赛 · AI+学科交叉",
    }


STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
STATIC_INDEX = os.path.join(STATIC_DIR, "index.html")
HAS_FRONTEND = os.path.isfile(STATIC_INDEX)


@app.get("/")
def root():
    """根路径：有前端则服务前端，否则跳转 API 文档。"""
    if HAS_FRONTEND:
        return FileResponse(STATIC_INDEX)
    return RedirectResponse(url="/docs")


@app.get("/docs", include_in_schema=False)
def custom_swagger_ui_html():
    """中文 Swagger UI 文档页面"""
    from fastapi.responses import HTMLResponse
    import os
    html_path = os.path.join(os.path.dirname(__file__), "static", "swagger-chinese.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/docs-en", include_in_schema=False)
def english_swagger_ui_html():
    """英文 Swagger UI 文档页面（备用）"""
    from fastapi.openapi.docs import get_swagger_ui_html
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=app.title + " - API Docs",
        swagger_js_url="https://registry.npmmirror.com/swagger-ui-dist/latest/files/swagger-ui-bundle.js",
        swagger_css_url="https://registry.npmmirror.com/swagger-ui-dist/latest/files/swagger-ui.css",
    )


if HAS_FRONTEND:
    # CloudBase 部署模式：前端 SPA fallback
    @app.get("/{path:path}")
    async def spa_fallback(path: str = ""):
        # API 路径由已注册的路由处理，此处不会被拦截（FastAPI 先匹配精确路径）
        # 此处仅处理前端 SPA 路由回退
        file_path = os.path.join(STATIC_DIR, path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(STATIC_INDEX)
