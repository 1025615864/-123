"""请求日志中间件"""
import json
import time
import logging
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..utils.rate_limiter import get_client_ip

logger = logging.getLogger("api.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志记录中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """处理请求并记录日志"""
        start_time = time.time()
        
        # 获取请求信息
        method = request.method
        path = request.url.path
        client_ip = get_client_ip(request)
        request_id = str(getattr(getattr(request, "state", None), "request_id", "") or "").strip()
        user_id = getattr(getattr(request, "state", None), "user_id", None)
        
        # 跳过健康检查和静态文件的日志
        skip_paths = ["/health", "/docs", "/redoc", "/openapi.json", "/favicon.ico"]
        should_log = not any(path.startswith(p) for p in skip_paths)
        
        try:
            response = await call_next(request)
            
            # 计算响应时间
            duration_ms = (time.time() - start_time) * 1000
            
            if should_log:
                # 根据状态码选择日志级别
                status_code = response.status_code
                payload = {
                    "event": "http_request",
                    "request_id": request_id or None,
                    "user_id": user_id,
                    "method": method,
                    "path": path,
                    "status": int(status_code),
                    "duration_ms": round(float(duration_ms), 2),
                    "client_ip": client_ip,
                }
                log_msg = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
                
                if status_code >= 500:
                    logger.error(log_msg)
                elif status_code >= 400:
                    logger.warning(log_msg)
                else:
                    logger.info(log_msg)
            
            # 添加响应头
            response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"
            
            return response
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            payload = {
                "event": "http_request_error",
                "request_id": request_id or None,
                "user_id": user_id,
                "method": method,
                "path": path,
                "status": None,
                "duration_ms": round(float(duration_ms), 2),
                "client_ip": client_ip,
                "error_type": type(e).__name__,
                "error": str(e),
            }
            logger.error(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), exc_info=True)
            raise


class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    """错误日志记录中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """捕获并记录未处理的异常"""
        try:
            return await call_next(request)
        except Exception as e:
            request_id = str(getattr(getattr(request, "state", None), "request_id", "") or "").strip()
            user_id = getattr(getattr(request, "state", None), "user_id", None)
            payload = {
                "event": "unhandled_exception",
                "request_id": request_id or None,
                "user_id": user_id,
                "method": request.method,
                "path": request.url.path,
                "error_type": type(e).__name__,
                "error": str(e),
            }
            logger.exception(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
            raise
