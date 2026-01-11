from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

try:
    import sentry_sdk
except Exception:  # pragma: no cover
    sentry_sdk = None


class SentryContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if sentry_sdk is None or (not bool(getattr(sentry_sdk, "is_initialized", lambda: False)())):
            return await call_next(request)

        request_id = str(getattr(getattr(request, "state", None), "request_id", "") or "").strip()
        user_id = getattr(getattr(request, "state", None), "user_id", None)

        with sentry_sdk.configure_scope() as scope:
            if request_id:
                scope.set_tag("request_id", request_id)
            if user_id is not None:
                scope.set_tag("user_id", str(user_id))
                scope.set_user({"id": str(user_id)})
            return await call_next(request)
