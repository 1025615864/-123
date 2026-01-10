from __future__ import annotations

import asyncio
import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)


def _bool_env(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return bool(default)
    return raw.lower() in {"1", "true", "yes", "y", "on"}


def _float_env(name: str, default: float) -> float:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return float(default)
    try:
        return float(raw)
    except Exception:
        return float(default)


class CriticalEventReporter:
    def __init__(self) -> None:
        self._lock: asyncio.Lock = asyncio.Lock()
        self._last_sent_at_by_key: dict[str, float] = {}

    def enabled(self) -> bool:
        return _bool_env("CRITICAL_EVENTS_ENABLED", False)

    def webhook_url(self) -> str:
        return str(os.getenv("CRITICAL_EVENTS_WEBHOOK_URL", "") or "").strip()

    def fire_and_forget(self, **kwargs: object) -> None:
        try:
            _ = asyncio.create_task(self.report(**kwargs))
        except Exception:
            return

    async def report(
        self,
        *,
        event: str,
        severity: str = "error",
        request_id: str | None = None,
        title: str | None = None,
        message: str | None = None,
        data: dict[str, object] | None = None,
        dedup_key: str | None = None,
    ) -> None:
        if not self.enabled():
            return

        url = self.webhook_url()
        if not url:
            return

        now = float(time.time())
        min_interval_seconds = _float_env("CRITICAL_EVENTS_MIN_INTERVAL_SECONDS", 30.0)

        key = str(dedup_key or "").strip()
        if not key:
            key = f"{str(event)}|{str(severity)}|{str(title or '')[:80]}|{str(message or '')[:120]}"

        async with self._lock:
            last = self._last_sent_at_by_key.get(key)
            if last is not None and (now - float(last)) < float(min_interval_seconds):
                return
            self._last_sent_at_by_key[key] = now

        payload: dict[str, object] = {
            "ts": now,
            "event": str(event),
            "severity": str(severity),
            "request_id": (str(request_id) if request_id else None),
            "title": (str(title) if title else None),
            "message": (str(message) if message else None),
            "env": str(os.getenv("APP_ENV") or os.getenv("ENV") or os.getenv("ENVIRONMENT") or ""),
            "service": "backend",
            "data": (data if isinstance(data, dict) else None),
        }

        headers: dict[str, str] = {"Content-Type": "application/json"}
        bearer = str(os.getenv("CRITICAL_EVENTS_WEBHOOK_BEARER", "") or "").strip()
        if bearer:
            headers["Authorization"] = f"Bearer {bearer}"

        header_name = str(os.getenv("CRITICAL_EVENTS_WEBHOOK_HEADER_NAME", "") or "").strip()
        header_value = str(os.getenv("CRITICAL_EVENTS_WEBHOOK_HEADER_VALUE", "") or "").strip()
        if header_name and header_value:
            headers[header_name] = header_value

        timeout_seconds = _float_env("CRITICAL_EVENTS_TIMEOUT_SECONDS", 3.0)

        try:
            async with httpx.AsyncClient(timeout=float(timeout_seconds)) as client:
                _ = await client.post(url, json=payload, headers=headers)
        except Exception:
            logger.exception("critical_event_report_failed event=%s", str(event))


critical_event_reporter = CriticalEventReporter()
