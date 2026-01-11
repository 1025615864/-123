from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        incoming = str(request.headers.get("X-Request-Id") or "").strip()
        request_id = incoming if incoming else uuid.uuid4().hex
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers.setdefault("X-Request-Id", request_id)
        return response
