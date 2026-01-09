from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..services.prometheus_metrics import prometheus_metrics


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
        except Exception:
            duration = max(0.0, float(time.perf_counter() - start))
            path = request.url.path
            if not (
                path.startswith("/metrics")
                or path.startswith("/docs")
                or path.startswith("/redoc")
                or path.startswith("/openapi.json")
                or path.startswith("/health")
            ):
                route_obj = request.scope.get("route")
                route_path = getattr(route_obj, "path", None)
                route = str(route_path or path)
                prometheus_metrics.record_http(
                    method=str(request.method or "GET"),
                    route=route,
                    status_code=500,
                    duration_seconds=duration,
                )
            raise
        finally:
            if response is not None:
                duration = max(0.0, float(time.perf_counter() - start))
                path = request.url.path
                if not (
                    path.startswith("/metrics")
                    or path.startswith("/docs")
                    or path.startswith("/redoc")
                    or path.startswith("/openapi.json")
                    or path.startswith("/health")
                ):
                    route_obj = request.scope.get("route")
                    route_path = getattr(route_obj, "path", None)
                    route = str(route_path or path)
                    status_code = int(getattr(response, "status_code", 0) or 0)
                    prometheus_metrics.record_http(
                        method=str(request.method or "GET"),
                        route=route,
                        status_code=status_code,
                        duration_seconds=duration,
                    )

        if response is None:
            raise RuntimeError("metrics_middleware_missing_response")
        return response
