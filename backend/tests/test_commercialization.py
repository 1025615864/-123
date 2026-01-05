from datetime import datetime, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import UserBalance
from app.models.system import SystemConfig
from app.models.user import User
from app.utils.security import create_access_token, hash_password


def _auth_header(user: User) -> dict[str, str]:
    token = create_access_token({"sub": str(user.id)})
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_vip_balance_payment_sets_vip_expires_and_quota_reflects(
    client: AsyncClient,
    test_session: AsyncSession,
):
    user = User(
        username="u_vip_pay",
        email="u_vip_pay@example.com",
        nickname="u_vip_pay",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    # Seed balance so we can use balance payment.
    bal = UserBalance(
        user_id=int(user.id),
        balance=1000.0,
        frozen=0.0,
        total_recharged=1000.0,
        total_consumed=0.0,
        balance_cents=100000,
        frozen_cents=0,
        total_recharged_cents=100000,
        total_consumed_cents=0,
    )
    test_session.add(bal)
    await test_session.commit()

    # Override VIP daily limits via SystemConfig
    test_session.add_all(
        [
            SystemConfig(
                key="VIP_AI_CHAT_DAILY_LIMIT",
                value="123",
                category="commercial",
                description="",
            ),
            SystemConfig(
                key="VIP_DOCUMENT_GENERATE_DAILY_LIMIT",
                value="456",
                category="commercial",
                description="",
            ),
        ]
    )
    await test_session.commit()

    # Create VIP order
    create_res = await client.post(
        "/api/payment/orders",
        json={"order_type": "vip", "amount": 0.01, "title": "VIP会员", "description": "VIP会员"},
        headers=_auth_header(user),
    )
    assert create_res.status_code == 200
    order_no = str(create_res.json()["order_no"])

    # Pay with balance
    pay_res = await client.post(
        f"/api/payment/orders/{order_no}/pay",
        json={"payment_method": "balance"},
        headers=_auth_header(user),
    )
    assert pay_res.status_code == 200

    # Verify vip_expires_at updated
    refreshed = (await test_session.execute(select(User).where(User.id == int(user.id)))).scalar_one()
    assert refreshed.vip_expires_at is not None

    expires_at = refreshed.vip_expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    assert expires_at > datetime.now(timezone.utc)

    # Quotas endpoint should reflect vip active + vip limits
    quotas_res = await client.get("/api/user/me/quotas", headers=_auth_header(user))
    assert quotas_res.status_code == 200
    data = quotas_res.json()

    assert data.get("is_vip_active") is True

    assert int(data.get("ai_chat_limit") or 0) == 123
    assert int(data.get("document_generate_limit") or 0) == 456


@pytest.mark.asyncio
async def test_guest_document_generate_quota_optional_toggle(
    client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.routers import document as doc_router
    from app.utils import rate_limiter as rl

    # Reset global in-memory limiter to avoid interference.
    rl.rate_limiter._requests.clear()  # type: ignore[attr-defined]
    rl.rate_limiter._last_seen.clear()  # type: ignore[attr-defined]

    monkeypatch.setattr(doc_router, "GUEST_DOCUMENT_GENERATE_LIMIT", 1, raising=True)
    monkeypatch.setattr(doc_router, "GUEST_DOCUMENT_GENERATE_WINDOW_SECONDS", 60 * 60 * 24, raising=True)

    payload = {
        "document_type": "complaint",
        "case_type": "合同纠纷",
        "plaintiff_name": "A",
        "defendant_name": "B",
        "facts": "f",
        "claims": "c",
    }

    ok = await client.post("/api/documents/generate", json=payload)
    assert ok.status_code == 200

    blocked = await client.post("/api/documents/generate", json=payload)
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_ai_pack_order_pricing_uses_system_config(
    client: AsyncClient,
    test_session: AsyncSession,
):
    user = User(
        username="u_pack_pay",
        email="u_pack_pay@example.com",
        nickname="u_pack_pay",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    test_session.add(
        SystemConfig(
            key="AI_CHAT_PACK_OPTIONS_JSON",
            value='{"10": 1.23, "50": 4.56}',
            category="commercial",
            description="",
        )
    )
    await test_session.commit()

    res = await client.post(
        "/api/payment/orders",
        json={
            "order_type": "ai_pack",
            "amount": 0.01,
            "title": "AI咨询次数包",
            "description": "AI咨询次数包",
            "related_id": 10,
            "related_type": "ai_chat",
        },
        headers=_auth_header(user),
    )
    assert res.status_code == 200
    body = res.json()
    got = float(body.get("amount") or 0)
    assert abs(got - 1.23) < 1e-6
