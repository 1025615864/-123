import importlib
from datetime import datetime, timedelta

import pytest

import app.services.email_service as es


class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        _ = tz
        return datetime(2026, 1, 19, 12, 0, 0)

    @classmethod
    def fromisoformat(cls, date_string: str):
        return datetime.fromisoformat(date_string)


@pytest.fixture(autouse=True)
def _reset_state():
    es._reset_tokens.clear()
    es._email_verification_tokens.clear()


def test_configure_and_is_configured():
    svc = es.EmailService()
    assert svc.is_configured is False

    svc.configure(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_user="u",
        smtp_password="p",
        from_email="from@example.com",
    )

    assert svc.is_configured is True
    assert svc.smtp_host == "smtp.example.com"
    assert svc.smtp_port == 587
    assert svc.smtp_user == "u"
    assert svc.smtp_password == "p"
    assert svc.from_email == "from@example.com"


@pytest.mark.asyncio
async def test_generate_reset_token_cache_success(monkeypatch):
    svc = es.EmailService()

    monkeypatch.setattr(es, "datetime", FixedDatetime, raising=True)
    monkeypatch.setattr(es.secrets, "token_urlsafe", lambda _n: "tok", raising=True)

    called = {}

    async def fake_set_json(key, value, expire):
        called["key"] = key
        called["value"] = value
        called["expire"] = expire
        return True

    monkeypatch.setattr(es.cache_service, "set_json", fake_set_json, raising=True)

    token = await svc.generate_reset_token(user_id=1, email="a@b.com")

    assert token == "tok"
    assert called["key"] == f"{es._RESET_TOKEN_PREFIX}tok"
    assert called["expire"] == es._RESET_TOKEN_TTL_SECONDS

    value = called["value"]
    assert value["user_id"] == 1
    assert value["email"] == "a@b.com"
    assert value["used"] is False
    assert value["expires_at"] == (FixedDatetime.now() + timedelta(hours=1)).isoformat()


@pytest.mark.asyncio
async def test_generate_reset_token_fallback_on_cache_error(monkeypatch):
    svc = es.EmailService()

    monkeypatch.setattr(es, "datetime", FixedDatetime, raising=True)
    monkeypatch.setattr(es.secrets, "token_urlsafe", lambda _n: "tok", raising=True)

    async def fake_set_json(*_args, **_kwargs):
        raise RuntimeError("cache down")

    monkeypatch.setattr(es.cache_service, "set_json", fake_set_json, raising=True)

    token = await svc.generate_reset_token(user_id=2, email="x@y.com")

    assert token == "tok"
    assert "tok" in es._reset_tokens
    assert es._reset_tokens["tok"]["user_id"] == 2


def test_cleanup_expired_tokens_removes_past_expiry():
    svc = es.EmailService()
    es._reset_tokens["old"] = {
        "user_id": 1,
        "email": "a@b.com",
        "expires_at": "2000-01-01T00:00:00",
        "used": False,
    }

    svc._cleanup_expired_tokens()
    assert "old" not in es._reset_tokens


@pytest.mark.asyncio
async def test_verify_reset_token_cache_hit(monkeypatch):
    svc = es.EmailService()

    async def fake_get_json(_key):
        return {
            "user_id": 1,
            "email": "a@b.com",
            "expires_at": "2026-01-19T13:00:00",
            "used": False,
        }

    monkeypatch.setattr(es.cache_service, "get_json", fake_get_json, raising=True)

    data = await svc.verify_reset_token("tok")
    assert data is not None
    assert data["user_id"] == 1
    assert data["email"] == "a@b.com"


@pytest.mark.asyncio
async def test_verify_reset_token_cache_used_returns_none(monkeypatch):
    svc = es.EmailService()

    async def fake_get_json(_key):
        return {
            "user_id": 1,
            "email": "a@b.com",
            "expires_at": "2026-01-19T13:00:00",
            "used": True,
        }

    monkeypatch.setattr(es.cache_service, "get_json", fake_get_json, raising=True)

    assert await svc.verify_reset_token("tok") is None


@pytest.mark.asyncio
async def test_verify_reset_token_fallback_invalid_or_expired(monkeypatch):
    svc = es.EmailService()
    monkeypatch.setattr(es, "datetime", FixedDatetime, raising=True)

    es._reset_tokens["bad"] = {
        "user_id": 1,
        "email": "a@b.com",
        "expires_at": "not-iso",
        "used": False,
    }

    assert await svc.verify_reset_token("bad") is None
    assert "bad" not in es._reset_tokens

    es._reset_tokens["expired"] = {
        "user_id": 1,
        "email": "a@b.com",
        "expires_at": (FixedDatetime.now() - timedelta(seconds=1)).isoformat(),
        "used": False,
    }

    assert await svc.verify_reset_token("expired") is None
    assert "expired" not in es._reset_tokens


