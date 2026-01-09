import asyncio
from datetime import datetime, timezone
import importlib
from typing import cast

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


async def _create_user(
    session: AsyncSession,
    *,
    username: str,
    email: str,
    email_verified: bool = False,
    phone_verified: bool = False,
) -> User:
    u = User(
        username=username,
        email=email,
        nickname=username,
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
        email_verified=bool(email_verified),
        phone_verified=bool(phone_verified),
    )
    if email_verified:
        u.email_verified_at = datetime.now(timezone.utc)
    if phone_verified:
        u.phone_verified_at = datetime.now(timezone.utc)

    session.add(u)
    await session.commit()
    await session.refresh(u)
    return u


def _reset_in_memory_state() -> None:
    from app.utils.rate_limiter import rate_limiter

    requests = getattr(rate_limiter, "_requests", None)
    if isinstance(requests, dict):
        requests.clear()

    last_seen = getattr(rate_limiter, "_last_seen", None)
    if isinstance(last_seen, dict):
        last_seen.clear()

    cache_service_mod = importlib.import_module("app.services.cache_service")
    setattr(cache_service_mod, "_memory_cache", {})

    email_service_mod = importlib.import_module("app.services.email_service")
    setattr(email_service_mod, "_reset_tokens", {})
    setattr(email_service_mod, "_email_verification_tokens", {})


@pytest.mark.asyncio
async def test_sms_send_rate_limited_by_lock(
    client: AsyncClient,
    test_session: AsyncSession,
):
    _reset_in_memory_state()
    user = await _create_user(
        test_session,
        username="u_sms_lock",
        email="u_sms_lock@example.com",
    )

    res1 = await client.post(
        "/api/user/sms/send",
        headers=_auth_header(user),
        json={"phone": "13800138000", "scene": "bind_phone"},
    )
    assert res1.status_code == 200
    payload1 = cast(dict[str, object], cast(object, res1.json()))
    assert str(payload1.get("message") or "")
    assert str(payload1.get("code") or "").strip()

    res2 = await client.post(
        "/api/user/sms/send",
        headers=_auth_header(user),
        json={"phone": "13800138000", "scene": "bind_phone"},
    )
    assert res2.status_code == 429


@pytest.mark.asyncio
async def test_sms_verify_success_updates_user(
    client: AsyncClient,
    test_session: AsyncSession,
):
    _reset_in_memory_state()
    user = await _create_user(
        test_session,
        username="u_sms_verify_ok",
        email="u_sms_verify_ok@example.com",
    )

    send = await client.post(
        "/api/user/sms/send",
        headers=_auth_header(user),
        json={"phone": "13800138001", "scene": "bind_phone"},
    )
    assert send.status_code == 200
    send_payload = cast(dict[str, object], cast(object, send.json()))
    code = str(send_payload.get("code") or "").strip()
    assert code

    verify = await client.post(
        "/api/user/sms/verify",
        headers=_auth_header(user),
        json={"phone": "13800138001", "scene": "bind_phone", "code": code},
    )
    assert verify.status_code == 200

    refreshed = (
        await test_session.execute(select(User).where(User.id == int(user.id)))
    ).scalar_one()
    assert str(getattr(refreshed, "phone", "") or "") == "13800138001"
    assert bool(getattr(refreshed, "phone_verified", False)) is True


@pytest.mark.asyncio
async def test_sms_verify_wrong_code_fails(
    client: AsyncClient,
    test_session: AsyncSession,
):
    _reset_in_memory_state()
    user = await _create_user(
        test_session,
        username="u_sms_verify_wrong",
        email="u_sms_verify_wrong@example.com",
    )

    send = await client.post(
        "/api/user/sms/send",
        headers=_auth_header(user),
        json={"phone": "13800138002", "scene": "bind_phone"},
    )
    assert send.status_code == 200

    verify = await client.post(
        "/api/user/sms/verify",
        headers=_auth_header(user),
        json={"phone": "13800138002", "scene": "bind_phone", "code": "000000"},
    )
    assert verify.status_code == 400

    refreshed = (
        await test_session.execute(select(User).where(User.id == int(user.id)))
    ).scalar_one()
    assert bool(getattr(refreshed, "phone_verified", False)) is False


