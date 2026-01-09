"""百姓法律助手 - FastAPI主应用"""
from contextlib import asynccontextmanager
import logging
import asyncio
import os
import time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.exceptions import ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .services.cache_service import cache_service
from .services.prometheus_metrics import prometheus_metrics
from .database import AsyncSessionLocal
from .routers import api_router, websocket
from .middleware.logging_middleware import RequestLoggingMiddleware, ErrorLoggingMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .middleware.metrics_middleware import MetricsMiddleware
from .middleware.envelope_middleware import EnvelopeMiddleware
from .utils.periodic_task_runner import PeriodicLockedRunner
# from .routers import ai  # AI module disabled - needs langchain dependencies

settings = get_settings()

logger = logging.getLogger(__name__)

try:
    from .routers import ai
except Exception:
    ai = None
    logger.exception("AI路由加载失败")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    _ = app
    await init_db()

    stop_event = asyncio.Event()

    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=cache_service, logger=logger)

    scheduled_enabled = True
    redis_connected = False

    async def _scheduled_news_job(session: AsyncSession) -> object:
        from .services.news_service import news_service

        return await news_service.process_scheduled_news(session)

    async def _scheduled_news_job_wrapper() -> object:
        start = time.perf_counter()
        ok = True
        try:
            async with AsyncSessionLocal() as session:
                return await _scheduled_news_job(session)
        except Exception:
            ok = False
            raise
        finally:
            prometheus_metrics.record_job(
                name="scheduled_news",
                ok=bool(ok),
                duration_seconds=max(0.0, float(time.perf_counter() - start)),
            )

    if settings.redis_url:
        redis_connected = bool(await cache_service.connect(settings.redis_url))

    if (not settings.debug) and (not redis_connected):
        scheduled_enabled = False
        logger.warning("Redis未连接且DEBUG为False：已禁用定时新闻任务（避免多worker重复执行）")

    scheduled_task: asyncio.Task[None] | None = None
    if scheduled_enabled:
        scheduled_task = asyncio.create_task(
            runner.run(
                lock_key="locks:scheduled_news",
                lock_ttl_seconds=60,
                interval_seconds=30.0,
                job=_scheduled_news_job_wrapper,
            )
        )

    rss_feeds_raw = os.getenv("RSS_FEEDS", "").strip()
    rss_ingest_enabled_raw = os.getenv("RSS_INGEST_ENABLED", "").strip().lower()
    rss_ingest_enabled_flag = rss_ingest_enabled_raw in {"1", "true", "yes", "on"}
    rss_enabled = bool(rss_feeds_raw) or bool(rss_ingest_enabled_flag) or bool(settings.debug)
    if (not settings.debug) and (not redis_connected):
        rss_enabled = False

    async def _rss_ingest_job_wrapper() -> object:
        start = time.perf_counter()
        ok = True
        try:
            async with AsyncSessionLocal() as session:
                from .services.rss_ingest_service import rss_ingest_service

                return await rss_ingest_service.run_once(session)
        except Exception:
            ok = False
            raise
        finally:
            prometheus_metrics.record_job(
                name="rss_ingest",
                ok=bool(ok),
                duration_seconds=max(0.0, float(time.perf_counter() - start)),
            )

    rss_task: asyncio.Task[None] | None = None
    if rss_enabled:
        rss_interval_seconds = float(os.getenv("RSS_INGEST_INTERVAL_SECONDS", "300").strip() or "300")
        rss_task = asyncio.create_task(
            runner.run(
                lock_key="locks:rss_ingest",
                lock_ttl_seconds=60,
                interval_seconds=rss_interval_seconds,
                job=_rss_ingest_job_wrapper,
            )
        )

    news_ai_enabled_raw = os.getenv("NEWS_AI_ENABLED", "").strip().lower()
    news_ai_enabled = news_ai_enabled_raw in {"1", "true", "yes", "on"}
    if (not settings.debug) and (not redis_connected):
        news_ai_enabled = False

    async def _news_ai_job_wrapper() -> object:
        start = time.perf_counter()
        ok = True
        try:
            async with AsyncSessionLocal() as session:
                from .services.news_ai_pipeline_service import news_ai_pipeline_service

                return await news_ai_pipeline_service.run_once(session)
        except Exception:
            ok = False
            raise
        finally:
            prometheus_metrics.record_job(
                name="news_ai_pipeline",
                ok=bool(ok),
                duration_seconds=max(0.0, float(time.perf_counter() - start)),
            )

    news_ai_task: asyncio.Task[None] | None = None
    if news_ai_enabled:
        news_ai_interval_seconds = float(os.getenv("NEWS_AI_INTERVAL_SECONDS", "120").strip() or "120")
        news_ai_task = asyncio.create_task(
            runner.run(
                lock_key="locks:news_ai_pipeline",
                lock_ttl_seconds=60,
                interval_seconds=news_ai_interval_seconds,
                job=_news_ai_job_wrapper,
            )
        )

    settlement_enabled_raw = os.getenv("SETTLEMENT_JOB_ENABLED", "").strip().lower()
    settlement_enabled_flag = settlement_enabled_raw in {"1", "true", "yes", "on"}
    settlement_enabled = bool(settlement_enabled_flag) or bool(settings.debug)
    if (not settings.debug) and (not redis_connected):
        settlement_enabled = False

    async def _settlement_job_wrapper() -> object:
        start = time.perf_counter()
        ok = True
        try:
            async with AsyncSessionLocal() as session:
                from .services.settlement_service import settlement_service

                return await settlement_service.settle_due_income_records(session)
        except Exception:
            ok = False
            raise
        finally:
            prometheus_metrics.record_job(
                name="settlement",
                ok=bool(ok),
                duration_seconds=max(0.0, float(time.perf_counter() - start)),
            )

    settlement_task: asyncio.Task[None] | None = None
    if settlement_enabled:
        settlement_interval_seconds = float(
            os.getenv("SETTLEMENT_JOB_INTERVAL_SECONDS", "3600").strip() or "3600"
        )
        settlement_task = asyncio.create_task(
            runner.run(
                lock_key="locks:settlement",
                lock_ttl_seconds=60,
                interval_seconds=settlement_interval_seconds,
                job=_settlement_job_wrapper,
            )
        )

    wechatpay_refresh_enabled_raw = os.getenv("WECHATPAY_CERT_REFRESH_ENABLED", "").strip().lower()
    wechatpay_refresh_enabled = wechatpay_refresh_enabled_raw in {"1", "true", "yes", "on"}
    if (not settings.debug) and (not redis_connected):
        wechatpay_refresh_enabled = False

    async def _wechatpay_platform_certs_refresh_job_wrapper() -> object:
        start = time.perf_counter()
        ok = True
        try:
            async with AsyncSessionLocal() as session:
                if not (
                    settings.wechatpay_mch_id
                    and settings.wechatpay_mch_serial_no
                    and settings.wechatpay_private_key
                    and settings.wechatpay_api_v3_key
                ):
                    return {"skipped": True, "reason": "wechatpay config missing"}

                from .models.system import SystemConfig
                from .utils.wechatpay_v3 import fetch_platform_certificates, dump_platform_certs_json

                certs = await fetch_platform_certificates(
                    certificates_url=settings.wechatpay_certificates_url,
                    mch_id=settings.wechatpay_mch_id,
                    mch_serial_no=settings.wechatpay_mch_serial_no,
                    mch_private_key_pem=settings.wechatpay_private_key,
                    api_v3_key=settings.wechatpay_api_v3_key,
                )
                raw = dump_platform_certs_json(certs)

                res = await session.execute(
                    select(SystemConfig).where(SystemConfig.key == "WECHATPAY_PLATFORM_CERTS_JSON")
                )
                row = res.scalar_one_or_none()
                if row is None:
                    row = SystemConfig(
                        key="WECHATPAY_PLATFORM_CERTS_JSON",
                        value=raw,
                        category="payment",
                        description="WeChatPay platform certificates cache",
                    )
                    session.add(row)
                else:
                    row.value = raw
                    row.category = "payment"
                    if not (row.description or "").strip():
                        row.description = "WeChatPay platform certificates cache"
                    session.add(row)

                await session.commit()
                return {"ok": True, "count": len(certs)}
        except Exception:
            ok = False
            raise
        finally:
            prometheus_metrics.record_job(
                name="wechatpay_platform_certs_refresh",
                ok=bool(ok),
                duration_seconds=max(0.0, float(time.perf_counter() - start)),
            )

    wechatpay_task: asyncio.Task[None] | None = None
    if wechatpay_refresh_enabled:
        interval_seconds = float(os.getenv("WECHATPAY_CERT_REFRESH_INTERVAL_SECONDS", "86400").strip() or "86400")
        wechatpay_task = asyncio.create_task(
            runner.run(
                lock_key="locks:wechatpay_platform_certs",
                lock_ttl_seconds=120,
                interval_seconds=interval_seconds,
                job=_wechatpay_platform_certs_refresh_job_wrapper,
            )
        )

    logger.info("数据库初始化完成")
    if ai is not None:
        logger.info("AI助手模块已启用")
    else:
        logger.info("AI助手模块未启用")
    
    yield

    stop_event.set()
    for t in (scheduled_task, rss_task, news_ai_task, wechatpay_task, settlement_task):
        if t is None:
            continue
        _ = t.cancel()
        try:
            await t
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    await cache_service.disconnect()

    logger.info("应用关闭")


