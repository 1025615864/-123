import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_alipay_notify_concurrent_idempotent(
    client: AsyncClient,
    test_session: AsyncSession,
    monkeypatch,
):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from sqlalchemy import select, func

    from app.models.user import User
    from app.models.payment import PaymentOrder, PaymentCallbackEvent
    from app.routers import payment as payment_router
    from app.utils.security import hash_password, create_access_token

    user = User(
        username="u_alipay_notify_concurrent",
        email="u_alipay_notify_concurrent@example.com",
        nickname="u_alipay_notify_concurrent",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    token = create_access_token({"sub": str(user.id)})

    create_res = await client.post(
        "/api/payment/orders",
        json={"order_type": "service", "amount": 10.0, "title": "svc"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert create_res.status_code == 200
    order_no = str(create_res.json()["order_no"])

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")

    monkeypatch.setattr(payment_router.settings, "alipay_public_key", public_pem, raising=False)
    monkeypatch.setattr(payment_router.settings, "alipay_app_id", "test_app", raising=False)

    trade_no = "ALI_T_CONCURRENT_1"
    params = {
        "app_id": "test_app",
        "out_trade_no": order_no,
        "trade_no": trade_no,
        "total_amount": "10.00",
        "trade_status": "TRADE_SUCCESS",
        "sign_type": "RSA2",
        "charset": "utf-8",
    }
    params["sign"] = payment_router._alipay_sign_rsa2(params, private_pem)

    async def _post_notify():
        return await client.post("/api/payment/alipay/notify", data=params)

    r1, r2 = await asyncio.gather(_post_notify(), _post_notify())

    assert any(r.status_code == 200 and r.text.strip() == "success" for r in (r1, r2))
    assert set([r1.status_code, r2.status_code]).issubset({200, 503})

    order_db_res = await test_session.execute(
        select(PaymentOrder).where(PaymentOrder.order_no == order_no)
    )
    order_db = order_db_res.scalar_one_or_none()
    assert order_db is not None
    assert str(order_db.status) == "paid"
    assert str(order_db.trade_no or "") == trade_no

    evt_count_res = await test_session.execute(
        select(func.count(PaymentCallbackEvent.id)).where(
            PaymentCallbackEvent.provider == "alipay",
            PaymentCallbackEvent.trade_no == trade_no,
        )
    )
    assert int(evt_count_res.scalar() or 0) == 1
