from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.system import SystemConfig
from app.models.user import User
from app.models.user_quota import UserQuotaDaily, UserQuotaPackBalance
from app.services.quota_service import QuotaService, _get_int_env, _is_vip_active, _get_int_config


def test_get_int_env_default_and_invalid(monkeypatch):
    monkeypatch.delenv("X_TEST_INT", raising=False)
    assert _get_int_env("X_TEST_INT", 7) == 7

    monkeypatch.setenv("X_TEST_INT", "abc")
    assert _get_int_env("X_TEST_INT", 7) == 7

    monkeypatch.setenv("X_TEST_INT", "42")
    assert _get_int_env("X_TEST_INT", 7) == 42


def test_is_vip_active_handles_none_and_naive_datetime() -> None:
    assert _is_vip_active(None) is False

    u = User(username="u", email="u@example.com", nickname="u", hashed_password="x")
    u.vip_expires_at = "not-a-datetime"  # type: ignore[assignment]
    assert _is_vip_active(u) is False

    u.vip_expires_at = datetime.utcnow() + timedelta(days=1)
    assert _is_vip_active(u) is True

    u.vip_expires_at = datetime.utcnow() - timedelta(days=1)
    assert _is_vip_active(u) is False


@pytest.mark.asyncio
async def test_get_or_create_today_and_pack_balance_integrityerror_fallback(monkeypatch, test_session):
    svc = QuotaService()

    user = User(username="quota_u", email="quota_u@example.com", nickname="quota_u", hashed_password="x")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    orig_commit = test_session.commit

    async def commit_then_raise():
        await orig_commit()
        raise IntegrityError("stmt", {}, Exception("orig"))

    monkeypatch.setattr(test_session, "commit", commit_then_raise, raising=True)

    row = await svc._get_or_create_today(test_session, int(user.id))
    assert row.user_id == user.id

    pack = await svc._get_or_create_pack_balance(test_session, int(user.id))
    assert pack.user_id == user.id


@pytest.mark.asyncio
async def test_quota_service_enforce_and_record_ai_chat_uses_pack_when_over_limit(test_session):
    svc = QuotaService()

    user = User(username="q1", email="q1@example.com", nickname="q1", hashed_password="x")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    test_session.add_all(
        [
            SystemConfig(key="FREE_AI_CHAT_DAILY_LIMIT", value="1"),
            SystemConfig(key="VIP_AI_CHAT_DAILY_LIMIT", value="999999"),
        ]
    )
    await test_session.commit()

    today = date.today()
    test_session.add(UserQuotaDaily(user_id=user.id, day=today, ai_chat_count=1, document_generate_count=0))
    test_session.add(UserQuotaPackBalance(user_id=user.id, ai_chat_credits=0, document_generate_credits=0))
    await test_session.commit()

    with pytest.raises(Exception) as ei:
        await svc.enforce_ai_chat_quota(test_session, user)
    assert getattr(ei.value, "status_code", None) == 429

    res = await test_session.execute(
        select(UserQuotaPackBalance).where(UserQuotaPackBalance.user_id == user.id)
    )
    p = res.scalar_one()
    p.ai_chat_credits = 2
    test_session.add(p)
    await test_session.commit()

    await svc.enforce_ai_chat_quota(test_session, user)


@pytest.mark.asyncio
async def test_quota_service_record_ai_chat_usage_increments_then_decrements_pack(test_session):
    svc = QuotaService()

    user = User(username="q2", email="q2@example.com", nickname="q2", hashed_password="x")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    test_session.add(SystemConfig(key="FREE_AI_CHAT_DAILY_LIMIT", value="1"))
    await test_session.commit()

    today = date.today()
    test_session.add(UserQuotaDaily(user_id=user.id, day=today, ai_chat_count=0, document_generate_count=0))
    test_session.add(UserQuotaPackBalance(user_id=user.id, ai_chat_credits=1, document_generate_credits=0))
    await test_session.commit()

    await svc.record_ai_chat_usage(test_session, user)

    res = await test_session.execute(
        select(UserQuotaDaily).where(
            UserQuotaDaily.user_id == user.id, UserQuotaDaily.day == today
        )
    )
    row = res.scalar_one()
    assert row.ai_chat_count == 1

    await svc.record_ai_chat_usage(test_session, user)

    res2 = await test_session.execute(
        select(UserQuotaPackBalance).where(UserQuotaPackBalance.user_id == user.id)
    )
    pack = res2.scalar_one()
    assert pack.ai_chat_credits == 0


