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
    bucket_le_counts: dict[float, int] | None = None


@dataclass
class JobAgg:
    runs_total: int = 0
    successes_total: int = 0
    failures_total: int = 0
    last_run_ts: float | None = None
    last_duration_seconds: float | None = None
    last_success: bool | None = None


@dataclass(frozen=True)
class RateLimitKey:
    endpoint: str
    result: str  # "allowed" or "blocked"


@dataclass
class RateLimitAgg:
    count: int = 0


@dataclass(frozen=True)
class UserActionKey:
    action: str
    result: str  # "success" or "failure"
    status: str


@dataclass
class UserActionAgg:
    count: int = 0


@dataclass(frozen=True)
class PaymentPayKey:
    method: str
    result: str


@dataclass
class PaymentPayAgg:
    count: int = 0


@dataclass(frozen=True)
class PaymentCallbackKey:
    provider: str
    verified: str  # "true" / "false"
    result: str  # "ok" / "error"


@dataclass
class PaymentCallbackAgg:
    count: int = 0


@dataclass
class SqlSlowAgg:
    count: int = 0
    sum_seconds: float = 0.0
    bucket_le_counts: dict[float, int] | None = None
    max_seconds: float = 0.0


class PrometheusMetrics:
    def __init__(self) -> None:
        self.started_at: float = float(time.time())
        self._http: dict[HttpKey, HttpAgg] = {}
        self._jobs: dict[str, JobAgg] = {}
        self._rate_limits: dict[RateLimitKey, RateLimitAgg] = {}
        self._user_actions: dict[UserActionKey, UserActionAgg] = {}
        self._payment_pay: dict[PaymentPayKey, PaymentPayAgg] = {}
        self._payment_callbacks: dict[PaymentCallbackKey, PaymentCallbackAgg] = {}
        self._sql_slow: SqlSlowAgg = SqlSlowAgg()
        self._lock: threading.Lock = threading.Lock()

        self.http_duration_buckets: list[float] = [
            0.01,
            0.025,
            0.05,
            0.1,
            0.25,
            0.5,
            1.0,
            2.5,
            5.0,
            10.0,
        ]

        self.sql_slow_duration_buckets: list[float] = [
            0.05,
            0.1,
            0.2,
            0.5,
            1.0,
            2.5,
            5.0,
            10.0,
        ]


    def record_sql_slow_query(self, *, duration_seconds: float) -> None:
        d = max(0.0, float(duration_seconds))
        with self._lock:
            self._sql_slow.count = int(self._sql_slow.count) + 1
            self._sql_slow.sum_seconds = float(self._sql_slow.sum_seconds) + float(d)
            if float(d) > float(self._sql_slow.max_seconds or 0.0):
                self._sql_slow.max_seconds = float(d)

            if self._sql_slow.bucket_le_counts is None:
                self._sql_slow.bucket_le_counts = {}
            for le in self.sql_slow_duration_buckets:
                if d <= float(le):
                    self._sql_slow.bucket_le_counts[float(le)] = int(self._sql_slow.bucket_le_counts.get(float(le), 0)) + 1
            self._sql_slow.bucket_le_counts[float("inf")] = int(self._sql_slow.bucket_le_counts.get(float("inf"), 0)) + 1


    def snapshot_sql_slow(self) -> SqlSlowAgg:
        with self._lock:
            buckets: dict[float, int] | None = None
            if isinstance(self._sql_slow.bucket_le_counts, dict):
                buckets = {float(bk): int(bv) for bk, bv in self._sql_slow.bucket_le_counts.items()}
            return SqlSlowAgg(
                count=int(self._sql_slow.count),
                sum_seconds=float(self._sql_slow.sum_seconds),
                bucket_le_counts=buckets,
                max_seconds=float(self._sql_slow.max_seconds or 0.0),
            )

    def record_http(self, *, method: str, route: str, status_code: int, duration_seconds: float) -> None:
        m = str(method or "").upper() or "GET"
        r = str(route or "").strip() or "unknown"
        sc = int(status_code)
        st = str(sc)
        key = HttpKey(method=m, route=r, status=st)
        d = max(0.0, float(duration_seconds))
        with self._lock:
            agg = self._http.get(key)
            if agg is None:
                agg = HttpAgg()
                self._http[key] = agg
            agg.count = int(agg.count) + 1
            agg.sum_seconds = float(agg.sum_seconds) + float(d)

            if agg.bucket_le_counts is None:
                agg.bucket_le_counts = {}
            for le in self.http_duration_buckets:
                if d <= float(le):
                    agg.bucket_le_counts[float(le)] = int(agg.bucket_le_counts.get(float(le), 0)) + 1
            agg.bucket_le_counts[float("inf")] = int(agg.bucket_le_counts.get(float("inf"), 0)) + 1

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

    def record_rate_limit(self, *, endpoint: str, allowed: bool) -> None:
        """记录限流检查结果"""
        e = str(endpoint or "").strip() or "unknown"
        result = "allowed" if allowed else "blocked"
        key = RateLimitKey(endpoint=e, result=result)
        with self._lock:
            agg = self._rate_limits.get(key)
            if agg is None:
                agg = RateLimitAgg()
                self._rate_limits[key] = agg
            agg.count = int(agg.count) + 1

    def snapshot_rate_limits(self) -> dict[RateLimitKey, RateLimitAgg]:
        with self._lock:
            return {
                k: RateLimitAgg(count=int(v.count))
                for k, v in self._rate_limits.items()
            }

    def record_user_action(self, *, action: str, ok: bool, status_code: int) -> None:
        a = str(action or "").strip() or "action"
        result = "success" if ok else "failure"
        st = str(int(status_code))
        key = UserActionKey(action=a, result=result, status=st)
        with self._lock:
            agg = self._user_actions.get(key)
            if agg is None:
                agg = UserActionAgg()
                self._user_actions[key] = agg
            agg.count = int(agg.count) + 1

    def snapshot_user_actions(self) -> dict[UserActionKey, UserActionAgg]:
        with self._lock:
            return {
                k: UserActionAgg(count=int(v.count))
                for k, v in self._user_actions.items()
            }

    def record_payment_pay(self, *, method: str, result: str) -> None:
        m = str(method or "").strip().lower() or "unknown"
        r = str(result or "").strip().lower() or "unknown"
        key = PaymentPayKey(method=m, result=r)
        with self._lock:
            agg = self._payment_pay.get(key)
            if agg is None:
                agg = PaymentPayAgg()
                self._payment_pay[key] = agg
            agg.count = int(agg.count) + 1

    def snapshot_payment_pay(self) -> dict[PaymentPayKey, PaymentPayAgg]:
        with self._lock:
            return {
                k: PaymentPayAgg(count=int(v.count))
                for k, v in self._payment_pay.items()
            }

    def record_payment_callback(self, *, provider: str, verified: bool, ok: bool) -> None:
        p = str(provider or "").strip().lower() or "unknown"
        v = "true" if verified else "false"
        r = "ok" if ok else "error"
        key = PaymentCallbackKey(provider=p, verified=v, result=r)
        with self._lock:
            agg = self._payment_callbacks.get(key)
            if agg is None:
                agg = PaymentCallbackAgg()
                self._payment_callbacks[key] = agg
            agg.count = int(agg.count) + 1

    def snapshot_payment_callbacks(self) -> dict[PaymentCallbackKey, PaymentCallbackAgg]:
        with self._lock:
            return {
                k: PaymentCallbackAgg(count=int(v.count))
                for k, v in self._payment_callbacks.items()
            }

    def snapshot_http(self) -> dict[HttpKey, HttpAgg]:
        with self._lock:
            out: dict[HttpKey, HttpAgg] = {}
            for k, v in self._http.items():
                buckets: dict[float, int] | None = None
                if isinstance(v.bucket_le_counts, dict):
                    buckets = {float(bk): int(bv) for bk, bv in v.bucket_le_counts.items()}
                out[k] = HttpAgg(count=int(v.count), sum_seconds=float(v.sum_seconds), bucket_le_counts=buckets)
            return out

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
        rate_limit_snap = self.snapshot_rate_limits()
        user_action_snap = self.snapshot_user_actions()
        payment_pay_snap = self.snapshot_payment_pay()
        payment_cb_snap = self.snapshot_payment_callbacks()
        sql_slow_snap = self.snapshot_sql_slow()

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

        lines.append("# HELP baixing_http_request_duration_seconds_count Total requests observed for duration histogram")
        lines.append("# TYPE baixing_http_request_duration_seconds_count counter")
        for key in sorted(http_snap.keys(), key=lambda x: (x.route, x.method, x.status)):
            agg = http_snap[key]
            if int(agg.count) <= 0:
                continue
            lines.append(
                "baixing_http_request_duration_seconds_count"
                + f"{{method=\"{_prom_escape_label_value(key.method)}\","
                + f"route=\"{_prom_escape_label_value(key.route)}\","
                + f"status=\"{_prom_escape_label_value(key.status)}\"}} {int(agg.count)}"
            )

        lines.append("# HELP baixing_http_request_duration_seconds_bucket Request duration histogram buckets")
        lines.append("# TYPE baixing_http_request_duration_seconds_bucket counter")
        for key in sorted(http_snap.keys(), key=lambda x: (x.route, x.method, x.status)):
            agg = http_snap[key]
            buckets = agg.bucket_le_counts if isinstance(agg.bucket_le_counts, dict) else None
            if not buckets:
                continue

            for le in list(self.http_duration_buckets) + [float("inf")]:
                c = int(buckets.get(float(le), 0))
                le_label = "+Inf" if le == float("inf") else str(le)
                lines.append(
                    "baixing_http_request_duration_seconds_bucket"
                    + f"{{method=\"{_prom_escape_label_value(key.method)}\","
                    + f"route=\"{_prom_escape_label_value(key.route)}\","
                    + f"status=\"{_prom_escape_label_value(key.status)}\","
                    + f"le=\"{_prom_escape_label_value(le_label)}\"}} {c}"
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

        # Rate limit metrics
        lines.append("# HELP baixing_rate_limit_checks_total Total rate limit checks")
        lines.append("# TYPE baixing_rate_limit_checks_total counter")
        for key in sorted(rate_limit_snap.keys(), key=lambda x: (x.endpoint, x.result)):
            agg = rate_limit_snap[key]
            if int(agg.count) <= 0:
                continue
            lines.append(
                "baixing_rate_limit_checks_total"
                + f"{{endpoint=\"{_prom_escape_label_value(key.endpoint)}\","
                + f"result=\"{_prom_escape_label_value(key.result)}\"}} {int(agg.count)}"
            )

        # User action metrics
        lines.append("# HELP baixing_user_actions_total Total user actions")
        lines.append("# TYPE baixing_user_actions_total counter")
        for key in sorted(user_action_snap.keys(), key=lambda x: (x.action, x.result, x.status)):
            agg = user_action_snap[key]
            if int(agg.count) <= 0:
                continue
            lines.append(
                "baixing_user_actions_total"
                + f"{{action=\"{_prom_escape_label_value(key.action)}\","
                + f"result=\"{_prom_escape_label_value(key.result)}\","
                + f"status=\"{_prom_escape_label_value(key.status)}\"}} {int(agg.count)}"
            )

        # Payment metrics
        lines.append("# HELP baixing_payment_pay_requests_total Total payment pay requests")
        lines.append("# TYPE baixing_payment_pay_requests_total counter")
        for key in sorted(payment_pay_snap.keys(), key=lambda x: (x.method, x.result)):
            agg = payment_pay_snap[key]
            if int(agg.count) <= 0:
                continue
            lines.append(
                "baixing_payment_pay_requests_total"
                + f"{{method=\"{_prom_escape_label_value(key.method)}\","
                + f"result=\"{_prom_escape_label_value(key.result)}\"}} {int(agg.count)}"
            )

        lines.append("# HELP baixing_payment_callback_events_total Total payment callback events")
        lines.append("# TYPE baixing_payment_callback_events_total counter")
        for key in sorted(payment_cb_snap.keys(), key=lambda x: (x.provider, x.verified, x.result)):
            agg = payment_cb_snap[key]
            if int(agg.count) <= 0:
                continue
            lines.append(
                "baixing_payment_callback_events_total"
                + f"{{provider=\"{_prom_escape_label_value(key.provider)}\","
                + f"verified=\"{_prom_escape_label_value(key.verified)}\","
                + f"result=\"{_prom_escape_label_value(key.result)}\"}} {int(agg.count)}"
            )

        lines.append("# HELP baixing_sql_slow_queries_total Total SQL slow queries observed")
        lines.append("# TYPE baixing_sql_slow_queries_total counter")
        lines.append(f"baixing_sql_slow_queries_total {int(sql_slow_snap.count)}")

        lines.append("# HELP baixing_sql_slow_query_duration_seconds_sum Total seconds of SQL slow queries")
        lines.append("# TYPE baixing_sql_slow_query_duration_seconds_sum counter")
        lines.append(f"baixing_sql_slow_query_duration_seconds_sum {float(sql_slow_snap.sum_seconds)}")

        lines.append("# HELP baixing_sql_slow_query_duration_seconds_count Total slow queries observed for duration histogram")
        lines.append("# TYPE baixing_sql_slow_query_duration_seconds_count counter")
        lines.append(f"baixing_sql_slow_query_duration_seconds_count {int(sql_slow_snap.count)}")

        lines.append("# HELP baixing_sql_slow_query_duration_seconds_bucket SQL slow query duration histogram buckets")
        lines.append("# TYPE baixing_sql_slow_query_duration_seconds_bucket counter")
        buckets = sql_slow_snap.bucket_le_counts if isinstance(sql_slow_snap.bucket_le_counts, dict) else {}
        for le in list(self.sql_slow_duration_buckets) + [float("inf")]:
            c = int(buckets.get(float(le), 0))
            le_label = "+Inf" if le == float("inf") else str(le)
            lines.append(
                "baixing_sql_slow_query_duration_seconds_bucket"
                + f"{{le=\"{_prom_escape_label_value(le_label)}\"}} {c}"
            )

        lines.append("# HELP baixing_sql_slow_query_max_duration_seconds Max observed SQL slow query duration")
        lines.append("# TYPE baixing_sql_slow_query_max_duration_seconds gauge")
        lines.append(f"baixing_sql_slow_query_max_duration_seconds {float(sql_slow_snap.max_seconds)}")

        if extra_lines:
            lines.extend([str(x) for x in list(extra_lines) if str(x).strip()])

        return "\n".join(lines) + "\n"


prometheus_metrics = PrometheusMetrics()
