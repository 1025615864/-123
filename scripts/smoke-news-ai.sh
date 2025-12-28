#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-}" # e.g. https://yourdomain.com
ADMIN_TOKEN="${ADMIN_TOKEN:-}"
POLL_SECONDS="${POLL_SECONDS:-30}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-1}"
STRICT="${STRICT:-0}"

if [ -z "$BASE_URL" ]; then
  echo "BASE_URL is required" >&2
  exit 2
fi
if [ -z "$ADMIN_TOKEN" ]; then
  echo "ADMIN_TOKEN is required" >&2
  exit 2
fi

BASE_URL="${BASE_URL%/}"
AUTH_HEADER="Authorization: Bearer ${ADMIN_TOKEN}"

step() {
  echo "[$1] $2"
}

step "1/7" "Health check..."
curl -fsS "${BASE_URL}/health" >/dev/null
curl -fsS "${BASE_URL}/api/health" >/dev/null

step "2/7" "News AI status (admin)..."
curl -fsS -H "$AUTH_HEADER" "${BASE_URL}/api/system/news-ai/status" >/dev/null

step "3/7" "Create a test news (admin)..."
NOW_MS=$(date +%s%3N 2>/dev/null || python - <<'PY'
import time
print(int(time.time()*1000))
PY
)
TITLE="SMOKE-NEWS-AI-${NOW_MS}"

NEWS_ID=$(curl -fsS -H "$AUTH_HEADER" -H "Content-Type: application/json" \
  -d "{\"title\":\"${TITLE}\",\"category\":\"general\",\"summary\":null,\"cover_image\":null,\"source\":\"SMOKE\",\"author\":\"SMOKE\",\"content\":\"Smoke test content ${NOW_MS}\",\"is_top\":false,\"is_published\":true,\"review_status\":\"approved\"}" \
  "${BASE_URL}/api/news" | python - <<'PY'
import json,sys
print(int(json.load(sys.stdin)["id"]))
PY
)

cleanup() {
  step "7/7" "Cleanup: delete test news..."
  curl -fsS -H "$AUTH_HEADER" -X DELETE "${BASE_URL}/api/news/${NEWS_ID}" >/dev/null || true
}
trap cleanup EXIT

step "4/7" "Trigger AI rerun..."
curl -fsS -H "$AUTH_HEADER" -X POST "${BASE_URL}/api/news/admin/${NEWS_ID}/ai/rerun" >/dev/null

step "5/7" "Poll admin detail until ai_annotation.processed_at is set..."
OK=0
START=$(date +%s)
while true; do
  sleep "$INTERVAL_SECONDS"

  DETAIL=$(curl -fsS -H "$AUTH_HEADER" "${BASE_URL}/api/news/admin/${NEWS_ID}")

  python - <<'PY' "$DETAIL" "$STRICT" && OK=1 && break || true
import json,sys
j=json.loads(sys.argv[1])
strict = str(sys.argv[2]).strip() in {"1","true","yes","on"}
ann=j.get("ai_annotation") or None
if not ann:
  raise SystemExit(1)
pa=ann.get("processed_at")
if not pa:
  raise SystemExit(1)
if strict:
  hl=ann.get("highlights")
  kw=ann.get("keywords")
  if not isinstance(hl, list) or len(hl) <= 0:
    raise SystemExit(1)
  if not isinstance(kw, list) or len(kw) <= 0:
    raise SystemExit(1)
PY

  NOW=$(date +%s)
  ELAPSED=$((NOW-START))
  if [ "$ELAPSED" -ge "$POLL_SECONDS" ]; then
    break
  fi

done

if [ "$OK" -ne 1 ]; then
  echo "AI annotation not ready in time (POLL_SECONDS=$POLL_SECONDS, STRICT=$STRICT)" >&2
  exit 1
fi

step "6/7" "OK: AI rerun succeeded."

echo "DONE"