@pytest.mark.asyncio
async def test_quota_service_document_quota_paths(test_session):
    svc = QuotaService()

    user = User(username="q3", email="q3@example.com", nickname="q3", hashed_password="x")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    test_session.add_all(
        [
            SystemConfig(key="FREE_DOCUMENT_GENERATE_DAILY_LIMIT", value="1"),
            SystemConfig(key="VIP_DOCUMENT_GENERATE_DAILY_LIMIT", value="999"),
        ]
    )
    await test_session.commit()

    today = date.today()
    test_session.add(UserQuotaDaily(user_id=user.id, day=today, ai_chat_count=0, document_generate_count=1))
    test_session.add(UserQuotaPackBalance(user_id=user.id, ai_chat_credits=0, document_generate_credits=0))
    await test_session.commit()

    with pytest.raises(Exception) as ei:
        await svc.enforce_document_generate_quota(test_session, user)
    assert getattr(ei.value, "status_code", None) == 429

    res = await test_session.execute(
        select(UserQuotaPackBalance).where(UserQuotaPackBalance.user_id == user.id)
    )
    pack = res.scalar_one()
    pack.document_generate_credits = 1
    test_session.add(pack)
    await test_session.commit()

    await svc.record_document_generate_usage(test_session, user)

    res2 = await test_session.execute(
        select(UserQuotaPackBalance).where(UserQuotaPackBalance.user_id == user.id)
    )
    pack2 = res2.scalar_one()
    assert pack2.document_generate_credits == 0


@pytest.mark.asyncio
async def test_quota_service_get_today_quota_includes_limits_and_remaining(test_session):
    svc = QuotaService()

    user = User(
        username="q4",
        email="q4@example.com",
        nickname="q4",
        hashed_password="x",
        vip_expires_at=datetime.now(timezone.utc) + timedelta(days=10),
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    test_session.add_all(
        [
            SystemConfig(key="FREE_AI_CHAT_DAILY_LIMIT", value="1"),
            SystemConfig(key="VIP_AI_CHAT_DAILY_LIMIT", value="9"),
            SystemConfig(key="FREE_DOCUMENT_GENERATE_DAILY_LIMIT", value="2"),
            SystemConfig(key="VIP_DOCUMENT_GENERATE_DAILY_LIMIT", value="8"),
        ]
    )
    await test_session.commit()

    today = date.today()
    test_session.add(UserQuotaDaily(user_id=user.id, day=today, ai_chat_count=1, document_generate_count=3))
    test_session.add(UserQuotaPackBalance(user_id=user.id, ai_chat_credits=2, document_generate_credits=1))
    await test_session.commit()

    info = await svc.get_today_quota(test_session, user)
    assert info["ai_chat_limit"] == 9
    assert info["document_generate_limit"] == 8
    assert info["ai_chat_pack_remaining"] == 2
    assert info["document_generate_pack_remaining"] == 1
    assert info["is_vip_active"] is True


@pytest.mark.asyncio
async def test_get_int_config_missing_and_invalid_values_fallback_to_default(test_session):
    assert await _get_int_config(test_session, "MISSING_KEY", 123) == 123

    test_session.add(SystemConfig(key="BAD_INT", value="abc"))
    await test_session.commit()
    assert await _get_int_config(test_session, "BAD_INT", 456) == 456

    test_session.add(SystemConfig(key="NONE_INT", value=None))
    await test_session.commit()
    assert await _get_int_config(test_session, "NONE_INT", 789) == 789


@pytest.mark.asyncio
async def test_quota_service_admin_role_is_unlimited_and_consume_calls(test_session):
    svc = QuotaService()
    user = User(username="qadmin", email="qadmin@example.com", nickname="qadmin", hashed_password="x", role="admin")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    await svc.consume_ai_chat(test_session, user)
    await svc.consume_document_generate(test_session, user)


@pytest.mark.asyncio
async def test_quota_service_list_quota_usage_pagination_and_limits(test_session):
    svc = QuotaService()

    user = User(username="q5", email="q5@example.com", nickname="q5", hashed_password="x")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    test_session.add_all(
        [
            SystemConfig(key="FREE_AI_CHAT_DAILY_LIMIT", value="1"),
            SystemConfig(key="FREE_DOCUMENT_GENERATE_DAILY_LIMIT", value="2"),
        ]
    )
    await test_session.commit()

    today = date.today()
    test_session.add_all(
        [
            UserQuotaDaily(user_id=user.id, day=today, ai_chat_count=1, document_generate_count=2),
            UserQuotaDaily(user_id=user.id, day=today - timedelta(days=1), ai_chat_count=0, document_generate_count=1),
        ]
    )
    await test_session.commit()

    resp = await svc.list_quota_usage(test_session, user, days=0, page=0, page_size=999)
    assert resp["page"] == 1
    assert resp["page_size"] == 100
    assert resp["total"] >= 1
    assert isinstance(resp["items"], list)
