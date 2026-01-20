from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import cast

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


def _sanitize_data(data_obj: object) -> dict[str, object] | None:
    if not isinstance(data_obj, dict):
        return None

    safe_data: dict[str, object] = {}
    for k_obj, v_obj in cast(dict[object, object], data_obj).items():
        k = str(k_obj or "").strip()
        if not k:
            continue
        safe_data[k] = v_obj
    return safe_data


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
            event_obj = kwargs.get("event")
            if not isinstance(event_obj, str) or not event_obj.strip():
                return

            severity_obj = kwargs.get("severity")
            severity = str(severity_obj).strip() if severity_obj is not None else "error"
            if not severity:
                severity = "error"

            request_id_obj = kwargs.get("request_id")
            request_id = str(request_id_obj).strip() if request_id_obj is not None else None
            if request_id == "":
                request_id = None

            title_obj = kwargs.get("title")
            title = str(title_obj) if title_obj is not None else None

            message_obj = kwargs.get("message")
            message = str(message_obj) if message_obj is not None else None

            data = _sanitize_data(kwargs.get("data"))

            dedup_key_obj = kwargs.get("dedup_key")
            dedup_key = str(dedup_key_obj).strip() if dedup_key_obj is not None else None
            if dedup_key == "":
                dedup_key = None

            _ = asyncio.create_task(
                self.report(
                    event=str(event_obj).strip(),
                    severity=severity,
                    request_id=request_id,
                    title=title,
                    message=message,
                    data=data,
                    dedup_key=dedup_key,
                )
            )
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
            "data": _sanitize_data(data),
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
