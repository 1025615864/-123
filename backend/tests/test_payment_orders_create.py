from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.consultation import Consultation
from app.models.payment import PaymentOrder
from app.models.system import SystemConfig
from app.models.user import User
from app.routers import payment_legacy as legacy
from app.routers.payment.orders_create import create_order
from app.utils.deps import get_current_user


@pytest.mark.asyncio
async def test_payment_orders_create_invalid_order_type_and_amount_leq_zero(client, test_session: AsyncSession):
    user = User(username="u_oc_1", email="u_oc_1@example.com", nickname="u_oc_1", hashed_password="x")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user
    try:
        bad_type = await client.post(
            "/api/payment/orders",
            json={"order_type": "nope", "amount": 1.0, "title": "t", "description": "d"},
        )
        assert bad_type.status_code == 400
        assert bad_type.json().get("detail") == "无效的订单类型"

        bad_amount = await client.post(
            "/api/payment/orders",
            json={"order_type": "service", "amount": 0, "title": "t", "description": "d"},
        )
        assert bad_amount.status_code == 400
        assert bad_amount.json().get("detail") == "金额必须大于0"

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_payment_orders_create_ai_pack_invalid_related_type_and_pack(client, test_session: AsyncSession):
    user = User(username="u_oc_2", email="u_oc_2@example.com", nickname="u_oc_2", hashed_password="x")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    test_session.add(
        SystemConfig(
            key="AI_CHAT_PACK_OPTIONS_JSON",
            value='{"10": 1.23}',
            category="commercial",
            description="",
        )
    )
    await test_session.commit()

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user
    try:
        bad_rt = await client.post(
            "/api/payment/orders",
            json={
                "order_type": "ai_pack",
                "amount": 0.01,
                "title": "t",
                "description": "d",
                "related_id": 10,
                "related_type": "bad_type",
            },
        )
        assert bad_rt.status_code == 400
        assert bad_rt.json().get("detail") == "无效的次数包类型"

        bad_pack = await client.post(
            "/api/payment/orders",
            json={
                "order_type": "ai_pack",
                "amount": 0.01,
                "title": "t",
                "description": "d",
                "related_id": 999,
                "related_type": "ai_chat",
            },
        )
        assert bad_pack.status_code == 400
        assert bad_pack.json().get("detail") == "无效的次数包"

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_payment_orders_create_light_consult_review_invalid_params_and_permissions(client, test_session: AsyncSession):
    owner = User(username="u_oc_3", email="u_oc_3@example.com", nickname="u_oc_3", hashed_password="x")
    other = User(username="u_oc_4", email="u_oc_4@example.com", nickname="u_oc_4", hashed_password="x")
    test_session.add_all([owner, other])
    await test_session.commit()
    await test_session.refresh(owner)
    await test_session.refresh(other)

    consultation_other = Consultation(user_id=int(other.id), session_id="s_oc_1", title="t")
    test_session.add(consultation_other)
    await test_session.commit()
    await test_session.refresh(consultation_other)

    async def override_user():
        return owner

    app.dependency_overrides[get_current_user] = override_user
    try:
        bad_rt = await client.post(
            "/api/payment/orders",
            json={
                "order_type": "light_consult_review",
                "amount": 0.01,
                "title": "t",
                "description": "d",
                "related_id": 1,
                "related_type": "bad",
            },
        )
        assert bad_rt.status_code == 400
        assert bad_rt.json().get("detail") == "无效的关联类型"

        missing_id = await client.post(
            "/api/payment/orders",
            json={
                "order_type": "light_consult_review",
                "amount": 0.01,
                "title": "t",
                "description": "d",
                "related_type": "ai_consultation",
            },
        )
        assert missing_id.status_code == 400
        assert missing_id.json().get("detail") == "缺少咨询ID"

        not_found = await client.post(
            "/api/payment/orders",
            json={
                "order_type": "light_consult_review",
                "amount": 0.01,
                "title": "t",
                "description": "d",
                "related_type": "ai_consultation",
                "related_id": 999999,
            },
        )
        assert not_found.status_code == 404
        assert not_found.json().get("detail") == "咨询记录不存在"

        forbidden = await client.post(
            "/api/payment/orders",
            json={
                "order_type": "light_consult_review",
                "amount": 0.01,
                "title": "t",
                "description": "d",
                "related_type": "ai_consultation",
                "related_id": int(consultation_other.id),
            },
        )
        assert forbidden.status_code == 403
        assert forbidden.json().get("detail") == "无权限购买该咨询的复核"

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_payment_orders_create_direct_calls_cover_type_parsing_branches(test_session: AsyncSession):
    user = User(username="u_oc_5", email="u_oc_5@example.com", nickname="u_oc_5", hashed_password="x")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    consultation = Consultation(user_id=int(user.id), session_id="s_oc_2", title="t")
    test_session.add(consultation)
    await test_session.commit()
    await test_session.refresh(consultation)

    test_session.add(
        SystemConfig(
            key="AI_CHAT_PACK_OPTIONS_JSON",
            value='{"10": 1.23}',
            category="commercial",
            description="",
        )
    )
    await test_session.commit()

    bad_bool = SimpleNamespace(
        order_type="ai_pack",
        amount=0.01,
        title="t",
        description="d",
        related_id=True,
        related_type="ai_chat",
    )
    with pytest.raises(legacy.HTTPException) as exc:
        await create_order(bad_bool, current_user=user, db=test_session)
    assert exc.value.status_code == 400
    assert exc.value.detail == "无效的次数包"

    ok_float = SimpleNamespace(
        order_type="ai_pack",
        amount=0.01,
        title="t",
        description="d",
        related_id=10.0,
        related_type="ai_chat",
    )
    resp = await create_order(ok_float, current_user=user, db=test_session)
    assert "order_no" in resp

    ok_str = SimpleNamespace(
        order_type="ai_pack",
        amount=0.01,
        title="t",
        description="d",
        related_id="10",
        related_type="ai_chat",
    )
    resp2 = await create_order(ok_str, current_user=user, db=test_session)
    assert "order_no" in resp2

    bad_str = SimpleNamespace(
        order_type="ai_pack",
        amount=0.01,
        title="t",
        description="d",
        related_id="abc",
        related_type="ai_chat",
    )
    with pytest.raises(legacy.HTTPException) as exc2:
        await create_order(bad_str, current_user=user, db=test_session)
    assert exc2.value.status_code == 400
    assert exc2.value.detail == "无效的次数包"

    ok_lr_float = SimpleNamespace(
        order_type="light_consult_review",
        amount=0.01,
        title="t",
        description="d",
        related_id=float(consultation.id),
        related_type="ai_consultation",
    )
    resp3 = await create_order(ok_lr_float, current_user=user, db=test_session)
    assert "order_no" in resp3

    ok_lr_str = SimpleNamespace(
        order_type="light_consult_review",
        amount=0.01,
        title="t",
        description="d",
        related_id=str(consultation.id),
        related_type="ai_consultation",
    )
    resp4 = await create_order(ok_lr_str, current_user=user, db=test_session)
    assert "order_no" in resp4

    bad_lr_bool = SimpleNamespace(
        order_type="light_consult_review",
        amount=0.01,
        title="t",
        description="d",
        related_id=True,
        related_type="ai_consultation",
    )
    with pytest.raises(legacy.HTTPException) as exc3:
        await create_order(bad_lr_bool, current_user=user, db=test_session)
    assert exc3.value.status_code == 400
    assert exc3.value.detail == "缺少咨询ID"

    bad_lr_str = SimpleNamespace(
        order_type="light_consult_review",
        amount=0.01,
        title="t",
        description="d",
        related_id="bad",
        related_type="ai_consultation",
    )
    with pytest.raises(legacy.HTTPException) as exc4:
        await create_order(bad_lr_str, current_user=user, db=test_session)
    assert exc4.value.status_code == 400
    assert exc4.value.detail == "缺少咨询ID"

    orders = await test_session.execute(
        legacy.select(PaymentOrder).where(PaymentOrder.user_id == int(user.id))
    )
    assert orders.scalars().first() is not None
