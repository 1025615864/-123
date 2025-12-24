"""百姓法律助手 - FastAPI主应用"""
from contextlib import asynccontextmanager
import logging
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import ResponseValidationError
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import init_db
from .services.cache_service import cache_service
from .database import AsyncSessionLocal
from .routers import api_router, websocket
from .middleware.logging_middleware import RequestLoggingMiddleware, ErrorLoggingMiddleware
from .middleware.rate_limit import RateLimitMiddleware
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

    async def _scheduled_news_loop():
        while not stop_event.is_set():
            try:
                async with AsyncSessionLocal() as session:
                    from .services.news_service import news_service

                    _ = await news_service.process_scheduled_news(session)
            except Exception:
                logger.exception("处理定时新闻任务失败")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=30.0)
            except asyncio.TimeoutError:
                pass

    scheduled_task = asyncio.create_task(_scheduled_news_loop())

    if settings.redis_url:
        _ = await cache_service.connect(settings.redis_url)

    logger.info("数据库初始化完成")
    if ai is not None:
        logger.info("AI助手模块已启用")
    else:
        logger.info("AI助手模块未启用")
    
    yield

    stop_event.set()
    scheduled_task.cancel()
    try:
        await scheduled_task
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
        memory_mb = process.memory_info().rss / 1024 / 1024
        checks_detail["memory"] = {
            "status": "ok",
            "usage_mb": round(memory_mb, 2)
        }
    except ImportError:
        checks_detail["memory"] = {"status": "unknown"}
    
    return checks


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