app = FastAPI(
    title=settings.app_name,
    description="""
# 百姓法律助手 API

提供AI法律咨询、论坛交流、新闻资讯、律所查询等服务的RESTful API。

## 功能模块

- **👤 用户模块** - 注册、登录、个人信息管理
- **🤖 AI咨询** - 智能法律问答、会话管理
- **📰 新闻资讯** - 法律新闻浏览
- **💬 社区论坛** - 帖子发布、评论互动
- **🏢 律所服务** - 律所/律师查询、预约咨询
- **📄 文书生成** - 法律文书模板生成
- **🔍 全局搜索** - 跨模块搜索
- **⚙️ 系统管理** - 配置管理、数据统计

## 认证方式

使用 JWT Bearer Token 认证，在请求头中添加：
```
Authorization: Bearer <your_token>
```

## 错误码说明

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 422 | 数据验证失败 |
| 500 | 服务器错误 |
""",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=[
        {"name": "用户管理", "description": "用户注册、登录、个人信息管理"},
        {"name": "AI法律助手", "description": "AI智能法律咨询"},
        {"name": "知识库管理", "description": "法律知识库与咨询模板管理"},
        {"name": "新闻资讯", "description": "法律新闻浏览"},
        {"name": "社区论坛", "description": "帖子发布、评论互动"},
        {"name": "律所服务", "description": "律所/律师查询"},
        {"name": "文书生成", "description": "法律文书模板生成"},
        {"name": "全局搜索", "description": "跨模块搜索"},
        {"name": "系统管理", "description": "配置管理、数据统计"},
        {"name": "文件上传", "description": "文件上传管理"},
        {"name": "通知管理", "description": "消息通知"},
        {"name": "支付管理", "description": "订单与支付"},
        {"name": "WebSocket", "description": "实时消息"},
        {"name": "管理后台", "description": "管理员功能"},
    ],
    contact={
        "name": "百姓法律助手团队",
        "email": "support@baixing-law.com",
    },
    license_info={
        "name": "MIT License",
    }
)


