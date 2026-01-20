from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.sql.dml import Update

from app.main import app
from app.models.payment import BalanceTransaction, PaymentOrder, PaymentStatus, UserBalance
from app.models.user import User
from app.utils.deps import require_admin


@pytest.mark.asyncio
async def test_payment_admin_orders_list_filters(client, test_session):
    admin = User(username="pay_admin", email="pay_admin@example.com", nickname="pay_admin", hashed_password="x", role="admin")
    u1 = User(username="pay_u1", email="pay_u1@example.com", nickname="pay_u1", hashed_password="x")
    u2 = User(username="pay_u2", email="pay_u2@example.com", nickname="pay_u2", hashed_password="x")
    test_session.add_all([admin, u1, u2])
    await test_session.commit()
    await test_session.refresh(admin)
    await test_session.refresh(u1)
    await test_session.refresh(u2)

    o1 = PaymentOrder(
        order_no="ord-1",
        user_id=u1.id,
        order_type="recharge",
        amount=10.0,
        actual_amount=10.0,
        status=PaymentStatus.PENDING.value,
        payment_method=None,
        title="t1",
    )
    o2 = PaymentOrder(
        order_no="ord-2",
        user_id=u2.id,
        order_type="vip",
        amount=20.0,
        actual_amount=20.0,
        status=PaymentStatus.PAID.value,
        payment_method="wechat",
        title="t2",
        trade_no="trade-2",
        paid_at=datetime.now(timezone.utc),
    )
    test_session.add_all([o1, o2])
    await test_session.commit()

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin
    try:
        resp = await client.get("/api/payment/admin/orders", params={"page": 1, "page_size": 20})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

        resp2 = await client.get(
            "/api/payment/admin/orders",
            params={"status_filter": PaymentStatus.PAID.value, "page": 1, "page_size": 20},
        )
        assert resp2.status_code == 200
        data2 = resp2.json()
        assert data2["total"] == 1
        assert data2["items"][0]["order_no"] == "ord-2"

        resp3 = await client.get(
            "/api/payment/admin/orders",
            params={"user_id": u1.id, "page": 1, "page_size": 20},
        )
        assert resp3.status_code == 200
        data3 = resp3.json()
        assert data3["total"] == 1
        assert data3["items"][0]["order_no"] == "ord-1"

    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_payment_admin_refund_order_update_rowcount_zero_rollbacks(client, test_session, monkeypatch):
    admin = User(username="pay_admin4", email="pay_admin4@example.com", nickname="pay_admin4", hashed_password="x", role="admin")
    u1 = User(username="pay_u5", email="pay_u5@example.com", nickname="pay_u5", hashed_password="x")
    test_session.add_all([admin, u1])
    await test_session.commit()
    await test_session.refresh(admin)
    await test_session.refresh(u1)

    o_paid = PaymentOrder(
        order_no="ord-paid-rowcount0",
        user_id=u1.id,
        order_type="vip",
        amount=10.0,
        actual_amount=10.0,
        status=PaymentStatus.PAID.value,
        payment_method="wechat",
        title="x",
        trade_no="trade-x",
        paid_at=datetime.now(timezone.utc),
    )
    test_session.add(o_paid)
    await test_session.commit()

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin
    try:
        orig_execute = test_session.execute

        async def patched_execute(statement, *args, **kwargs):
            if isinstance(statement, Update) and getattr(getattr(statement, "table", None), "name", None) == "payment_orders":
                return SimpleNamespace(rowcount=0)
            return await orig_execute(statement, *args, **kwargs)

        monkeypatch.setattr(test_session, "execute", patched_execute, raising=True)

        res = await client.post("/api/payment/admin/refund/ord-paid-rowcount0")
        assert res.status_code == 400
        assert res.json().get("detail") == "订单状态异常"

    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_payment_admin_mark_paid_order_update_rowcount_zero_rollbacks(client, test_session, monkeypatch):
    admin = User(username="pay_admin5", email="pay_admin5@example.com", nickname="pay_admin5", hashed_password="x", role="admin")
    u1 = User(username="pay_u6", email="pay_u6@example.com", nickname="pay_u6", hashed_password="x")
    test_session.add_all([admin, u1])
    await test_session.commit()
    await test_session.refresh(admin)
    await test_session.refresh(u1)

    o_pending = PaymentOrder(
        order_no="ord-pending-rowcount0",
        user_id=u1.id,
        order_type="recharge",
        amount=7.0,
        actual_amount=7.0,
        status=PaymentStatus.PENDING.value,
        payment_method=None,
        title="x",
    )
    test_session.add(o_pending)
    await test_session.commit()

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin
    try:
        orig_execute = test_session.execute

        async def patched_execute(statement, *args, **kwargs):
            if isinstance(statement, Update) and getattr(getattr(statement, "table", None), "name", None) == "payment_orders":
                return SimpleNamespace(rowcount=0)
            return await orig_execute(statement, *args, **kwargs)

        monkeypatch.setattr(test_session, "execute", patched_execute, raising=True)

        res = await client.post(
            "/api/payment/admin/orders/ord-pending-rowcount0/mark-paid",
            json={"payment_method": "wechat"},
        )
        assert res.status_code == 400
        assert res.json().get("detail") == "订单状态异常"

    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_payment_admin_mark_paid_rollback_on_unexpected_exception(client, test_session, monkeypatch):
    admin = User(username="pay_admin6", email="pay_admin6@example.com", nickname="pay_admin6", hashed_password="x", role="admin")
    u1 = User(username="pay_u7", email="pay_u7@example.com", nickname="pay_u7", hashed_password="x")
    test_session.add_all([admin, u1])
    await test_session.commit()
    await test_session.refresh(admin)
    await test_session.refresh(u1)

    o_pending = PaymentOrder(
        order_no="ord-pending-ex",
        user_id=u1.id,
        order_type="recharge",
        amount=7.0,
        actual_amount=7.0,
        status=PaymentStatus.PENDING.value,
        payment_method=None,
        title="x",
    )
    test_session.add(o_pending)
    await test_session.commit()

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin
    try:
        orig_execute = test_session.execute

        async def patched_execute(statement, *args, **kwargs):
            if isinstance(statement, Update) and getattr(getattr(statement, "table", None), "name", None) == "user_balances":
                raise RuntimeError("boom")
            return await orig_execute(statement, *args, **kwargs)

        monkeypatch.setattr(test_session, "execute", patched_execute, raising=True)

        with pytest.raises(RuntimeError):
            await client.post(
                "/api/payment/admin/orders/ord-pending-ex/mark-paid",
                json={"payment_method": "wechat"},
            )

    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_payment_admin_refund_branches(client, test_session):
    admin = User(username="pay_admin2", email="pay_admin2@example.com", nickname="pay_admin2", hashed_password="x", role="admin")
    u1 = User(username="pay_u3", email="pay_u3@example.com", nickname="pay_u3", hashed_password="x")
    test_session.add_all([admin, u1])
    await test_session.commit()
    await test_session.refresh(admin)
    await test_session.refresh(u1)

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin
    try:
        # not found
        r0 = await client.post("/api/payment/admin/refund/not-exist")
        assert r0.status_code == 404

        # already refunded
        o_refunded = PaymentOrder(
            order_no="ord-refunded",
            user_id=u1.id,
            order_type="vip",
            amount=9.9,
            actual_amount=9.9,
            status=PaymentStatus.REFUNDED.value,
            payment_method="wechat",
            title="x",
        )
        test_session.add(o_refunded)
        await test_session.commit()
        r1 = await client.post("/api/payment/admin/refund/ord-refunded")
        assert r1.status_code == 200
        assert r1.json()["message"] == "退款成功"

        # not paid
        o_pending = PaymentOrder(
            order_no="ord-pending",
            user_id=u1.id,
            order_type="vip",
            amount=9.9,
            actual_amount=9.9,
            status=PaymentStatus.PENDING.value,
            payment_method=None,
            title="x",
        )
        test_session.add(o_pending)
        await test_session.commit()
        r2 = await client.post("/api/payment/admin/refund/ord-pending")
        assert r2.status_code == 400

        # paid + balance -> creates balance transaction
        o_paid = PaymentOrder(
            order_no="ord-paid",
            user_id=u1.id,
            order_type="vip",
            amount=10.0,
            actual_amount=10.0,
            status=PaymentStatus.PAID.value,
            payment_method="balance",
            title="x",
            trade_no="trade-x",
            paid_at=datetime.now(timezone.utc),
        )
        bal = UserBalance(user_id=u1.id, balance=0.0, frozen=0.0, total_recharged=0.0, total_consumed=0.0)
        test_session.add_all([o_paid, bal])
        await test_session.commit()

        r3 = await client.post("/api/payment/admin/refund/ord-paid")
        assert r3.status_code == 200
        assert r3.json()["message"] == "退款成功"

        refreshed_order = await test_session.get(PaymentOrder, o_paid.id)
        assert refreshed_order is not None
        assert refreshed_order.status == PaymentStatus.REFUNDED

        bal_res = await test_session.execute(select(UserBalance).where(UserBalance.user_id == u1.id))
        refreshed_bal = bal_res.scalar_one()
        assert float(refreshed_bal.balance) == pytest.approx(10.0)

        tx = (
            await test_session.execute(
                BalanceTransaction.__table__.select().where(BalanceTransaction.order_id == o_paid.id)
            )
        ).first()
        assert tx is not None

    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_payment_admin_mark_paid_branches(client, test_session):
    admin = User(username="pay_admin3", email="pay_admin3@example.com", nickname="pay_admin3", hashed_password="x", role="admin")
    u1 = User(username="pay_u4", email="pay_u4@example.com", nickname="pay_u4", hashed_password="x")
    test_session.add_all([admin, u1])
    await test_session.commit()
    await test_session.refresh(admin)
    await test_session.refresh(u1)

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin
    try:
        # invalid payment method
        bad = await client.post(
            "/api/payment/admin/orders/xxx/mark-paid",
            json={"payment_method": "balance"},
        )
        assert bad.status_code == 400

        # not found
        nf = await client.post(
            "/api/payment/admin/orders/not-exist/mark-paid",
            json={"payment_method": "wechat"},
        )
        assert nf.status_code == 404

        # already paid
        o_paid = PaymentOrder(
            order_no="ord-paid2",
            user_id=u1.id,
            order_type="recharge",
            amount=5.0,
            actual_amount=5.0,
            status=PaymentStatus.PAID.value,
            payment_method="wechat",
            title="x",
        )
        test_session.add(o_paid)
        await test_session.commit()
        ap = await client.post(
            "/api/payment/admin/orders/ord-paid2/mark-paid",
            json={"payment_method": "wechat"},
        )
        assert ap.status_code == 200

        # status not pending
        o_cancelled = PaymentOrder(
            order_no="ord-cancelled",
            user_id=u1.id,
            order_type="recharge",
            amount=5.0,
            actual_amount=5.0,
            status=PaymentStatus.CANCELLED.value,
            payment_method=None,
            title="x",
        )
        test_session.add(o_cancelled)
        await test_session.commit()
        st = await client.post(
            "/api/payment/admin/orders/ord-cancelled/mark-paid",
            json={"payment_method": "wechat"},
        )
        assert st.status_code == 400

        # order type not recharge
        o_vip = PaymentOrder(
            order_no="ord-vip",
            user_id=u1.id,
            order_type="vip",
            amount=5.0,
            actual_amount=5.0,
            status=PaymentStatus.PENDING.value,
            payment_method=None,
            title="x",
        )
        test_session.add(o_vip)
        await test_session.commit()
        ot = await client.post(
            "/api/payment/admin/orders/ord-vip/mark-paid",
            json={"payment_method": "wechat"},
        )
        assert ot.status_code == 400

        # success
        o_pending = PaymentOrder(
            order_no="ord-pending2",
            user_id=u1.id,
            order_type="recharge",
            amount=7.0,
            actual_amount=7.0,
            status=PaymentStatus.PENDING.value,
            payment_method=None,
            title="x",
        )
        test_session.add(o_pending)
        await test_session.commit()

        ok = await client.post(
            "/api/payment/admin/orders/ord-pending2/mark-paid",
            json={"payment_method": "wechat"},
        )
        assert ok.status_code == 200
        assert ok.json()["message"] == "标记成功"

        refreshed_order = await test_session.get(PaymentOrder, o_pending.id)
        assert refreshed_order is not None
        assert refreshed_order.status == PaymentStatus.PAID
        assert refreshed_order.paid_at is not None
        assert refreshed_order.payment_method == "wechat"
        assert refreshed_order.trade_no is not None
        assert str(refreshed_order.trade_no).startswith("ADM")

        bal = (
            await test_session.execute(
                UserBalance.__table__.select().where(UserBalance.user_id == u1.id)
            )
        ).first()
        assert bal is not None

    finally:
        app.dependency_overrides.pop(require_admin, None)
