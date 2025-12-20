"""请求日志中间件"""
import time
import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("api.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """请求日志记录中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并记录日志"""
        start_time = time.time()
        
        # 获取请求信息
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"
        
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
                log_msg = f"{method} {path} - {status_code} - {duration_ms:.2f}ms - {client_ip}"
                
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
            logger.error(f"{method} {path} - ERROR - {duration_ms:.2f}ms - {client_ip} - {str(e)}")
            raise


class ErrorLoggingMiddleware(BaseHTTPMiddleware):
    """错误日志记录中间件"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """捕获并记录未处理的异常"""
        try:
            return await call_next(request)
        except Exception as e:
            logger.exception(
                "Unhandled exception: %s %s - %s",
                request.method,
                request.url.path,
                str(e)
            )
            raise