@app.exception_handler(ResponseValidationError)
async def response_validation_exception_handler(request: Request, exc: ResponseValidationError):
    logger.exception("Response validation error path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": exc.errors() if settings.debug else "服务器错误"},
    )

app.add_middleware(ErrorLoggingMiddleware)
app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 添加速率限制中间件
app.add_middleware(
    RateLimitMiddleware,
    requests_per_minute=120,
    requests_per_second=20,
    excluded_paths=["/docs", "/redoc", "/openapi.json", "/health", "/api/health", "/", "/api/docs"],
    trusted_proxies=settings.trusted_proxies,
)

app.add_middleware(MetricsMiddleware)
app.add_middleware(EnvelopeMiddleware)

app.include_router(api_router, prefix="/api")
app.include_router(websocket.router)


@app.get("/")
async def root():
    """根路由"""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "message": "欢迎使用百姓法律助手API",
        "docs": "/docs"
    }


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy"}


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics_endpoint(request: Request):
    token = os.getenv("METRICS_AUTH_TOKEN", "").strip()
    if token:
        auth = str(request.headers.get("Authorization") or "").strip()
        if auth != f"Bearer {token}":
            return PlainTextResponse(content="unauthorized\n", status_code=401)

    body = prometheus_metrics.render_prometheus()
    return PlainTextResponse(content=body, media_type="text/plain; version=0.0.4")


@app.get("/api/health")
async def api_health_check():
    """健康检查（API别名，兼容前端proxy）"""
    return {"status": "healthy"}


@app.get("/health/detailed")
async def health_check_detailed():
    """详细健康检查"""
    import time
    from datetime import datetime
    
    checks: dict[str, object] = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
        "checks": {}
    }

    checks_detail = checks.get("checks")
    if not isinstance(checks_detail, dict):
        checks_detail = {}
        checks["checks"] = checks_detail
    
    # 数据库检查
    try:
        from sqlalchemy import text
        from .database import engine
        start = time.time()
        async with engine.connect() as conn:
            _ = await conn.execute(text("SELECT 1"))
        db_time = (time.time() - start) * 1000
        checks_detail["database"] = {
            "status": "ok",
            "response_time_ms": round(db_time, 2)
        }
    except Exception as e:
        checks["status"] = "degraded"
        checks_detail["database"] = {
            "status": "error",
            "error": str(e)
        }
    
    # AI服务检查
    if settings.openai_api_key:
        checks_detail["ai_service"] = {"status": "configured"}
    else:
        checks_detail["ai_service"] = {"status": "not_configured"}
    
    # 内存使用
    try:
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()
        rss_bytes = int(getattr(mem_info, "rss", 0) or 0)
        memory_mb = float(rss_bytes) / 1024.0 / 1024.0
        checks_detail["memory"] = {
            "status": "ok",
            "usage_mb": round(memory_mb, 2)
        }
    except ImportError:
        checks_detail["memory"] = {"status": "unknown"}
    
    return checks
