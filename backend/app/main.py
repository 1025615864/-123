"""百姓法律助手 - FastAPI主应用"""
from contextlib import asynccontextmanager
import importlib
import logging
import asyncio
import os
import time
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from fastapi.exceptions import ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .services.cache_service import cache_service
from .services.prometheus_metrics import prometheus_metrics
from .database import AsyncSessionLocal
from .routers import api_router, websocket
from .middleware.logging_middleware import RequestLoggingMiddleware, ErrorLoggingMiddleware
from .middleware.auth_context_middleware import AuthContextMiddleware
from .middleware.sentry_context_middleware import SentryContextMiddleware
from .middleware.request_id_middleware import RequestIdMiddleware
from .middleware.rate_limit import RateLimitMiddleware
from .middleware.metrics_middleware import MetricsMiddleware
from .middleware.envelope_middleware import EnvelopeMiddleware
from .utils.periodic_task_runner import PeriodicLockedRunner
# from .routers import ai  # AI module disabled - needs langchain dependencies

settings = get_settings()

logger = logging.getLogger(__name__)

try:
    import sentry_sdk
except Exception:
    sentry_sdk = None

if sentry_sdk is not None:
    dsn = str(getattr(settings, "sentry_dsn", "") or "").strip()
    if dsn:
        env = str(getattr(settings, "sentry_environment", "") or "").strip() or None
        release = str(getattr(settings, "sentry_release", "") or "").strip() or None
        traces = float(getattr(settings, "sentry_traces_sample_rate", 0.0) or 0.0)
        profiles = float(getattr(settings, "sentry_profiles_sample_rate", 0.0) or 0.0)
        _ = sentry_sdk.init(
            dsn=dsn,
            environment=env,
            release=release,
            traces_sample_rate=max(0.0, min(1.0, traces)),
            profiles_sample_rate=max(0.0, min(1.0, profiles)),
        )

try:
    from .routers import ai
except Exception:
    ai = None
    logger.exception("AI路由加载失败")


def _prom_escape_label_value(value: str) -> str:
    s = str(value)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', "\\\"")
    s = s.replace("\n", "\\n")
    return s


