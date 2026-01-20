from types import SimpleNamespace

import pytest
from httpx import AsyncClient

from app.main import app
from app.models.payment import PaymentOrder
from app.models.user import User
from app.utils.deps import get_current_user
from app.utils.security import hash_password


@pytest.mark.asyncio
async def test_orders_pay_integration_invalid_method(client: AsyncClient) -> None:
    async def override_user():
        return SimpleNamespace(id=1)

    app.dependency_overrides[get_current_user] = override_user
    try:
        res = await client.post(
            "/api/payment/orders/ON/pay",
            json={"payment_method": "bad"},
        )
        assert res.status_code == 400
        assert str(res.json().get("detail"))
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_orders_pay_integration_order_not_found(client: AsyncClient) -> None:
    async def override_user():
        return SimpleNamespace(id=999)

    app.dependency_overrides[get_current_user] = override_user
    try:
        res = await client.post(
            "/api/payment/orders/ON/pay",
            json={"payment_method": "alipay"},
        )
        assert res.status_code == 404
        assert str(res.json().get("detail"))
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_orders_pay_integration_already_paid_returns_trade_no(
    client: AsyncClient,
    test_session,
) -> None:
    user = User(
        username="u_pay_int",
        email="u_pay_int@example.com",
        nickname="u_pay_int",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    order = PaymentOrder(
        order_no="ON",
        user_id=int(user.id),
        order_type="service",
        amount=1.0,
        actual_amount=1.0,
        status="paid",
        payment_method="alipay",
        trade_no="T123",
        title="t",
    )
    test_session.add(order)
    await test_session.commit()

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user
    try:
        res = await client.post(
            "/api/payment/orders/ON/pay",
            json={"payment_method": "alipay"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data.get("trade_no") == "T123"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
