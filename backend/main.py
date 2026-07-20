"""
心镜·AIGC智能体平台 — FastAPI 主入口
=======================================

基于国产算力平台（沐曦MetaX GPU / Gitee.AI）的AIGC智能体系统。
为第八届CCF开源创新大赛·国产开源GPU AI创新生态赛 任务三设计。

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def seed_data():
    """预种演示数据：3个学生 + 7天历史情绪记录"""
    import random
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

    logger.info(f"心镜·AIGC智能体平台 v{settings.service_version} 已启动")
    logger.info(f"API文档: http://localhost:8000/docs")

    yield

    logger.info("服务正在关闭...")


app = FastAPI(
    title="心镜·AIGC智能体平台",
    description=(
        "基于国产算力平台（沐曦MetaX GPU / Gitee.AI）的AIGC智能体系统。\n\n"
        "**第八届CCF开源创新大赛 · 国产开源GPU AI创新生态赛 任务三**\n\n"
        "核心特性:\n"
        "- 🧠 多智能体协作架构（感知→分析→报告→预警→协调）\n"
        "- ✨ AIGC内容生成（心理报告、干预方案、家校沟通函、成长叙事）\n"
        "- 🇨🇳 国产算力平台适配（沐曦GPU / Gitee.AI）\n"
        "- 📊 实时情绪监测与深度心理健康分析\n"
        "- 🔔 三级预警与多渠道反馈"
    ),
    version="2.0.0",
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
from backend.api.routes.admin import router as admin_router

app.include_router(upload_router, prefix="/api")
app.include_router(sse_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")
app.include_router(students_router, prefix="/api")
app.include_router(alerts_router, prefix="/api")
app.include_router(aigc_router, prefix="/api")
app.include_router(agents_router, prefix="/api")
app.include_router(vibraimage_router)
app.include_router(admin_router, prefix="/api")


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
        "version": "2.1.0",
        "platform": platform_info,
        "model": model_info,
        "competition": "第八届CCF开源创新大赛 - 任务三",
    }


@app.get("/")
def root():
    """根路径重定向到API文档"""
    from fastapi.responses import RedirectResponse
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
