from datetime import datetime

import pytest

from app.main import app
from app.models.payment import BalanceTransaction, PaymentOrder, PaymentStatus, UserBalance
from app.models.system import SystemConfig
from app.models.user import User
from app.utils.deps import get_current_user


@pytest.mark.asyncio
async def test_payment_orders_list_and_status_filter(client, test_session):
    u1 = User(username="pay_u_list", email="pay_u_list@example.com", nickname="pay_u_list", hashed_password="x")
    u2 = User(username="pay_u_list2", email="pay_u_list2@example.com", nickname="pay_u_list2", hashed_password="x")
    test_session.add_all([u1, u2])
    await test_session.commit()
    await test_session.refresh(u1)
    await test_session.refresh(u2)

    o1 = PaymentOrder(
        order_no="u-ord-1",
        user_id=u1.id,
        order_type="vip",
        amount=10.0,
        actual_amount=10.0,
        status=PaymentStatus.PENDING.value,
        payment_method=None,
        title="t1",
        created_at=datetime(2026, 1, 1, 0, 0, 1),
    )
    o2 = PaymentOrder(
        order_no="u-ord-2",
        user_id=u1.id,
        order_type="vip",
        amount=20.0,
        actual_amount=20.0,
        status=PaymentStatus.PAID.value,
        payment_method="wechat",
        title="t2",
        created_at=datetime(2026, 1, 1, 0, 0, 2),
    )
    o3 = PaymentOrder(
        order_no="u-ord-3",
        user_id=u1.id,
        order_type="vip",
        amount=30.0,
        actual_amount=30.0,
        status=PaymentStatus.PAID.value,
        payment_method="alipay",
        title="t3",
        created_at=datetime(2026, 1, 1, 0, 0, 3),
    )
    other = PaymentOrder(
        order_no="u-ord-x",
        user_id=u2.id,
        order_type="vip",
        amount=40.0,
        actual_amount=40.0,
        status=PaymentStatus.PAID.value,
        payment_method="wechat",
        title="tx",
        created_at=datetime(2026, 1, 1, 0, 0, 4),
    )

    test_session.add_all([o1, o2, o3, other])
    await test_session.commit()

    async def override_user():
        return u1

    app.dependency_overrides[get_current_user] = override_user
    try:
        resp = await client.get("/api/payment/orders", params={"page": 1, "page_size": 2})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["items"][0]["order_no"] == "u-ord-3"

        resp2 = await client.get(
            "/api/payment/orders",
            params={"status_filter": PaymentStatus.PAID.value, "page": 1, "page_size": 10},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["total"] == 2
        assert {x["order_no"] for x in data2["items"]} == {"u-ord-2", "u-ord-3"}

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_payment_cancel_order_branches(client, test_session):
    u1 = User(username="pay_u_cancel", email="pay_u_cancel@example.com", nickname="pay_u_cancel", hashed_password="x")
    u2 = User(username="pay_u_cancel2", email="pay_u_cancel2@example.com", nickname="pay_u_cancel2", hashed_password="x")
    test_session.add_all([u1, u2])
    await test_session.commit()
    await test_session.refresh(u1)
    await test_session.refresh(u2)

    o_pending = PaymentOrder(
        order_no="c-1",
        user_id=u1.id,
        order_type="vip",
        amount=10.0,
        actual_amount=10.0,
        status=PaymentStatus.PENDING.value,
        payment_method=None,
        title="t",
    )
    o_paid = PaymentOrder(
        order_no="c-2",
        user_id=u1.id,
        order_type="vip",
        amount=10.0,
        actual_amount=10.0,
        status=PaymentStatus.PAID.value,
        payment_method="wechat",
        title="t",
    )
    o_other = PaymentOrder(
        order_no="c-3",
        user_id=u2.id,
        order_type="vip",
        amount=10.0,
        actual_amount=10.0,
        status=PaymentStatus.PENDING.value,
        payment_method=None,
        title="t",
    )
    test_session.add_all([o_pending, o_paid, o_other])
    await test_session.commit()
    await test_session.refresh(o_pending)
    await test_session.refresh(o_paid)
    await test_session.refresh(o_other)

    async def override_user():
        return u1

    app.dependency_overrides[get_current_user] = override_user
    try:
        ok = await client.post("/api/payment/orders/c-1/cancel")
        assert ok.status_code == 200
        assert ok.json()["message"] == "订单已取消"
        refreshed = await test_session.get(PaymentOrder, o_pending.id)
        assert refreshed is not None
        assert refreshed.status == PaymentStatus.CANCELLED

        bad = await client.post("/api/payment/orders/c-2/cancel")
        assert bad.status_code == 400

        nf = await client.post("/api/payment/orders/c-3/cancel")
        assert nf.status_code == 404

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_payment_pricing_uses_system_config(client, test_session):
    test_session.add(SystemConfig(key="VIP_DEFAULT_DAYS", value="15", category="payment"))
    test_session.add(SystemConfig(key="VIP_DEFAULT_PRICE", value="19.9", category="payment"))
    test_session.add(SystemConfig(key="LIGHT_CONSULT_REVIEW_PRICE", value="9.9", category="payment"))
    test_session.add(SystemConfig(key="AI_CHAT_PACK_OPTIONS_JSON", value='{"50":49.0,"10":12.0}', category="payment"))
    test_session.add(
        SystemConfig(key="DOCUMENT_GENERATE_PACK_OPTIONS_JSON", value='{"100":79.0}', category="payment")
    )
    await test_session.commit()

    resp = await client.get("/api/payment/pricing")
    assert resp.status_code == 200
    data = resp.json()

    assert data["vip"]["days"] == 15
    assert data["vip"]["price"] == 19.9
    assert data["services"]["light_consult_review"]["price"] == 9.9

    ai_list = data["packs"]["ai_chat"]
    assert [x["count"] for x in ai_list] == [10, 50]

    doc_list = data["packs"]["document_generate"]
    assert [x["count"] for x in doc_list] == [100]


@pytest.mark.asyncio
async def test_payment_balance_and_transactions(client, test_session):
    u1 = User(username="pay_u_bal", email="pay_u_bal@example.com", nickname="pay_u_bal", hashed_password="x")
    u2 = User(username="pay_u_bal2", email="pay_u_bal2@example.com", nickname="pay_u_bal2", hashed_password="x")
    test_session.add_all([u1, u2])
    await test_session.commit()
    await test_session.refresh(u1)
    await test_session.refresh(u2)

    async def override_user():
        return u1

    app.dependency_overrides[get_current_user] = override_user
    try:
        bal = await client.get("/api/payment/balance")
        assert bal.status_code == 200
        b = bal.json()
        assert b["balance"] == 0.0
        assert b["frozen"] == 0.0

        created = (
            await test_session.execute(
                UserBalance.__table__.select().where(UserBalance.user_id == u1.id)
            )
        ).first()
        assert created is not None

        t1 = BalanceTransaction(
            user_id=u1.id,
            order_id=None,
            type="recharge",
            amount=10.0,
            balance_before=0.0,
            balance_after=10.0,
            description="r",
            created_at=datetime(2026, 1, 1, 0, 0, 1),
        )
        t2 = BalanceTransaction(
            user_id=u1.id,
            order_id=None,
            type="consume",
            amount=-1.0,
            balance_before=10.0,
            balance_after=9.0,
            description="c",
            created_at=datetime(2026, 1, 1, 0, 0, 2),
        )
        t_other = BalanceTransaction(
            user_id=u2.id,
            order_id=None,
            type="recharge",
            amount=1.0,
            balance_before=0.0,
            balance_after=1.0,
            description="x",
            created_at=datetime(2026, 1, 1, 0, 0, 3),
        )
        test_session.add_all([t1, t2, t_other])
        await test_session.commit()
        await test_session.refresh(t1)
        await test_session.refresh(t2)

        lst = await client.get("/api/payment/balance/transactions", params={"page": 1, "page_size": 1})
        assert lst.status_code == 200
        d = lst.json()
        assert d["total"] == 2
        assert len(d["items"]) == 1
        assert d["items"][0]["id"] == t2.id

        lst2 = await client.get("/api/payment/balance/transactions", params={"page": 2, "page_size": 1})
        assert lst2.status_code == 200
        d2 = lst2.json()
        assert d2["total"] == 2
        assert len(d2["items"]) == 1
        assert d2["items"][0]["id"] == t1.id

    finally:
        app.dependency_overrides.pop(get_current_user, None)
