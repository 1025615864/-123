from datetime import datetime, timedelta

import pytest

from app.main import app
from app.models.system import SystemConfig
from app.models.user import User
from app.utils.deps import require_admin


@pytest.mark.asyncio
async def test_payment_admin_wechat_platform_certs_list_empty_and_nonempty(client, test_session):
    admin = User(username="wx_admin", email="wx_admin@example.com", nickname="wx_admin", hashed_password="x", role="admin")
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin
    try:
        r0 = await client.get("/api/payment/admin/wechat/platform-certs")
        assert r0.status_code == 200
        d0 = r0.json()
        assert d0["total"] == 0
        assert d0["items"] == []

        from app.routers import payment_legacy as legacy

        raw = legacy.dump_platform_certs_json(
            [legacy.WeChatPayPlatformCert(serial_no="B", pem="pem", expire_time="x")]
        )
        test_session.add(SystemConfig(key="WECHATPAY_PLATFORM_CERTS_JSON", value=raw, category="payment"))
        await test_session.commit()

        r1 = await client.get("/api/payment/admin/wechat/platform-certs")
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1["total"] == 1
        assert d1["items"][0]["serial_no"] == "B"

    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_payment_admin_import_wechat_platform_certs_variants(client, test_session):
    admin = User(username="wx_admin2", email="wx_admin2@example.com", nickname="wx_admin2", hashed_password="x", role="admin")
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin

    try:
        bad1 = await client.post(
            "/api/payment/admin/wechat/platform-certs/import",
            json={"platform_certs_json": "{}", "merge": True},
        )
        assert bad1.status_code == 400

        bad2 = await client.post(
            "/api/payment/admin/wechat/platform-certs/import",
            json={},
        )
        assert bad2.status_code == 400

        from app.routers import payment_legacy as legacy

        incoming = legacy.dump_platform_certs_json(
            [legacy.WeChatPayPlatformCert(serial_no="SER1", pem="pem1", expire_time="x")]
        )
        ok1 = await client.post(
            "/api/payment/admin/wechat/platform-certs/import",
            json={"platform_certs_json": incoming, "merge": False},
        )
        assert ok1.status_code == 200
        assert ok1.json()["count"] == 1

        incoming2 = legacy.dump_platform_certs_json(
            [legacy.WeChatPayPlatformCert(serial_no="SER2", pem="pem2", expire_time="x")]
        )
        ok2 = await client.post(
            "/api/payment/admin/wechat/platform-certs/import",
            json={"platform_certs_json": incoming2, "merge": True},
        )
        assert ok2.status_code == 200
        assert ok2.json()["count"] == 2

        ok3 = await client.post(
            "/api/payment/admin/wechat/platform-certs/import",
            json={
                "cert_pem": "-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n",
                "serial_no": "SER3",
                "expire_time": "2026-01-01T00:00:00+00:00",
            },
        )
        assert ok3.status_code == 200
        assert ok3.json()["count"] == 3

        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography import x509
        from cryptography.x509.oid import NameOID

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "wx")])
        cert_obj = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow() - timedelta(days=1))
            .not_valid_after(datetime.utcnow() + timedelta(days=365))
            .sign(key, hashes.SHA256())
        )
        cert_pem = cert_obj.public_bytes(serialization.Encoding.PEM).decode("utf-8")

        ok4 = await client.post(
            "/api/payment/admin/wechat/platform-certs/import",
            json={"cert_pem": cert_pem},
        )
        assert ok4.status_code == 200
        assert ok4.json()["count"] == 4

    finally:
        app.dependency_overrides.pop(require_admin, None)


@pytest.mark.asyncio
async def test_payment_admin_refresh_wechat_platform_certs_branches(client, test_session, monkeypatch):
    admin = User(username="wx_admin3", email="wx_admin3@example.com", nickname="wx_admin3", hashed_password="x", role="admin")
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin

    try:
        import app.routers.payment_legacy as legacy

        monkeypatch.setattr(legacy.settings, "wechatpay_mch_id", "", raising=False)
        monkeypatch.setattr(legacy.settings, "wechatpay_mch_serial_no", "", raising=False)
        r0 = await client.post("/api/payment/admin/wechat/platform-certs/refresh")
        assert r0.status_code == 400

        monkeypatch.setattr(legacy.settings, "wechatpay_mch_id", "mch", raising=False)
        monkeypatch.setattr(legacy.settings, "wechatpay_mch_serial_no", "serial", raising=False)
        monkeypatch.setattr(legacy.settings, "wechatpay_private_key", "", raising=False)
        r1 = await client.post("/api/payment/admin/wechat/platform-certs/refresh")
        assert r1.status_code == 400

        monkeypatch.setattr(legacy.settings, "wechatpay_private_key", "key", raising=False)
        monkeypatch.setattr(legacy.settings, "wechatpay_api_v3_key", "", raising=False)
        r2 = await client.post("/api/payment/admin/wechat/platform-certs/refresh")
        assert r2.status_code == 400

        monkeypatch.setattr(legacy.settings, "wechatpay_api_v3_key", "0123456789abcdef0123456789abcdef", raising=False)

        import app.routers.payment as payment_router

        async def _fake_fetch(**_kwargs):
            return [legacy.WeChatPayPlatformCert(serial_no="SERX", pem="pem", expire_time="x")]

        monkeypatch.setattr(payment_router, "fetch_platform_certificates", _fake_fetch, raising=True)

        r3 = await client.post("/api/payment/admin/wechat/platform-certs/refresh")
        assert r3.status_code == 200
        assert r3.json()["count"] == 1

        cfg = await test_session.execute(
            SystemConfig.__table__.select().where(SystemConfig.key == "WECHATPAY_PLATFORM_CERTS_JSON")
        )
        row = cfg.first()
        assert row is not None

    finally:
        app.dependency_overrides.pop(require_admin, None)