def _ai_metrics_extra_lines() -> list[str]:
    snap: dict[str, object] = {}
    try:
        mod = importlib.import_module("app.services.ai_metrics")
        ai_metrics_obj = getattr(mod, "ai_metrics", None)
        if ai_metrics_obj is not None:
            snapshot = getattr(ai_metrics_obj, "snapshot", None)
            if callable(snapshot):
                raw = snapshot()
                if isinstance(raw, dict):
                    snap = {str(k): v for k, v in raw.items()}
    except Exception:
        snap = {}

    started_at_obj = snap.get("started_at")
    started_at = (
        float(started_at_obj)
        if isinstance(started_at_obj, (int, float)) and not isinstance(started_at_obj, bool)
        else 0.0
    )

    chat_total_obj = snap.get("chat_requests_total")
    chat_total = (
        int(chat_total_obj)
        if isinstance(chat_total_obj, (int, float)) and not isinstance(chat_total_obj, bool)
        else 0
    )

    chat_stream_total_obj = snap.get("chat_stream_requests_total")
    chat_stream_total = (
        int(chat_stream_total_obj)
        if isinstance(chat_stream_total_obj, (int, float)) and not isinstance(chat_stream_total_obj, bool)
        else 0
    )

    errors_total_obj = snap.get("errors_total")
    errors_total = (
        int(errors_total_obj)
        if isinstance(errors_total_obj, (int, float)) and not isinstance(errors_total_obj, bool)
        else 0
    )

    error_code_counts_obj = snap.get("error_code_counts")
    endpoint_error_counts_obj = snap.get("endpoint_error_counts")

    error_code_counts: dict[str, int] = {}
    if isinstance(error_code_counts_obj, dict):
        for k_obj, v_obj in error_code_counts_obj.items():
            k = str(k_obj or "").strip()
            if not k:
                continue
            try:
                if isinstance(v_obj, (int, float)) and not isinstance(v_obj, bool):
                    error_code_counts[k] = int(v_obj)
                elif isinstance(v_obj, str):
                    error_code_counts[k] = int(float(v_obj.strip() or "0"))
            except Exception:
                continue

    endpoint_error_counts: dict[str, int] = {}
    if isinstance(endpoint_error_counts_obj, dict):
        for k_obj, v_obj in endpoint_error_counts_obj.items():
            k = str(k_obj or "").strip()
            if not k:
                continue
            try:
                if isinstance(v_obj, (int, float)) and not isinstance(v_obj, bool):
                    endpoint_error_counts[k] = int(v_obj)
                elif isinstance(v_obj, str):
                    endpoint_error_counts[k] = int(float(v_obj.strip() or "0"))
            except Exception:
                continue

    lines: list[str] = []
    lines.append("# HELP baixing_ai_started_at_seconds Unix timestamp when AiMetrics started")
    lines.append("# TYPE baixing_ai_started_at_seconds gauge")
    lines.append(f"baixing_ai_started_at_seconds {started_at}")
    lines.append("# HELP baixing_ai_chat_requests_total Total /ai/chat requests")
    lines.append("# TYPE baixing_ai_chat_requests_total counter")
    lines.append(f"baixing_ai_chat_requests_total {chat_total}")
    lines.append("# HELP baixing_ai_chat_stream_requests_total Total /ai/chat_stream requests")
    lines.append("# TYPE baixing_ai_chat_stream_requests_total counter")
    lines.append(f"baixing_ai_chat_stream_requests_total {chat_stream_total}")
    lines.append("# HELP baixing_ai_errors_total Total AI errors")
    lines.append("# TYPE baixing_ai_errors_total counter")
    lines.append(f"baixing_ai_errors_total {errors_total}")

    lines.append("# HELP baixing_ai_error_code_total Total errors grouped by error_code")
    lines.append("# TYPE baixing_ai_error_code_total counter")
    for code in sorted(error_code_counts.keys()):
        v = int(error_code_counts.get(code) or 0)
        if v <= 0:
            continue
        lines.append(
            f"baixing_ai_error_code_total{{error_code=\"{_prom_escape_label_value(code)}\"}} {v}"
        )

    lines.append("# HELP baixing_ai_endpoint_error_total Total errors grouped by endpoint")
    lines.append("# TYPE baixing_ai_endpoint_error_total counter")
    for ep in sorted(endpoint_error_counts.keys()):
        v = int(endpoint_error_counts.get(ep) or 0)
        if v <= 0:
            continue
        lines.append(
            f"baixing_ai_endpoint_error_total{{endpoint=\"{_prom_escape_label_value(ep)}\"}} {v}"
        )

    return lines


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    _ = app
    await init_db()

    stop_event = asyncio.Event()

    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=cache_service, logger=logger)

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
        raise RuntimeError("Redis must be available when DEBUG is False. Please set REDIS_URL and ensure Redis is reachable.")

    scheduled_task: asyncio.Task[None] | None = asyncio.create_task(
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

    review_sla_enabled_raw = os.getenv("REVIEW_TASK_SLA_JOB_ENABLED", "").strip().lower()
    review_sla_enabled_flag = review_sla_enabled_raw in {"1", "true", "yes", "on"}
    review_sla_enabled = bool(review_sla_enabled_flag) or bool(settings.debug)
    if (not settings.debug) and (not redis_connected):
        review_sla_enabled = False

    async def _review_task_sla_job_wrapper() -> object:
        start = time.perf_counter()
        ok = True
        try:
            async with AsyncSessionLocal() as session:
                from .services.review_task_sla_service import scan_and_notify_review_task_sla

                return await scan_and_notify_review_task_sla(session)
        except Exception:
            ok = False
            raise
        finally:
            prometheus_metrics.record_job(
                name="review_task_sla",
                ok=bool(ok),
                duration_seconds=max(0.0, float(time.perf_counter() - start)),
            )

    review_sla_task: asyncio.Task[None] | None = None
    if review_sla_enabled:
        interval_seconds = float(os.getenv("REVIEW_TASK_SLA_SCAN_INTERVAL_SECONDS", "60").strip() or "60")
        review_sla_task = asyncio.create_task(
            runner.run(
                lock_key="locks:review_task_sla",
                lock_ttl_seconds=60,
                interval_seconds=interval_seconds,
                job=_review_task_sla_job_wrapper,
            )
        )

    logger.info("数据库初始化完成")
    if ai is not None:
        logger.info("AI助手模块已启用")
    else:
        logger.info("AI助手模块未启用")
    
    yield

    stop_event.set()
    for t in (scheduled_task, rss_task, news_ai_task, wechatpay_task, settlement_task, review_sla_task):
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

app.add_middleware(SentryContextMiddleware)
app.add_middleware(AuthContextMiddleware)

app.add_middleware(RequestIdMiddleware)

app.include_router(api_router, prefix="/api")
app.include_router(websocket.router)


def _normalize_base_url(raw: str) -> str:
    base = str(raw or "").strip()
    if base.endswith("/"):
        base = base[:-1]
    return base


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    base = _normalize_base_url(getattr(settings, "frontend_base_url", "") or "")
    sitemap_url = f"{base}/sitemap.xml" if base else "/sitemap.xml"
    content = "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /admin",
            f"Sitemap: {sitemap_url}",
            "",
        ]
    )
    return PlainTextResponse(content=content, media_type="text/plain")


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    base = _normalize_base_url(getattr(settings, "frontend_base_url", "") or "")

    paths = [
        "/",
        "/chat",
        "/chat/history",
        "/forum",
        "/news",
        "/news/topics",
        "/lawfirm",
        "/search",
        "/calculator",
        "/limitations",
        "/documents",
        "/contracts",
        "/faq",
        "/vip",
        "/terms",
        "/privacy",
        "/ai-disclaimer",
    ]

    try:
        from .models.news import News, NewsTopic

        async with AsyncSessionLocal() as session:
            topics_res = await session.execute(
                select(NewsTopic.id)
                .where(NewsTopic.is_active == True)
                .order_by(desc(NewsTopic.sort_order), desc(NewsTopic.id))
            )
            topic_rows = topics_res.all()
            topic_ids: list[int] = []
            for (tid,) in topic_rows:
                try:
                    if tid is None:
                        continue
                    topic_ids.append(int(tid))
                except Exception:
                    continue
            for tid in topic_ids:
                paths.append(f"/news/topics/{tid}")

            news_limit = 500
            news_res = await session.execute(
                select(News.id)
                .where(News.is_published == True, News.review_status == "approved")
                .order_by(desc(News.published_at), desc(News.created_at), desc(News.id))
                .limit(int(news_limit))
            )
            news_rows = news_res.all()
            news_ids: list[int] = []
            for (nid,) in news_rows:
                try:
                    if nid is None:
                        continue
                    news_ids.append(int(nid))
                except Exception:
                    continue
            for nid in news_ids:
                paths.append(f"/news/{nid}")
    except Exception:
        logger.exception("failed to build dynamic sitemap urls")

    uniq_paths: list[str] = []
    seen: set[str] = set()
    for p in paths:
        if not isinstance(p, str):
            continue
        if p in seen:
            continue
        seen.add(p)
        uniq_paths.append(p)
    paths = uniq_paths

    def _loc(p: str) -> str:
        if not p.startswith("/"):
            p = "/" + p
        return f"{base}{p}" if base else p

    urls_xml: str = "\n".join(
        f"  <url>\n    <loc>{_loc(p)}</loc>\n  </url>" for p in paths
    )

    xml = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">\n"
        f"{urls_xml}\n"
        "</urlset>\n"
    )
    return Response(content=xml, media_type="application/xml")


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

    extra_lines = _ai_metrics_extra_lines()
    body = prometheus_metrics.render_prometheus(extra_lines=extra_lines)
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
