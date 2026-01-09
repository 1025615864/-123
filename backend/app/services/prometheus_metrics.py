from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from collections.abc import Iterable


def _prom_escape_label_value(value: str) -> str:
    s = str(value)
    s = s.replace("\\", "\\\\")
    s = s.replace('"', "\\\"")
    s = s.replace("\n", "\\n")
    return s


@dataclass(frozen=True)
class HttpKey:
    method: str
    route: str
    status: str


@dataclass
class HttpAgg:
    count: int = 0
    sum_seconds: float = 0.0


@dataclass
class JobAgg:
    runs_total: int = 0
    successes_total: int = 0
    failures_total: int = 0
    last_run_ts: float | None = None
    last_duration_seconds: float | None = None
    last_success: bool | None = None


class PrometheusMetrics:
    def __init__(self) -> None:
        self.started_at: float = float(time.time())
        self._http: dict[HttpKey, HttpAgg] = {}
        self._jobs: dict[str, JobAgg] = {}
        self._lock: threading.Lock = threading.Lock()

    def record_http(self, *, method: str, route: str, status_code: int, duration_seconds: float) -> None:
        m = str(method or "").upper() or "GET"
        r = str(route or "").strip() or "unknown"
        sc = int(status_code)
        st = str(sc)
        key = HttpKey(method=m, route=r, status=st)
        with self._lock:
            agg = self._http.get(key)
            if agg is None:
                agg = HttpAgg()
                self._http[key] = agg
            agg.count = int(agg.count) + 1
            agg.sum_seconds = float(agg.sum_seconds) + float(duration_seconds)

    def record_job(self, *, name: str, ok: bool, duration_seconds: float) -> None:
        n = str(name or "").strip() or "job"
        with self._lock:
            agg = self._jobs.get(n)
            if agg is None:
                agg = JobAgg()
                self._jobs[n] = agg
            agg.runs_total = int(agg.runs_total) + 1
            if ok:
                agg.successes_total = int(agg.successes_total) + 1
            else:
                agg.failures_total = int(agg.failures_total) + 1
            agg.last_run_ts = float(time.time())
            agg.last_duration_seconds = float(duration_seconds)
            agg.last_success = bool(ok)

    def snapshot_http(self) -> dict[HttpKey, HttpAgg]:
        with self._lock:
            return {k: HttpAgg(count=int(v.count), sum_seconds=float(v.sum_seconds)) for k, v in self._http.items()}

    def snapshot_jobs(self) -> dict[str, JobAgg]:
        with self._lock:
            return {
                str(k): JobAgg(
                    runs_total=int(v.runs_total),
                    successes_total=int(v.successes_total),
                    failures_total=int(v.failures_total),
                    last_run_ts=(float(v.last_run_ts) if v.last_run_ts is not None else None),
                    last_duration_seconds=(
                        float(v.last_duration_seconds) if v.last_duration_seconds is not None else None
                    ),
                    last_success=(bool(v.last_success) if v.last_success is not None else None),
                )
                for k, v in self._jobs.items()
            }

    def render_prometheus(self, *, extra_lines: Iterable[str] | None = None) -> str:
        http_snap = self.snapshot_http()
        jobs_snap = self.snapshot_jobs()

        lines: list[str] = []
        lines.append("# HELP baixing_process_started_at_seconds Unix timestamp when process started")
        lines.append("# TYPE baixing_process_started_at_seconds gauge")
        lines.append(f"baixing_process_started_at_seconds {float(self.started_at)}")

        lines.append("# HELP baixing_http_requests_total Total HTTP requests")
        lines.append("# TYPE baixing_http_requests_total counter")
        for key in sorted(http_snap.keys(), key=lambda x: (x.route, x.method, x.status)):
            agg = http_snap[key]
            if int(agg.count) <= 0:
                continue
            lines.append(
                "baixing_http_requests_total"
                + f"{{method=\"{_prom_escape_label_value(key.method)}\","
                + f"route=\"{_prom_escape_label_value(key.route)}\","
                + f"status=\"{_prom_escape_label_value(key.status)}\"}} {int(agg.count)}"
            )

        lines.append("# HELP baixing_http_request_duration_seconds_sum Total seconds spent handling requests")
        lines.append("# TYPE baixing_http_request_duration_seconds_sum counter")
        for key in sorted(http_snap.keys(), key=lambda x: (x.route, x.method, x.status)):
            agg = http_snap[key]
            if float(agg.sum_seconds) <= 0:
                continue
            lines.append(
                "baixing_http_request_duration_seconds_sum"
                + f"{{method=\"{_prom_escape_label_value(key.method)}\","
                + f"route=\"{_prom_escape_label_value(key.route)}\","
                + f"status=\"{_prom_escape_label_value(key.status)}\"}} {float(agg.sum_seconds)}"
            )

        lines.append("# HELP baixing_job_runs_total Total scheduled job runs")
        lines.append("# TYPE baixing_job_runs_total counter")
        for name in sorted(jobs_snap.keys()):
            agg = jobs_snap[name]
            if int(agg.runs_total) > 0:
                lines.append(
                    f"baixing_job_runs_total{{job=\"{_prom_escape_label_value(name)}\"}} {int(agg.runs_total)}"
                )

        lines.append("# HELP baixing_job_success_total Total scheduled job successes")
        lines.append("# TYPE baixing_job_success_total counter")
        for name in sorted(jobs_snap.keys()):
            agg = jobs_snap[name]
            if int(agg.successes_total) > 0:
                lines.append(
                    f"baixing_job_success_total{{job=\"{_prom_escape_label_value(name)}\"}} {int(agg.successes_total)}"
                )

        lines.append("# HELP baixing_job_failure_total Total scheduled job failures")
        lines.append("# TYPE baixing_job_failure_total counter")
        for name in sorted(jobs_snap.keys()):
            agg = jobs_snap[name]
            if int(agg.failures_total) > 0:
                lines.append(
                    f"baixing_job_failure_total{{job=\"{_prom_escape_label_value(name)}\"}} {int(agg.failures_total)}"
                )

        lines.append("# HELP baixing_job_last_run_timestamp_seconds Last scheduled job run unix timestamp")
        lines.append("# TYPE baixing_job_last_run_timestamp_seconds gauge")
        for name in sorted(jobs_snap.keys()):
            agg = jobs_snap[name]
            if agg.last_run_ts is None:
                continue
            lines.append(
                f"baixing_job_last_run_timestamp_seconds{{job=\"{_prom_escape_label_value(name)}\"}} {float(agg.last_run_ts)}"
            )

        lines.append("# HELP baixing_job_last_duration_seconds Last scheduled job duration seconds")
        lines.append("# TYPE baixing_job_last_duration_seconds gauge")
        for name in sorted(jobs_snap.keys()):
            agg = jobs_snap[name]
            if agg.last_duration_seconds is None:
                continue
            lines.append(
                f"baixing_job_last_duration_seconds{{job=\"{_prom_escape_label_value(name)}\"}} {float(agg.last_duration_seconds)}"
            )

        lines.append("# HELP baixing_job_last_success Whether last job run succeeded")
        lines.append("# TYPE baixing_job_last_success gauge")
        for name in sorted(jobs_snap.keys()):
            agg = jobs_snap[name]
            if agg.last_success is None:
                continue
            lines.append(
                f"baixing_job_last_success{{job=\"{_prom_escape_label_value(name)}\"}} {1 if agg.last_success else 0}"
            )

        if extra_lines:
            lines.extend([str(x) for x in list(extra_lines) if str(x).strip()])

        return "\n".join(lines) + "\n"


prometheus_metrics = PrometheusMetrics()
