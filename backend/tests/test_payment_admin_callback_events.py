from datetime import datetime, timezone

import pytest

from app.main import app
from app.models.payment import PaymentCallbackEvent
from app.models.user import User
from app.utils.deps import require_admin


@pytest.mark.asyncio
async def test_payment_admin_callback_events_list_filters(client, test_session):
    admin = User(username="cb_admin", email="cb_admin@example.com", nickname="cb_admin", hashed_password="x", role="admin")
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    e1 = PaymentCallbackEvent(
        provider="wechat",
        order_no="ord-aaa",
        trade_no="t-1",
        amount=1.0,
        verified=True,
        error_message=None,
        raw_payload="raw1",
        created_at=datetime(2026, 3, 1, 0, 0, 0),
    )
    e2 = PaymentCallbackEvent(
        provider="wechat",
        order_no="ord-bbb",
        trade_no="t-2",
        amount=2.0,
        verified=False,
        error_message="err",
        raw_payload="raw2",
        created_at=datetime(2026, 3, 2, 0, 0, 0),
    )
    e3 = PaymentCallbackEvent(
        provider="alipay",
        order_no="xyz",
        trade_no="t-3",
        amount=3.0,
        verified=True,
        error_message="",
        raw_payload="raw3",
        created_at=datetime(2026, 3, 3, 0, 0, 0),
    )
    test_session.add_all([e1, e2, e3])
    await test_session.commit()
    await test_session.refresh(e1)
    await test_session.refresh(e2)
    await test_session.refresh(e3)

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin
    try:
        resp = await client.get("/api/payment/admin/callback-events", params={"page": 1, "page_size": 50})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

        r_provider = await client.get(
            "/api/payment/admin/callback-events",
            params={"provider": "wechat", "page": 1, "page_size": 50},
        )
        assert r_provider.status_code == 200
        assert r_provider.json()["total"] == 2

        r_order_no = await client.get(
            "/api/payment/admin/callback-events",
            params={"order_no": "ord-aaa", "page": 1, "page_size": 50},
        )
        assert r_order_no.status_code == 200
        assert r_order_no.json()["total"] == 1

        r_trade_no = await client.get(
            "/api/payment/admin/callback-events",
            params={"trade_no": "t-2", "page": 1, "page_size": 50},
        )
        assert r_trade_no.status_code == 200
        assert r_trade_no.json()["total"] == 1

        r_verified = await client.get(
            "/api/payment/admin/callback-events",
            params={"verified": True, "page": 1, "page_size": 50},
        )
        assert r_verified.status_code == 200
        assert r_verified.json()["total"] == 2

        r_q = await client.get(
            "/api/payment/admin/callback-events",
            params={"q": "t-1", "page": 1, "page_size": 50},
        )
        assert r_q.status_code == 200
        assert r_q.json()["total"] == 1

        r_has_error = await client.get(
            "/api/payment/admin/callback-events",
            params={"has_error": True, "page": 1, "page_size": 50},
        )
        assert r_has_error.status_code == 200
        assert r_has_error.json()["total"] == 1

        r_no_error = await client.get(
            "/api/payment/admin/callback-events",
            params={"has_error": False, "page": 1, "page_size": 50},
        )
        assert r_no_error.status_code == 200
        assert r_no_error.json()["total"] == 2

        from_ts = int(datetime(2026, 3, 2, 0, 0, 0, tzinfo=timezone.utc).timestamp())
        r_from = await client.get(
            "/api/payment/admin/callback-events",
            params={"from_ts": from_ts, "page": 1, "page_size": 50},
        )
        assert r_from.status_code == 200
        assert r_from.json()["total"] == 2

        to_ts = int(datetime(2026, 3, 2, 0, 0, 0, tzinfo=timezone.utc).timestamp())
        r_to = await client.get(
            "/api/payment/admin/callback-events",
            params={"to_ts": to_ts, "page": 1, "page_size": 50},
        )
        assert r_to.status_code == 200
        assert r_to.json()["total"] == 2

        r_bad_ts = await client.get(
            "/api/payment/admin/callback-events",
            params={"from_ts": 999999999999999999, "to_ts": 999999999999999999, "page": 1, "page_size": 50},
        )
        assert r_bad_ts.status_code == 200
        assert r_bad_ts.json()["total"] == 3

    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_payment_admin_callback_events_stats_and_detail(client, test_session):
    admin = User(username="cb_admin2", email="cb_admin2@example.com", nickname="cb_admin2", hashed_password="x", role="admin")
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    e1 = PaymentCallbackEvent(provider="wechat", order_no="o1", trade_no="s1", amount=1.0, verified=True, error_message=None)
    e2 = PaymentCallbackEvent(provider="wechat", order_no="o2", trade_no="s2", amount=2.0, verified=False, error_message="bad")
    e3 = PaymentCallbackEvent(provider="alipay", order_no="o3", trade_no="s3", amount=3.0, verified=True, error_message=None)
    test_session.add_all([e1, e2, e3])
    await test_session.commit()
    await test_session.refresh(e1)
    await test_session.refresh(e2)
    await test_session.refresh(e3)

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin
    try:
        stats = await client.get("/api/payment/admin/callback-events/stats", params={"minutes": 60})
        assert stats.status_code == 200
        s = stats.json()
        assert s["all_total"] == 3
        assert s["all_verified"] == 2
        assert s["all_failed"] == 1

        stats2 = await client.get(
            "/api/payment/admin/callback-events/stats",
            params={"minutes": 60, "provider": "wechat"},
        )
        assert stats2.status_code == 200
        s2 = stats2.json()
        assert s2["provider"] == "wechat"
        assert s2["all_total"] == 2

        nf = await client.get("/api/payment/admin/callback-events/999999")
        assert nf.status_code == 404

        detail = await client.get(f"/api/payment/admin/callback-events/{e2.id}")
        assert detail.status_code == 200
        d = detail.json()
        assert d["id"] == e2.id
        assert d["provider"] == "wechat"
        assert "masked_payload" in d

    finally:
        app.dependency_overrides.pop(require_admin, None)