@pytest.mark.asyncio
async def test_verify_reset_token_cache_exception_fallback_memory_valid(monkeypatch):
    svc = es.EmailService()
    monkeypatch.setattr(es, "datetime", FixedDatetime, raising=True)

    async def fake_get_json(*_args, **_kwargs):
        raise RuntimeError("cache down")

    monkeypatch.setattr(es.cache_service, "get_json", fake_get_json, raising=True)

    es._reset_tokens["tok"] = {
        "user_id": 9,
        "email": "a@b.com",
        "expires_at": (FixedDatetime.now() + timedelta(seconds=10)).isoformat(),
        "used": False,
    }

    data = await svc.verify_reset_token("tok")
    assert data is not None
    assert data["user_id"] == 9


@pytest.mark.asyncio
async def test_verify_reset_token_fallback_used_returns_none(monkeypatch):
    svc = es.EmailService()

    async def fake_get_json(*_args, **_kwargs):
        raise RuntimeError("cache down")

    monkeypatch.setattr(es.cache_service, "get_json", fake_get_json, raising=True)

    es._reset_tokens["tok"] = {
        "user_id": 1,
        "email": "a@b.com",
        "expires_at": "2026-01-19T13:00:00",
        "used": True,
    }
    assert await svc.verify_reset_token("tok") is None


@pytest.mark.asyncio
async def test_invalidate_token_cache_path(monkeypatch):
    svc = es.EmailService()

    async def fake_get_json(_key):
        return {
            "user_id": 1,
            "email": "a@b.com",
            "expires_at": "2026-01-19T13:00:00",
            "used": False,
        }

    called = {}

    async def fake_set_json(key, value, expire):
        called["key"] = key
        called["value"] = value
        called["expire"] = expire
        return True

    monkeypatch.setattr(es.cache_service, "get_json", fake_get_json, raising=True)
    monkeypatch.setattr(es.cache_service, "set_json", fake_set_json, raising=True)

    await svc.invalidate_token("tok")

    assert called["key"] == f"{es._RESET_TOKEN_PREFIX}tok"
    assert called["value"]["used"] is True


@pytest.mark.asyncio
async def test_invalidate_token_fallback_sets_memory_used(monkeypatch):
    svc = es.EmailService()

    async def fake_get_json(*_args, **_kwargs):
        raise RuntimeError("cache down")

    monkeypatch.setattr(es.cache_service, "get_json", fake_get_json, raising=True)

    es._reset_tokens["tok"] = {
        "user_id": 1,
        "email": "a@b.com",
        "expires_at": "2026-01-19T13:00:00",
        "used": False,
    }

    await svc.invalidate_token("tok")
    assert es._reset_tokens["tok"]["used"] is True


@pytest.mark.asyncio
async def test_generate_and_verify_email_verification_token_cache(monkeypatch):
    svc = es.EmailService()

    monkeypatch.setattr(es, "datetime", FixedDatetime, raising=True)
    monkeypatch.setattr(es.secrets, "token_urlsafe", lambda _n: "etok", raising=True)

    async def fake_set_json(*_args, **_kwargs):
        return True

    async def fake_get_json(_key):
        return {
            "user_id": 3,
            "email": "v@e.com",
            "expires_at": (FixedDatetime.now() + timedelta(seconds=es._EMAIL_VERIFY_TOKEN_TTL_SECONDS)).isoformat(),
            "used": False,
        }

    monkeypatch.setattr(es.cache_service, "set_json", fake_set_json, raising=True)
    monkeypatch.setattr(es.cache_service, "get_json", fake_get_json, raising=True)

    token = await svc.generate_email_verification_token(3, "v@e.com")
    assert token == "etok"

    data = await svc.verify_email_verification_token("etok")
    assert data is not None
    assert data["user_id"] == 3


@pytest.mark.asyncio
async def test_generate_email_verification_token_fallback_and_cleanup_bad_reset_expires(monkeypatch):
    svc = es.EmailService()
    monkeypatch.setattr(es, "datetime", FixedDatetime, raising=True)
    monkeypatch.setattr(es.secrets, "token_urlsafe", lambda _n: "etok2", raising=True)

    async def fake_set_json(*_args, **_kwargs):
        raise RuntimeError("cache down")

    monkeypatch.setattr(es.cache_service, "set_json", fake_set_json, raising=True)

    es._reset_tokens["bad"] = {
        "user_id": 1,
        "email": "a@b.com",
        "expires_at": "not-iso",
        "used": False,
    }

    token = await svc.generate_email_verification_token(1, "a@b.com")
    assert token == "etok2"
    assert "etok2" in es._email_verification_tokens
    assert "bad" not in es._reset_tokens


