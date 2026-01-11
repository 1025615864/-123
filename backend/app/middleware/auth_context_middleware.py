from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..utils.security import decode_token


class AuthContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        user_id: int | None = None
        try:
            auth = str(request.headers.get("authorization") or "").strip()
            if auth.lower().startswith("bearer "):
                token = auth.split(" ", 1)[1].strip()
                payload = decode_token(token)
                if payload is not None:
                    sub = payload.get("sub")
                    if sub is not None:
                        try:
                            user_id = int(str(sub))
                        except Exception:
                            user_id = None
        except Exception:
            user_id = None

        request.state.user_id = user_id
        return await call_next(request)
