from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware


class EnvelopeMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        want = str(request.headers.get("X-Api-Envelope") or "").strip()
        if want not in {"1", "true", "yes", "on"}:
            return response

        if response.status_code == 204:
            return response

        if not (200 <= int(response.status_code) < 300):
            return response

        content_type = str(response.headers.get("content-type") or "").lower()
        if "application/json" not in content_type:
            return response

        reconstructed = False
        body_bytes: bytes | None = None
        background = getattr(response, "background", None)

        if isinstance(response, JSONResponse):
            body_bytes = bytes(response.body)
        else:
            raw = getattr(response, "body", None)
            if raw is None:
                body_bytes = None
            elif isinstance(raw, (bytes, bytearray)):
                body_bytes = bytes(raw)
            elif isinstance(raw, memoryview):
                body_bytes = raw.tobytes()
            else:
                body_bytes = None

            if body_bytes is None:
                iterator = getattr(response, "body_iterator", None)
                if iterator is not None:
                    reconstructed = True
                    buf = bytearray()
                    async for chunk in iterator:
                        if chunk is None:
                            continue
                        if isinstance(chunk, (bytes, bytearray)):
                            buf.extend(chunk)
                        elif isinstance(chunk, memoryview):
                            buf.extend(chunk.tobytes())
                        else:
                            try:
                                buf.extend(bytes(chunk))  # type: ignore[arg-type]
                            except Exception:
                                continue
                    body_bytes = bytes(buf)

        def _return_unmodified() -> Response:
            if not reconstructed:
                return response
            headers = dict(response.headers)
            _ = headers.pop("content-length", None)
            return Response(
                content=body_bytes or b"",
                status_code=int(response.status_code),
                headers=headers,
                media_type=getattr(response, "media_type", None),
                background=background,
            )

        if body_bytes is None:
            return response

        if not body_bytes:
            return _return_unmodified()

        try:
            payload: object = cast(object, json.loads(body_bytes))
        except Exception:
            return _return_unmodified()

        if isinstance(payload, dict) and ("ok" in payload) and ("data" in payload):
            return _return_unmodified()

        wrapped: dict[str, object] = {
            "ok": True,
            "data": payload,
            "ts": int(time.time()),
        }

        headers = dict(response.headers)
        _ = headers.pop("content-length", None)

        return JSONResponse(
            content=wrapped,
            status_code=int(response.status_code),
            headers=headers,
            background=background,
        )