@pytest.mark.asyncio
async def test_sms_verify_expired_code_fails(
    client: AsyncClient,
    test_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    _reset_in_memory_state()

    user_router_mod = importlib.import_module("app.routers.user")
    monkeypatch.setattr(user_router_mod, "_SMS_CODE_TTL_SECONDS", 1, raising=True)

    user = await _create_user(
        test_session,
        username="u_sms_verify_exp",
        email="u_sms_verify_exp@example.com",
    )

    send = await client.post(
        "/api/user/sms/send",
        headers=_auth_header(user),
        json={"phone": "13800138003", "scene": "bind_phone"},
    )
    assert send.status_code == 200
    send_payload = cast(dict[str, object], cast(object, send.json()))
    code = str(send_payload.get("code") or "").strip()
    assert code

    await asyncio.sleep(1.05)

    verify = await client.post(
        "/api/user/sms/verify",
        headers=_auth_header(user),
        json={"phone": "13800138003", "scene": "bind_phone", "code": code},
    )
    assert verify.status_code == 400

    refreshed = (
        await test_session.execute(select(User).where(User.id == int(user.id)))
    ).scalar_one()
    assert bool(getattr(refreshed, "phone_verified", False)) is False


@pytest.mark.asyncio
async def test_email_verification_request_and_verify_success(
    client: AsyncClient,
    test_session: AsyncSession,
):
    _reset_in_memory_state()
    user = await _create_user(
        test_session,
        username="u_email_verify_ok",
        email="u_email_verify_ok@example.com",
        email_verified=False,
    )

    req = await client.post(
        "/api/user/email-verification/request",
        headers=_auth_header(user),
        json={},
    )
    assert req.status_code == 200
    req_payload = cast(dict[str, object], cast(object, req.json()))
    token = str(req_payload.get("token") or "").strip()
    assert token

    verify = await client.get(
        "/api/user/email-verification/verify",
        params={"token": token},
    )
    assert verify.status_code == 200

    refreshed = (
        await test_session.execute(select(User).where(User.id == int(user.id)))
    ).scalar_one()
    assert bool(getattr(refreshed, "email_verified", False)) is True


@pytest.mark.asyncio
async def test_email_verification_invalid_token_returns_400(
    client: AsyncClient,
):
    _reset_in_memory_state()
    verify = await client.get(
        "/api/user/email-verification/verify",
        params={"token": "invalid-token"},
    )
    assert verify.status_code == 400


@pytest.mark.asyncio
async def test_email_verification_request_rate_limited_by_ip(
    client: AsyncClient,
    test_session: AsyncSession,
):
    _reset_in_memory_state()
    user = await _create_user(
        test_session,
        username="u_email_verify_rl",
        email="u_email_verify_rl@example.com",
        email_verified=False,
    )

    for _ in range(3):
        res = await client.post(
            "/api/user/email-verification/request",
            headers=_auth_header(user),
            json={},
        )
        assert res.status_code == 200

    blocked = await client.post(
        "/api/user/email-verification/request",
        headers=_auth_header(user),
        json={},
    )
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_email_verification_token_expired_returns_400(
    client: AsyncClient,
    test_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
):
    _reset_in_memory_state()

    email_service_mod = importlib.import_module("app.services.email_service")
    monkeypatch.setattr(email_service_mod, "_EMAIL_VERIFY_TOKEN_TTL_SECONDS", 1, raising=True)

    user = await _create_user(
        test_session,
        username="u_email_verify_exp",
        email="u_email_verify_exp@example.com",
        email_verified=False,
    )

    req = await client.post(
        "/api/user/email-verification/request",
        headers=_auth_header(user),
        json={},
    )
    assert req.status_code == 200
    req_payload = cast(dict[str, object], cast(object, req.json()))
    token = str(req_payload.get("token") or "").strip()
    assert token

    await asyncio.sleep(1.05)

    verify = await client.get(
        "/api/user/email-verification/verify",
        params={"token": token},
    )
    assert verify.status_code == 400


@pytest.mark.asyncio
async def test_email_verification_token_cannot_be_reused(
    client: AsyncClient,
    test_session: AsyncSession,
):
    _reset_in_memory_state()
    user = await _create_user(
        test_session,
        username="u_email_verify_reuse",
        email="u_email_verify_reuse@example.com",
        email_verified=False,
    )

    req = await client.post(
        "/api/user/email-verification/request",
        headers=_auth_header(user),
        json={},
    )
    assert req.status_code == 200
    req_payload = cast(dict[str, object], cast(object, req.json()))
    token = str(req_payload.get("token") or "").strip()
    assert token

    ok = await client.get(
        "/api/user/email-verification/verify",
        params={"token": token},
    )
    assert ok.status_code == 200

    reused = await client.get(
        "/api/user/email-verification/verify",
        params={"token": token},
    )
    assert reused.status_code == 400
