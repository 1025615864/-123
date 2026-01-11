import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_admin_feedback_ticket_stats_and_assignment(
    client: AsyncClient,
    test_session: AsyncSession,
):
    from app.models.feedback import FeedbackTicket
    from app.models.user import User
    from app.utils.security import create_access_token, hash_password

    admin = User(
        username="a_feedback",
        email="a_feedback@example.com",
        nickname="a_feedback",
        hashed_password=hash_password("Test123456"),
        role="admin",
        is_active=True,
    )
    test_session.add(admin)
    await test_session.commit()
    await test_session.refresh(admin)

    user = User(
        username="u_feedback",
        email="u_feedback@example.com",
        nickname="u_feedback",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    t1 = FeedbackTicket(user_id=int(user.id), subject="s1", content="c1", status="open")
    t2 = FeedbackTicket(user_id=int(user.id), subject="s2", content="c2", status="processing")
    t3 = FeedbackTicket(user_id=int(user.id), subject="s3", content="c3", status="closed")
    test_session.add_all([t1, t2, t3])
    await test_session.commit()

    token = create_access_token({"sub": str(admin.id)})
    headers = {"Authorization": f"Bearer {token}"}

    stats_res = await client.get("/api/feedback/admin/tickets/stats", headers=headers)
    assert stats_res.status_code == 200
    stats = stats_res.json()
    assert int(stats.get("total") or 0) >= 3
    assert int(stats.get("open") or 0) >= 1
    assert int(stats.get("processing") or 0) >= 1
    assert int(stats.get("closed") or 0) >= 1
    assert int(stats.get("unassigned") or 0) >= 3

    assign_res = await client.put(
        f"/api/feedback/admin/tickets/{t1.id}",
        json={"admin_id": int(admin.id)},
        headers=headers,
    )
    assert assign_res.status_code == 200
    item = assign_res.json()
    assert int(item.get("admin_id") or 0) == int(admin.id)

    unassign_res = await client.put(
        f"/api/feedback/admin/tickets/{t1.id}",
        json={"admin_id": None},
        headers=headers,
    )
    assert unassign_res.status_code == 200
    item2 = unassign_res.json()
    assert item2.get("admin_id") is None


@pytest.mark.asyncio
async def test_admin_feedback_ticket_assignment_only_self(
    client: AsyncClient,
    test_session: AsyncSession,
):
    from app.models.feedback import FeedbackTicket
    from app.models.user import User
    from app.utils.security import create_access_token, hash_password

    admin1 = User(
        username="a_feedback_1",
        email="a_feedback_1@example.com",
        nickname="a_feedback_1",
        hashed_password=hash_password("Test123456"),
        role="admin",
        is_active=True,
    )
    admin2 = User(
        username="a_feedback_2",
        email="a_feedback_2@example.com",
        nickname="a_feedback_2",
        hashed_password=hash_password("Test123456"),
        role="admin",
        is_active=True,
    )
    user = User(
        username="u_feedback_2",
        email="u_feedback_2@example.com",
        nickname="u_feedback_2",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add_all([admin1, admin2, user])
    await test_session.commit()
    await test_session.refresh(admin1)
    await test_session.refresh(admin2)
    await test_session.refresh(user)

    t = FeedbackTicket(user_id=int(user.id), subject="s", content="c", status="open")
    test_session.add(t)
    await test_session.commit()
    await test_session.refresh(t)

    token = create_access_token({"sub": str(admin1.id)})
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.put(
        f"/api/feedback/admin/tickets/{t.id}",
        json={"admin_id": int(admin2.id)},
        headers=headers,
    )
    assert res.status_code == 400
