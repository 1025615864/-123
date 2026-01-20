from datetime import datetime, timezone

import pytest

from app.main import app
from app.models.payment import PaymentCallbackEvent, PaymentOrder, PaymentStatus
from app.models.user import User
from app.utils.deps import require_admin


@pytest.mark.asyncio
async def test_admin_reconcile_order_not_found_returns_404(client, test_session):
    admin = User(username="admin1", email="admin1@example.com", nickname="admin1", hashed_password="x", role="admin")
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin
    try:
        resp = await client.get("/api/payment/admin/reconcile/not-exist")
        assert resp.status_code == 404
        assert resp.json()["detail"] == "订单不存在"
    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_admin_reconcile_order_diagnosis_branches(client, test_session):
    admin = User(username="admin2", email="admin2@example.com", nickname="admin2", hashed_password="x", role="admin")
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin
    try:
        now = datetime.now(timezone.utc)

        async def run_case(order_no: str, *, order_status: str, events: list[PaymentCallbackEvent], expected: str):
            order = PaymentOrder(
                order_no=order_no,
                user_id=admin.id,
                order_type="vip",
                amount=10.0,
                actual_amount=10.0,
                status=order_status,
                payment_method="wechat",
                title="t",
                trade_no="trade-1",
                paid_at=now,
            )
            test_session.add(order)
            for e in events:
                test_session.add(e)
            await test_session.commit()

            resp = await client.get(f"/api/payment/admin/reconcile/{order_no}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["order_no"] == order_no
            assert data["diagnosis"] == expected
            assert data["details"]["expected_amount"] == 10.0
            return data

        await run_case(
            "o-no-callback",
            order_status=PaymentStatus.PENDING.value,
            events=[],
            expected="no_callback",
        )

        await run_case(
            "o-amount-mismatch",
            order_status=PaymentStatus.PENDING.value,
            events=[
                PaymentCallbackEvent(
                    provider="wechat",
                    order_no="o-amount-mismatch",
                    trade_no="tm-1",
                    amount=10.0,
                    verified=False,
                    error_message="金额不一致",
                )
            ],
            expected="amount_mismatch",
        )

        await run_case(
            "o-decrypt-failed",
            order_status=PaymentStatus.PENDING.value,
            events=[
                PaymentCallbackEvent(
                    provider="wechat",
                    order_no="o-decrypt-failed",
                    trade_no="td-1",
                    amount=10.0,
                    verified=False,
                    error_message="解密失败",
                )
            ],
            expected="decrypt_failed",
        )

        await run_case(
            "o-signature-failed",
            order_status=PaymentStatus.PENDING.value,
            events=[
                PaymentCallbackEvent(
                    provider="wechat",
                    order_no="o-signature-failed",
                    trade_no="ts-1",
                    amount=10.0,
                    verified=False,
                    error_message="验签失败",
                )
            ],
            expected="signature_failed",
        )

        await run_case(
            "o-paid-without-success",
            order_status=PaymentStatus.PAID.value,
            events=[
                PaymentCallbackEvent(
                    provider="wechat",
                    order_no="o-paid-without-success",
                    trade_no="tp-1",
                    amount=10.0,
                    verified=True,
                    error_message="其它错误",
                )
            ],
            expected="paid_without_success_callback",
        )

        await run_case(
            "o-success-but-not-paid",
            order_status=PaymentStatus.PENDING.value,
            events=[
                PaymentCallbackEvent(
                    provider="wechat",
                    order_no="o-success-but-not-paid",
                    trade_no="tn-1",
                    amount=10.0,
                    verified=True,
                    error_message=None,
                )
            ],
            expected="success_callback_but_order_not_paid",
        )

    finally:
        app.dependency_overrides.pop(require_admin, None)
