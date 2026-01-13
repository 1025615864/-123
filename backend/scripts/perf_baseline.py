import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path

from typing import Any
from collections.abc import Callable

import httpx


@dataclass
class Stat:
    name: str
    count: int
    p50_ms: float
    p95_ms: float
    p99_ms: float


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0.0
    if p <= 0:
        return float(sorted_values[0])
    if p >= 100:
        return float(sorted_values[-1])

    k = (len(sorted_values) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_values) - 1)
    if f == c:
        return float(sorted_values[f])
    d0 = sorted_values[f] * (c - k)
    d1 = sorted_values[c] * (k - f)
    return float(d0 + d1)


def _to_stat(name: str, samples_s: list[float]) -> Stat:
    ms = [float(x) * 1000.0 for x in samples_s]
    ms.sort()
    return Stat(
        name=name,
        count=len(ms),
        p50_ms=round(_percentile(ms, 50), 2),
        p95_ms=round(_percentile(ms, 95), 2),
        p99_ms=round(_percentile(ms, 99), 2),
    )


def _sleep_seconds_for_429(headers: dict[str, str]) -> float:
    retry_after = str(headers.get("retry-after") or "").strip()
    if retry_after:
        try:
            return float(max(0, int(float(retry_after))))
        except Exception:
            pass

    reset = str(headers.get("x-ratelimit-reset") or "").strip()
    if reset:
        try:
            ts = float(reset)
            return max(0.0, ts - time.time())
        except Exception:
            pass

    return 2.0


def _sleep_backoff(i: int, headers: dict[str, str]) -> None:
    sleep_s = _sleep_seconds_for_429({k.lower(): str(v) for k, v in headers.items()})
    jitter = 0.05 * float(max(0, int(i)))
    time.sleep(max(0.2, float(sleep_s) + jitter))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8003")
    parser.add_argument("--runs", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument(
        "--output-json",
        default="",
        help="optional: write results to json file",
    )
    args = parser.parse_args()

    base_url = str(args.base_url).rstrip("/")
    runs = max(1, int(args.runs))
    warmup = max(0, int(args.warmup))

    timeout = httpx.Timeout(30.0)

    with httpx.Client(base_url=base_url, timeout=timeout) as client:
        # 1) login admin
        login_res = client.post(
            "/api/user/login",
            json={"username": "admin", "password": "admin123"},
        )
        login_res.raise_for_status()
        token = str(login_res.json().get("token", {}).get("access_token") or "").strip()
        if not token:
            raise RuntimeError("failed to obtain admin token")

        headers_admin = {
            "Authorization": f"Bearer {token}",
        }

        # 2) endpoints
        endpoints: list[tuple[str, Callable[[], httpx.Response]]] = []

        def run_ai_chat_stream() -> httpx.Response:
            return client.post(
                "/api/ai/chat/stream",
                headers={
                    **headers_admin,
                    "X-E2E-Mock-AI": "1",
                },
                json={"message": "perf baseline: hello", "session_id": None},
            )

        def run_documents_generate() -> httpx.Response:
            return client.post(
                "/api/documents/generate",
                headers=headers_admin,
                json={
                    "document_type": "complaint",
                    "case_type": "劳动纠纷",
                    "plaintiff_name": "原告A",
                    "defendant_name": "被告B",
                    "facts": "事实：用于性能基线。",
                    "claims": "诉求：用于性能基线。",
                    "evidence": "证据：用于性能基线。",
                },
            )

        def run_payment_channel_status() -> httpx.Response:
            return client.get(
                "/api/payment/admin/callback-events",
                headers=headers_admin,
                params={"page": 1, "page_size": 50},
            )

        def run_news_ingest_runs_admin() -> httpx.Response:
            return client.get(
                "/api/news/admin/ingest-runs",
                headers=headers_admin,
                params={"page": 1, "page_size": 20},
            )

        endpoints.append(("ai_chat_stream", run_ai_chat_stream))
        endpoints.append(("documents_generate", run_documents_generate))
        endpoints.append(("payment_admin_callback_events", run_payment_channel_status))
        endpoints.append(("news_admin_ingest_runs", run_news_ingest_runs_admin))

        results: dict[str, Any] = {
            "base_url": base_url,
            "runs": runs,
            "warmup": warmup,
            "stats": [],
            "raw_ms": {},
        }

        for name, fn in endpoints:
            # warmup (only count successful responses)
            warmed = 0
            warm_attempts = 0
            while warmed < warmup and warm_attempts < max(10, warmup * 5):
                warm_attempts += 1
                res = fn()
                if res.status_code == 429:
                    _sleep_backoff(warm_attempts, dict(res.headers))
                    continue
                res.raise_for_status()
                warmed += 1

            samples: list[float] = []
            attempts = 0
            while len(samples) < runs and attempts < runs * 20:
                attempts += 1
                t0 = time.perf_counter()
                res = fn()
                t1 = time.perf_counter()

                if res.status_code == 429:
                    _sleep_backoff(attempts, dict(res.headers))
                    continue

                res.raise_for_status()
                _ = res.content
                samples.append(t1 - t0)

            stat = _to_stat(name, samples)
            results["stats"].append(
                {
                    "name": stat.name,
                    "count": stat.count,
                    "p50_ms": stat.p50_ms,
                    "p95_ms": stat.p95_ms,
                    "p99_ms": stat.p99_ms,
                }
            )
            results["raw_ms"][name] = [round(s * 1000.0, 2) for s in samples]

        if str(args.output_json).strip():
            out = Path(str(args.output_json)).expanduser()
            if not out.is_absolute():
                out = (Path.cwd() / out).resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
