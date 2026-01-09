import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import cast


def _load_env_file(env_file: str) -> dict[str, str]:
    path = Path(env_file)
    if not path.is_absolute():
        root = Path(__file__).resolve().parents[1]
        path = root / env_file
    if not path.exists():
        return {}

    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def _http_json(
    method: str,
    url: str,
    data: dict[str, object] | None = None,
    token: str | None = None,
) -> dict[str, object]:
    headers: dict[str, str] = {"Accept": "application/json"}
    body: bytes | None = None

    if data is not None:
        body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"

    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode("utf-8")
        if not raw:
            return {}
        parsed: object = cast(object, json.loads(raw))
        if isinstance(parsed, dict):
            return cast(dict[str, object], parsed)
        return {}


def _ikunpay_sign_md5(params: dict[str, str], key: str) -> str:
    items: list[tuple[str, str]] = []
    for k, v in params.items():
        if k in {"sign", "sign_type"}:
            continue
        s = str(v)
        if s == "":
            continue
        items.append((k, s))
    items.sort(key=lambda x: x[0])
    sign_content = "&".join([f"{k}={v}" for k, v in items])
    return hashlib.md5((sign_content + str(key)).encode("utf-8")).hexdigest().lower()


def main() -> int:
    backend_base = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
    api_base = f"{backend_base}/api"

    env_file = os.getenv("ENV_FILE", "env.local")
    env = _load_env_file(env_file)

    pid = (os.getenv("IKUNPAY_PID") or env.get("IKUNPAY_PID") or "").strip()
    key = (os.getenv("IKUNPAY_KEY") or env.get("IKUNPAY_KEY") or "").strip()
    notify_url = (os.getenv("IKUNPAY_NOTIFY_URL") or env.get("IKUNPAY_NOTIFY_URL") or "").strip()

    if not pid or not key or not notify_url:
        raise SystemExit(
            json.dumps(
                {
                    "ok": False,
                    "error": "missing_ikunpay_env",
                    "pid_set": bool(pid),
                    "key_set": bool(key),
                    "notify_url_set": bool(notify_url),
                    "env_file": env_file,
                },
                ensure_ascii=False,
            )
        )

    user_login = _http_json(
        "POST",
        f"{api_base}/user/login",
        {"username": os.getenv("USER_USERNAME", "user1"), "password": os.getenv("USER_PASSWORD", "user123")},
    )
    user_token: str | None = None
    user_token_obj = user_login.get("token")
    if isinstance(user_token_obj, dict):
        access_obj = cast(dict[str, object], user_token_obj).get("access_token")
        if isinstance(access_obj, str):
            user_token = access_obj

    admin_login = _http_json(
        "POST",
        f"{api_base}/user/login",
        {"username": os.getenv("ADMIN_USERNAME", "admin"), "password": os.getenv("ADMIN_PASSWORD", "admin123")},
    )
    admin_token: str | None = None
    admin_token_obj = admin_login.get("token")
    if isinstance(admin_token_obj, dict):
        access_obj2 = cast(dict[str, object], admin_token_obj).get("access_token")
        if isinstance(access_obj2, str):
            admin_token = access_obj2

    if not user_token or not admin_token:
        raise SystemExit(json.dumps({"ok": False, "error": "login_failed"}, ensure_ascii=False))

    order = _http_json(
        "POST",
        f"{api_base}/payment/orders",
        {
            "order_type": "recharge",
            "amount": float(os.getenv("ORDER_AMOUNT", "1")),
            "title": os.getenv("ORDER_TITLE", "测试充值(自动回调)"),
            "description": os.getenv("ORDER_DESC", "ikunpay smoke test"),
        },
        token=user_token,
    )

    order_no_obj = order.get("order_no")
    order_no = str(order_no_obj or "").strip()
    if not order_no:
        raise SystemExit(json.dumps({"ok": False, "error": "create_order_failed", "resp": order}, ensure_ascii=False))

    pay = _http_json(
        "POST",
        f"{api_base}/payment/orders/{urllib.parse.quote(order_no)}/pay",
        {"payment_method": "ikunpay"},
        token=user_token,
    )

    trade_no = f"IKTEST{int(time.time())}"
    money = f"{float(os.getenv('ORDER_AMOUNT', '1')):.2f}"

    notify_params: dict[str, str] = {
        "pid": pid,
        "trade_no": trade_no,
        "out_trade_no": order_no,
        "money": money,
        "trade_status": "TRADE_SUCCESS",
        "timestamp": str(int(time.time())),
        "sign_type": "MD5",
    }
    notify_params["sign"] = _ikunpay_sign_md5(notify_params, key)

    notify_full_url = notify_url
    joiner = "&" if ("?" in notify_full_url) else "?"
    notify_full_url = notify_full_url + joiner + urllib.parse.urlencode(notify_params)

    notify_http_code: int | None = None
    notify_body: str | None = None
    notify_error: str | None = None

    try:
        with urllib.request.urlopen(notify_full_url, timeout=30) as resp:
            notify_http_code = int(resp.getcode())
            notify_body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        notify_http_code = int(getattr(e, "code", 0) or 0)
        notify_body = e.read().decode("utf-8") if hasattr(e, "read") else None
        notify_error = f"HTTPError:{e}"
    except Exception as e:
        notify_error = f"{type(e).__name__}:{e}"

    order_after = _http_json(
        "GET",
        f"{api_base}/payment/orders/{urllib.parse.quote(order_no)}",
        token=user_token,
    )

    events = _http_json(
        "GET",
        f"{api_base}/payment/admin/callback-events?"
        + urllib.parse.urlencode(
            {
                "provider": "ikunpay",
                "order_no": order_no,
                "page": "1",
                "page_size": "5",
            }
        ),
        token=admin_token,
    )

    latest = None
    items_obj = events.get("items")
    items: list[object] = []
    if isinstance(items_obj, list):
        items = cast(list[object], items_obj)
    if items:
        first = items[0]
        if isinstance(first, dict):
            latest = cast(dict[str, object], first)

    status_obj = order_after.get("status")
    is_paid = str(status_obj or "") == "paid"
    verified = False
    if isinstance(latest, dict):
        verified = bool(latest.get("verified")) is True
    ok = bool(is_paid and verified)

    print(
        json.dumps(
            {
                "ok": bool(ok),
                "order_no": order_no,
                "pay_url": pay.get("pay_url"),
                "notify_url": notify_url,
                "notify_http_code": notify_http_code,
                "notify_body": notify_body,
                "notify_error": notify_error,
                "order_status": order_after.get("status"),
                "order_trade_no": order_after.get("trade_no"),
                "callback_total": events.get("total"),
                "callback_latest": latest,
            },
            ensure_ascii=False,
        )
    )

    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