@pytest.mark.asyncio
async def test_verify_email_verification_token_fallback_invalid_or_expired(monkeypatch):
    svc = es.EmailService()
    monkeypatch.setattr(es, "datetime", FixedDatetime, raising=True)

    es._email_verification_tokens["bad"] = {
        "user_id": 1,
        "email": "a@b.com",
        "expires_at": "not-iso",
        "used": False,
    }

    assert await svc.verify_email_verification_token("bad") is None
    assert "bad" not in es._email_verification_tokens

    es._email_verification_tokens["expired"] = {
        "user_id": 1,
        "email": "a@b.com",
        "expires_at": (FixedDatetime.now() - timedelta(seconds=1)).isoformat(),
        "used": False,
    }

    assert await svc.verify_email_verification_token("expired") is None
    assert "expired" not in es._email_verification_tokens


@pytest.mark.asyncio
async def test_verify_email_verification_token_cache_exception_fallback_memory_valid(monkeypatch):
    svc = es.EmailService()
    monkeypatch.setattr(es, "datetime", FixedDatetime, raising=True)

    async def fake_get_json(*_args, **_kwargs):
        raise RuntimeError("cache down")

    monkeypatch.setattr(es.cache_service, "get_json", fake_get_json, raising=True)

    es._email_verification_tokens["tok"] = {
        "user_id": 7,
        "email": "v@e.com",
        "expires_at": (FixedDatetime.now() + timedelta(seconds=10)).isoformat(),
        "used": False,
    }

    data = await svc.verify_email_verification_token("tok")
    assert data is not None
    assert data["user_id"] == 7


@pytest.mark.asyncio
async def test_verify_email_verification_token_fallback_used_returns_none(monkeypatch):
    svc = es.EmailService()

    async def fake_get_json(*_args, **_kwargs):
        raise RuntimeError("cache down")

    monkeypatch.setattr(es.cache_service, "get_json", fake_get_json, raising=True)

    es._email_verification_tokens["tok"] = {
        "user_id": 7,
        "email": "v@e.com",
        "expires_at": "2026-01-19T13:00:00",
        "used": True,
    }
    assert await svc.verify_email_verification_token("tok") is None


@pytest.mark.asyncio
async def test_invalidate_email_verification_token_cache_path(monkeypatch):
    svc = es.EmailService()

    async def fake_get_json(_key):
        return {
            "user_id": 3,
            "email": "v@e.com",
            "expires_at": "2026-01-19T13:00:00",
            "used": False,
        }

    called = {}

    async def fake_set_json(key, value, expire):
        called["key"] = key
        called["value"] = value
        called["expire"] = expire
        return True

    monkeypatch.setattr(es.cache_service, "get_json", fake_get_json, raising=True)
    monkeypatch.setattr(es.cache_service, "set_json", fake_set_json, raising=True)

    await svc.invalidate_email_verification_token("tok")
    assert called["key"] == f"{es._EMAIL_VERIFY_TOKEN_PREFIX}tok"
    assert called["value"]["used"] is True


@pytest.mark.asyncio
async def test_invalidate_email_verification_token_fallback_sets_memory_used(monkeypatch):
    svc = es.EmailService()

    async def fake_get_json(*_args, **_kwargs):
        raise RuntimeError("cache down")

    monkeypatch.setattr(es.cache_service, "get_json", fake_get_json, raising=True)

    es._email_verification_tokens["tok"] = {
        "user_id": 3,
        "email": "v@e.com",
        "expires_at": "2026-01-19T13:00:00",
        "used": False,
    }

    await svc.invalidate_email_verification_token("tok")
    assert es._email_verification_tokens["tok"]["used"] is True


@pytest.mark.asyncio
async def test_send_password_reset_email_not_configured_returns_true():
    svc = es.EmailService()
    ok = await svc.send_password_reset_email(
        email="a@b.com",
        reset_token="tok",
        reset_url="http://reset",
    )
    assert ok is True


@pytest.mark.asyncio
async def test_send_password_reset_email_configured_importerror(monkeypatch):
    svc = es.EmailService()
    svc.configure("smtp.example.com", 587, "u", "p")

    def fake_import_module(_name):
        raise ImportError("no aiosmtplib")

    monkeypatch.setattr(importlib, "import_module", fake_import_module, raising=True)

    ok = await svc.send_password_reset_email(
        email="a@b.com",
        reset_token="tok",
        reset_url="http://reset",
    )
    assert ok is False


