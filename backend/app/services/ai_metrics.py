import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AiRecentError:
    ts: float
    request_id: str
    endpoint: str
    error_code: str
    status_code: int | None
    message: str | None

    def to_dict(self) -> dict[str, object]:
        dt = datetime.fromtimestamp(float(self.ts))
        return {
            "ts": float(self.ts),
            "at": dt.isoformat(),
            "request_id": str(self.request_id),
            "endpoint": str(self.endpoint),
            "error_code": str(self.error_code),
            "status_code": int(self.status_code) if self.status_code is not None else None,
            "message": str(self.message) if self.message is not None else None,
        }


class AiMetrics:
    def __init__(self) -> None:
        self.started_at: float = float(time.time())
        self.chat_requests_total: int = 0
        self.chat_stream_requests_total: int = 0
        self.errors_total: int = 0
        self._error_code_counts: dict[str, int] = {}
        self._endpoint_error_counts: dict[str, int] = {}
        self._recent_errors: deque[AiRecentError] = deque(maxlen=50)
        self._lock: threading.Lock = threading.Lock()

    def record_request(self, endpoint: str) -> None:
        ep = str(endpoint)
        with self._lock:
            if ep == "chat":
                self.chat_requests_total += 1
            elif ep == "chat_stream":
                self.chat_stream_requests_total += 1

    def record_error(
        self,
        *,
        endpoint: str,
        request_id: str,
        error_code: str,
        status_code: int | None = None,
        message: str | None = None,
    ) -> None:
        with self._lock:
            self.errors_total += 1
            ec = str(error_code)
            ep = str(endpoint)
            self._error_code_counts[ec] = int(self._error_code_counts.get(ec, 0)) + 1
            self._endpoint_error_counts[ep] = int(self._endpoint_error_counts.get(ep, 0)) + 1
            self._recent_errors.append(
                AiRecentError(
                    ts=float(time.time()),
                    request_id=str(request_id),
                    endpoint=str(endpoint),
                    error_code=str(error_code),
                    status_code=(int(status_code) if status_code is not None else None),
                    message=(str(message) if message is not None else None),
                )
            )

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            top_error_codes = sorted(
                (
                    {"error_code": k, "count": int(v)}
                    for k, v in self._error_code_counts.items()
                    if str(k).strip()
                ),
                key=lambda row: int(row.get("count", 0)),
                reverse=True,
            )
            top_endpoints = sorted(
                (
                    {"endpoint": k, "count": int(v)}
                    for k, v in self._endpoint_error_counts.items()
                    if str(k).strip()
                ),
                key=lambda row: int(row.get("count", 0)),
                reverse=True,
            )
            return {
                "started_at": float(self.started_at),
                "started_at_iso": datetime.fromtimestamp(float(self.started_at)).isoformat(),
                "chat_requests_total": int(self.chat_requests_total),
                "chat_stream_requests_total": int(self.chat_stream_requests_total),
                "errors_total": int(self.errors_total),
                "recent_errors": [e.to_dict() for e in list(self._recent_errors)],
                "top_error_codes": list(top_error_codes)[:10],
                "top_endpoints": list(top_endpoints)[:10],
            }


ai_metrics = AiMetrics()
