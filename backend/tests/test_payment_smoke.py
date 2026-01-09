import hashlib
import hmac
import importlib
from urllib.parse import parse_qsl, unquote, urlsplit

import pytest
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import cast


def _json_dict(res: Response) -> dict[str, object]:
    raw = cast(object, res.json())
    assert isinstance(raw, dict)
    return cast(dict[str, object], raw)


@pytest.mark.asyncio
async def test_payment_webhook_marks_order_paid_and_records_event(
    client: AsyncClient,
    test_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    payment_router = importlib.import_module("app.routers.payment")
    user_module = importlib.import_module("app.models.user")
    security_module = importlib.import_module("app.utils.security")
    User = getattr(user_module, "User")
    create_access_token = getattr(security_module, "create_access_token")
    hash_password = getattr(security_module, "hash_password")

    user = User(
        username="u_pay_smoke",
        email="u_pay_smoke@example.com",
        nickname="u_pay_smoke",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    user_token = create_access_token({"sub": str(user.id)})

    create_res = await client.post(
        "/api/payment/orders",
        json={
            "order_type": "service",
            "amount": 1.23,
            "title": "Smoke Test",
            "description": "Smoke Test",
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_res.status_code == 200
    create_payload = _json_dict(create_res)
    order_no = str(create_payload.get("order_no") or "").strip()
    assert order_no

    secret = "test_payment_webhook_secret_123456"
    monkeypatch.setattr(payment_router.settings, "payment_webhook_secret", secret, raising=False)

    trade_no = "TRADE_SMOKE_001"
    amount_str = "1.23"
    sign_payload = f"{order_no}|{trade_no}|alipay|{amount_str}"
    signature = hmac.new(
        secret.encode("utf-8"),
        sign_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    webhook_res = await client.post(
        "/api/payment/webhook",
        json={
            "order_no": order_no,
            "trade_no": trade_no,
            "payment_method": "alipay",
            "amount": 1.23,
            "signature": signature,
        },
    )
    assert webhook_res.status_code == 200

    detail_res = await client.get(
        f"/api/payment/orders/{order_no}",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert detail_res.status_code == 200
    detail = _json_dict(detail_res)
    assert str(detail.get("status") or "").lower() == "paid"
    assert str(detail.get("payment_method") or "").lower() == "alipay"

    admin = User(
        username="u_pay_admin",
        email="u_pay_admin@example.com",
        nickname="u_pay_admin",
        hashed_password=hash_password("Test123456"),
        role="admin",
        is_active=True,
    )
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    admin_token = create_access_token({"sub": str(admin.id)})

    events_res = await client.get(
        "/api/payment/admin/callback-events",
        params={"order_no": order_no},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert events_res.status_code == 200
    payload = _json_dict(events_res)
    items_obj = payload.get("items")
    assert isinstance(items_obj, list)
    items = cast(list[object], items_obj)
    assert len(items) >= 1
    first_raw = items[0]
    assert isinstance(first_raw, dict)
    first = cast(dict[str, object], first_raw)
    assert str(first.get("order_no") or "") == order_no
    assert str(first.get("provider") or "").lower() == "alipay"
    assert bool(first.get("verified")) is True


@pytest.mark.asyncio
async def test_ikunpay_pay_url_return_url_contains_order_no(
    client: AsyncClient,
    test_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    payment_router = importlib.import_module("app.routers.payment")
    user_module = importlib.import_module("app.models.user")
    security_module = importlib.import_module("app.utils.security")
    User = getattr(user_module, "User")
    create_access_token = getattr(security_module, "create_access_token")
    hash_password = getattr(security_module, "hash_password")

    user = User(
        username="u_pay_ikun",
        email="u_pay_ikun@example.com",
        nickname="u_pay_ikun",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    user_token = create_access_token({"sub": str(user.id)})

    create_res = await client.post(
        "/api/payment/orders",
        json={
            "order_type": "service",
            "amount": 1.23,
            "title": "Ikun ReturnUrl",
            "description": "Ikun ReturnUrl",
        },
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert create_res.status_code == 200
    create_payload = _json_dict(create_res)
    order_no = str(create_payload.get("order_no") or "").strip()
    assert order_no

    monkeypatch.setattr(payment_router.settings, "ikunpay_pid", "PID_TEST", raising=False)
    monkeypatch.setattr(payment_router.settings, "ikunpay_key", "KEY_TEST", raising=False)
    monkeypatch.setattr(
        payment_router.settings,
        "ikunpay_notify_url",
        "https://example.com/notify",
        raising=False,
    )
    monkeypatch.setattr(
        payment_router.settings,
        "ikunpay_return_url",
        "https://example.com/payment/return?foo=bar",
        raising=False,
    )

    pay_res = await client.post(
        f"/api/payment/orders/{order_no}/pay",
        json={"payment_method": "ikunpay"},
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert pay_res.status_code == 200
    pay_payload = _json_dict(pay_res)
    pay_url = str(pay_payload.get("pay_url") or "").strip()
    assert pay_url

    pay_query = dict(parse_qsl(urlsplit(pay_url).query, keep_blank_values=True))
    return_url_encoded = str(pay_query.get("return_url") or "").strip()
    assert return_url_encoded
    return_url = unquote(return_url_encoded)
    assert f"order_no={order_no}" in return_url
    assert "foo=bar" in return_url
