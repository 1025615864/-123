import pytest

from app.main import app
from app.models.feedback import FeedbackTicket
from app.models.user import User
from app.utils.deps import get_current_user, require_admin


@pytest.mark.asyncio
async def test_feedback_user_create_and_list(client, test_session):
    user = User(username="fb_user", email="fb_user@example.com", nickname="fb_user", hashed_password="x")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user
    try:
        resp = await client.post(
            "/api/feedback",
            json={"subject": "  s1 ", "content": "  c1  "},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["user_id"] == user.id
        assert data["subject"] == "s1"
        assert data["content"] == "c1"
        assert data["status"] == "open"

        lst = await client.get("/api/feedback", params={"page": 1, "page_size": 10})
        assert lst.status_code == 200
        l = lst.json()
        assert l["total"] == 1
        assert len(l["items"]) == 1
        assert l["items"][0]["id"] == data["id"]

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_feedback_admin_stats_list_and_update(client, test_session):
    admin = User(username="fb_admin", email="fb_admin@example.com", nickname="fb_admin", hashed_password="x", role="admin")
    user = User(username="fb_user2", email="fb_user2@example.com", nickname="fb_user2", hashed_password="x")
    other_admin = User(username="fb_admin2", email="fb_admin2@example.com", nickname="fb_admin2", hashed_password="x", role="admin")
    test_session.add_all([admin, other_admin, user])
    await test_session.commit()
    await test_session.refresh(admin)
    await test_session.refresh(other_admin)
    await test_session.refresh(user)

    t1 = FeedbackTicket(user_id=user.id, subject="a", content="x", status="open", admin_id=None)
    t2 = FeedbackTicket(user_id=user.id, subject="b", content="y", status="processing", admin_id=admin.id)
    t3 = FeedbackTicket(user_id=user.id, subject="c", content="z", status="closed", admin_id=None)
    test_session.add_all([t1, t2, t3])
    await test_session.commit()
    await test_session.refresh(t1)
    await test_session.refresh(t2)
    await test_session.refresh(t3)

    async def override_admin():
        return admin

    app.dependency_overrides[require_admin] = override_admin
    try:
        stats = await client.get("/api/feedback/admin/tickets/stats")
        assert stats.status_code == 200
        s = stats.json()
        assert s["total"] == 3
        assert s["open"] == 1
        assert s["processing"] == 1
        assert s["closed"] == 1
        assert s["unassigned"] == 2

        # list all
        lst = await client.get("/api/feedback/admin/tickets", params={"page": 1, "page_size": 10})
        assert lst.status_code == 200
        l = lst.json()
        assert l["total"] == 3
        assert len(l["items"]) == 3

        # filter by status
        lst2 = await client.get(
            "/api/feedback/admin/tickets",
            params={"status": "processing", "page": 1, "page_size": 10},
        )
        assert lst2.status_code == 200
        l2 = lst2.json()
        assert l2["total"] == 1
        assert l2["items"][0]["id"] == t2.id

        # keyword filter
        lst3 = await client.get(
            "/api/feedback/admin/tickets",
            params={"keyword": "a", "page": 1, "page_size": 10},
        )
        assert lst3.status_code == 200
        l3 = lst3.json()
        assert l3["total"] == 1
        assert l3["items"][0]["id"] == t1.id

        # update missing -> 404
        missing = await client.put("/api/feedback/admin/tickets/999999", json={"status": "open"})
        assert missing.status_code == 404

        # invalid status -> 400
        bad = await client.put(f"/api/feedback/admin/tickets/{t1.id}", json={"status": "bad"})
        assert bad.status_code == 400

        # assign to other admin not allowed -> 400
        bad2 = await client.put(f"/api/feedback/admin/tickets/{t1.id}", json={"admin_id": other_admin.id})
        assert bad2.status_code == 400

        # set reply + status + assign to self
        upd = await client.put(
            f"/api/feedback/admin/tickets/{t1.id}",
            json={"admin_reply": "  reply  ", "status": "processing", "admin_id": admin.id},
        )
        assert upd.status_code == 200
        u = upd.json()
        assert u["status"] == "processing"
        assert u["admin_reply"] == "reply"
        assert u["admin_id"] == admin.id

        # clear assignment
        upd2 = await client.put(
            f"/api/feedback/admin/tickets/{t1.id}",
            json={"admin_id": None},
        )
        assert upd2.status_code == 200
        u2 = upd2.json()
        assert u2["admin_id"] is None

    finally:
        app.dependency_overrides.pop(require_admin, None)