@pytest.mark.asyncio
async def test_send_password_reset_email_configured_success(monkeypatch):
    svc = es.EmailService()
    svc.configure("smtp.example.com", 587, "u", "p")

    called = {}

    class DummyAiOSMTP:
        @staticmethod
        async def send(message, **kwargs):
            called["message"] = message
            called["kwargs"] = kwargs
            return None

    def fake_import_module(name):
        assert name == "aiosmtplib"
        return DummyAiOSMTP

    monkeypatch.setattr(importlib, "import_module", fake_import_module, raising=True)

    ok = await svc.send_password_reset_email(
        email="a@b.com",
        reset_token="tok",
        reset_url="http://reset",
    )

    assert ok is True
    assert called["message"]["To"] == "a@b.com"
    assert "密码重置" in str(called["message"]["Subject"])


@pytest.mark.asyncio
async def test_send_password_reset_email_configured_exception_returns_false(monkeypatch):
    svc = es.EmailService()
    svc.configure("smtp.example.com", 587, "u", "p")

    class DummyAiOSMTP:
        @staticmethod
        async def send(*_args, **_kwargs):
            raise RuntimeError("smtp down")

    monkeypatch.setattr(importlib, "import_module", lambda _n: DummyAiOSMTP, raising=True)

    ok = await svc.send_password_reset_email(
        email="a@b.com",
        reset_token="tok",
        reset_url="http://reset",
    )
    assert ok is False


@pytest.mark.asyncio
async def test_send_notification_email_not_configured_returns_false():
    svc = es.EmailService()
    ok = await svc.send_notification_email(email="a@b.com", subject="s", content="c")
    assert ok is False


@pytest.mark.asyncio
async def test_send_notification_email_configured_success(monkeypatch):
    svc = es.EmailService()
    svc.configure("smtp.example.com", 587, "u", "p")

    class DummyAiOSMTP:
        @staticmethod
        async def send(_message, **_kwargs):
            return None

    monkeypatch.setattr(importlib, "import_module", lambda _n: DummyAiOSMTP, raising=True)

    ok = await svc.send_notification_email(email="a@b.com", subject="s", content="c")
    assert ok is True


@pytest.mark.asyncio
async def test_send_notification_email_configured_importerror(monkeypatch):
    svc = es.EmailService()
    svc.configure("smtp.example.com", 587, "u", "p")

    def fake_import_module(_name):
        raise ImportError("no aiosmtplib")

    monkeypatch.setattr(importlib, "import_module", fake_import_module, raising=True)

    ok = await svc.send_notification_email(email="a@b.com", subject="s", content="c")
    assert ok is False


@pytest.mark.asyncio
async def test_send_notification_email_configured_exception_returns_false(monkeypatch):
    svc = es.EmailService()
    svc.configure("smtp.example.com", 587, "u", "p")

    class DummyAiOSMTP:
        @staticmethod
        async def send(*_args, **_kwargs):
            raise RuntimeError("smtp down")

    monkeypatch.setattr(importlib, "import_module", lambda _n: DummyAiOSMTP, raising=True)

    ok = await svc.send_notification_email(email="a@b.com", subject="s", content="c")
    assert ok is False


@pytest.mark.asyncio
async def test_send_email_verification_email_not_configured_returns_true():
    svc = es.EmailService()
    ok = await svc.send_email_verification_email(email="a@b.com", verify_url="http://verify")
    assert ok is True


@pytest.mark.asyncio
async def test_send_email_verification_email_configured_importerror(monkeypatch):
    svc = es.EmailService()
    svc.configure("smtp.example.com", 587, "u", "p")

    def fake_import_module(_name):
        raise ImportError("no aiosmtplib")

    monkeypatch.setattr(importlib, "import_module", fake_import_module, raising=True)

    ok = await svc.send_email_verification_email(email="a@b.com", verify_url="http://verify")
    assert ok is False


@pytest.mark.asyncio
async def test_send_email_verification_email_configured_success(monkeypatch):
    svc = es.EmailService()
    svc.configure("smtp.example.com", 587, "u", "p")

    called = {}

    class DummyAiOSMTP:
        @staticmethod
        async def send(message, **_kwargs):
            called["message"] = message
            return None

    monkeypatch.setattr(importlib, "import_module", lambda _n: DummyAiOSMTP, raising=True)

    ok = await svc.send_email_verification_email(email="a@b.com", verify_url="http://verify")
    assert ok is True
    assert called["message"]["To"] == "a@b.com"
    assert "邮箱验证" in str(called["message"]["Subject"])


@pytest.mark.asyncio
async def test_send_email_verification_email_configured_exception_returns_false(monkeypatch):
    svc = es.EmailService()
    svc.configure("smtp.example.com", 587, "u", "p")

    class DummyAiOSMTP:
        @staticmethod
        async def send(*_args, **_kwargs):
            raise RuntimeError("smtp down")

    monkeypatch.setattr(importlib, "import_module", lambda _n: DummyAiOSMTP, raising=True)

    ok = await svc.send_email_verification_email(email="a@b.com", verify_url="http://verify")
    assert ok is False
