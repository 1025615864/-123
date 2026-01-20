import os
from datetime import datetime, timedelta, timezone

import pytest

from app.main import app
from app.models.payment import PaymentOrder, PaymentStatus
from app.models.system import SystemConfig
from app.models.user import User
from app.utils.deps import require_admin


@pytest.mark.asyncio
async def test_payment_admin_channel_status_updated_at_and_refresh_flag(client, test_session, monkeypatch):
    admin = User(username="pay_cfg_admin", email="pay_cfg_admin@example.com", nickname="pay_cfg_admin", hashed_password="x", role="admin")
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin

    try:
        import app.routers.payment_legacy as legacy

        monkeypatch.setattr(legacy.settings, "frontend_base_url", "https://front.example.com/", raising=False)

        monkeypatch.setattr(legacy.settings, "alipay_app_id", "app", raising=False)
        monkeypatch.setattr(legacy.settings, "alipay_public_key", "pub", raising=False)
        monkeypatch.setattr(legacy.settings, "alipay_private_key", "priv", raising=False)
        monkeypatch.setattr(legacy.settings, "alipay_notify_url", "https://example.com/notify", raising=False)

        monkeypatch.setattr(legacy.settings, "wechatpay_mch_id", "mch", raising=False)
        monkeypatch.setattr(legacy.settings, "wechatpay_mch_serial_no", "serial", raising=False)
        monkeypatch.setattr(legacy.settings, "wechatpay_private_key", "key", raising=False)
        monkeypatch.setattr(legacy.settings, "wechatpay_api_v3_key", "0123456789abcdef0123456789abcdef", raising=False)

        monkeypatch.setattr(legacy.settings, "ikunpay_pid", "pid", raising=False)
        monkeypatch.setattr(legacy.settings, "ikunpay_key", "key", raising=False)
        monkeypatch.setattr(legacy.settings, "ikunpay_notify_url", "https://example.com/notify2", raising=False)

        monkeypatch.setattr(legacy.settings, "payment_webhook_secret", "whsec_test", raising=False)

        monkeypatch.setenv("WECHATPAY_CERT_REFRESH_ENABLED", "1")

        cfg_json_ok = '{"updated_at":"123","certs":[{"serial_no":"SER","pem":"pem","expire_time":"x"}]}'
        test_session.add(SystemConfig(key="WECHATPAY_PLATFORM_CERTS_JSON", value=cfg_json_ok, category="payment"))
        await test_session.commit()

        res = await client.get("/api/payment/admin/channel-status")
        assert res.status_code == 200
        data = res.json()

        assert data["alipay_configured"] is True
        assert data["wechatpay_configured"] is True
        assert data["ikunpay_configured"] is True
        assert data["payment_webhook_secret_configured"] is True
        assert data["wechatpay_platform_certs_cached"] is True
        assert data["wechatpay_platform_certs_total"] == 1
        assert data["wechatpay_platform_certs_updated_at"] == 123
        assert data["wechatpay_cert_refresh_enabled"] is True

        assert data["details"]["alipay"]["public_key_check"] is not None
        assert data["details"]["alipay"]["private_key_check"] is not None
        assert data["details"]["alipay"]["effective_return_url"].endswith("/payment/return")

        cfg_obj_bad = {"updated_at": "bad", "certs": [{"serial_no": "SER", "pem": "pem", "expire_time": "x"}]}
        cfg_json_bad = __import__("json").dumps(cfg_obj_bad, ensure_ascii=False, separators=(",", ":"))
        row = await test_session.execute(
            SystemConfig.__table__.update().where(SystemConfig.key == "WECHATPAY_PLATFORM_CERTS_JSON").values(value=cfg_json_bad)
        )
        _ = row
        await test_session.commit()

        res2 = await client.get("/api/payment/admin/channel-status")
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["wechatpay_platform_certs_total"] == 1
        assert data2["wechatpay_platform_certs_updated_at"] is None

    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_payment_admin_env_updates_and_empty_returns_400(client, test_session, monkeypatch):
    admin = User(username="pay_env_admin", email="pay_env_admin@example.com", nickname="pay_env_admin", hashed_password="x", role="admin")
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin

    try:
        r0 = await client.post("/api/payment/admin/env", json={"items": []})
        assert r0.status_code == 400

        r0b = await client.post("/api/payment/admin/env", json={"items": [{"key": "   ", "value": "x"}]})
        assert r0b.status_code == 400

        monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET", "old")

        res = await client.post(
            "/api/payment/admin/env",
            json={
                "items": [
                    {"key": "ALIPAY_APP_ID", "value": "test_app"},
                    {"key": "PAYMENT_WEBHOOK_SECRET", "value": ""},
                ]
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["message"] == "OK"
        assert data["env_file"] == "in-memory"
        assert sorted(data["updated_keys"]) == ["ALIPAY_APP_ID", "PAYMENT_WEBHOOK_SECRET"]
        assert "channel_status" in data

        assert os.environ.get("ALIPAY_APP_ID") == "test_app"
        assert os.environ.get("PAYMENT_WEBHOOK_SECRET") is None

    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_payment_admin_stats_revenue_and_today(client, test_session, monkeypatch):
    admin = User(username="pay_stats_admin", email="pay_stats_admin@example.com", nickname="pay_stats_admin", hashed_password="x", role="admin")
    user = User(username="pay_stats_user", email="pay_stats_user@example.com", nickname="pay_stats_user", hashed_password="x")
    test_session.add_all([admin, user])
    await test_session.commit()
    await test_session.refresh(admin)
    await test_session.refresh(user)

    fixed_now = datetime(2026, 4, 1, 12, 0, 0, tzinfo=timezone.utc)

    class _DT:
        @staticmethod
        def now(tz=None):
            _ = tz
            return fixed_now

    import app.routers.payment.admin_stats as stats_router

    monkeypatch.setattr(stats_router, "datetime", _DT, raising=True)

    o_pending = PaymentOrder(
        order_no="s-1",
        user_id=user.id,
        order_type="vip",
        amount=1.0,
        actual_amount=1.0,
        status=PaymentStatus.PENDING.value,
        payment_method=None,
        title="x",
    )
    o_paid_today = PaymentOrder(
        order_no="s-2",
        user_id=user.id,
        order_type="vip",
        amount=10.0,
        actual_amount=10.0,
        status=PaymentStatus.PAID.value,
        payment_method="wechat",
        title="x",
        paid_at=fixed_now,
        actual_amount_cents=None,
    )
    o_paid_old = PaymentOrder(
        order_no="s-3",
        user_id=user.id,
        order_type="vip",
        amount=25.0,
        actual_amount=25.0,
        status=PaymentStatus.PAID.value,
        payment_method="wechat",
        title="x",
        paid_at=fixed_now - timedelta(days=1),
        actual_amount_cents=2500,
    )
    test_session.add_all([o_pending, o_paid_today, o_paid_old])
    await test_session.commit()

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin
    try:
        res = await client.get("/api/payment/admin/stats")
        assert res.status_code == 200
        data = res.json()

        assert data["total_orders"] == 3
        assert data["paid_orders"] == 2
        assert data["total_revenue"] == 35.0
        assert data["today_revenue"] == 10.0
        assert data["conversion_rate"] == 66.7

    finally:
        app.dependency_overrides.pop(require_admin, None)
