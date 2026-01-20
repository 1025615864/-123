from datetime import datetime, timezone

import pytest

from app.main import app
from app.models.calendar import CalendarReminder
from app.models.user import User
from app.utils.deps import get_current_user


@pytest.mark.asyncio
async def test_calendar_create_list_update_delete_flow(client, test_session, monkeypatch):
    user = User(username="cal_user", email="cal_user@example.com", nickname="cal_user", hashed_password="x")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user

    try:
        due1 = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        due2 = datetime(2026, 1, 2, 0, 0, 0, tzinfo=timezone.utc)

        # create 1
        resp = await client.post(
            "/api/calendar/reminders",
            json={"title": "t1", "note": "n1", "due_at": due1.isoformat(), "remind_at": None},
        )
        assert resp.status_code == 200
        r1 = resp.json()
        assert r1["user_id"] == user.id
        assert r1["title"] == "t1"
        assert r1["note"] == "n1"
        assert r1["is_done"] is False
        assert r1["done_at"] is None

        # create 2
        resp2 = await client.post(
            "/api/calendar/reminders",
            json={"title": "t2", "note": None, "due_at": due2.isoformat(), "remind_at": None},
        )
        assert resp2.status_code == 200
        r2 = resp2.json()

        # list all
        lst = await client.get("/api/calendar/reminders")
        assert lst.status_code == 200
        data = lst.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2
        assert data["items"][0]["id"] == r1["id"]

        # list from_at filter
        lst2 = await client.get("/api/calendar/reminders", params={"from_at": due2.isoformat()})
        assert lst2.status_code == 200
        data2 = lst2.json()
        assert data2["total"] == 1
        assert data2["items"][0]["id"] == r2["id"]

        # update done -> sets done_at
        fixed_now = datetime(2026, 1, 3, 0, 0, 0, tzinfo=timezone.utc)

        class _DT:
            @staticmethod
            def now(tz=None):
                _ = tz
                return fixed_now

        import app.routers.calendar as cal_router

        monkeypatch.setattr(cal_router, "datetime", _DT, raising=True)

        upd = await client.put(
            f"/api/calendar/reminders/{r1['id']}",
            json={"is_done": True},
        )
        assert upd.status_code == 200
        u1 = upd.json()
        assert u1["is_done"] is True
        assert u1["done_at"].startswith(fixed_now.isoformat().replace("+00:00", "")) or u1["done_at"].startswith(
            fixed_now.isoformat()
        )

        # update done False -> clears done_at
        upd2 = await client.put(
            f"/api/calendar/reminders/{r1['id']}",
            json={"is_done": False},
        )
        assert upd2.status_code == 200
        u2 = upd2.json()
        assert u2["is_done"] is False
        assert u2["done_at"] is None

        # delete
        d = await client.delete(f"/api/calendar/reminders/{r1['id']}")
        assert d.status_code == 200
        assert d.json()["message"] == "删除成功"

        # ensure deleted
        res = await test_session.get(CalendarReminder, int(r1["id"]))
        assert res is None

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_calendar_filters_pagination_and_update_fields(client, test_session, monkeypatch):
    user = User(username="cal_user3", email="cal_user3@example.com", nickname="cal_user3", hashed_password="x")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user

    try:
        due1 = datetime(2026, 2, 1, 0, 0, 0, tzinfo=timezone.utc)
        due2 = datetime(2026, 2, 2, 0, 0, 0, tzinfo=timezone.utc)
        due3 = datetime(2026, 2, 3, 0, 0, 0, tzinfo=timezone.utc)

        r1 = (
            await client.post(
                "/api/calendar/reminders",
                json={"title": "a", "note": None, "due_at": due1.isoformat(), "remind_at": None},
            )
        ).json()
        r2 = (
            await client.post(
                "/api/calendar/reminders",
                json={"title": "b", "note": None, "due_at": due2.isoformat(), "remind_at": None},
            )
        ).json()
        r3 = (
            await client.post(
                "/api/calendar/reminders",
                json={"title": "c", "note": None, "due_at": due3.isoformat(), "remind_at": None},
            )
        ).json()

        fixed_done_at = datetime(2026, 2, 10, 0, 0, 0, tzinfo=timezone.utc)

        class _DT1:
            @staticmethod
            def now(tz=None):
                _ = tz
                return fixed_done_at

        import app.routers.calendar as cal_router

        monkeypatch.setattr(cal_router, "datetime", _DT1, raising=True)
        done_resp = await client.put(
            f"/api/calendar/reminders/{r2['id']}",
            json={"is_done": True},
        )
        assert done_resp.status_code == 200
        done_data = done_resp.json()
        assert done_data["is_done"] is True
        done_at_1 = done_data["done_at"]
        assert done_at_1 is not None

        fixed_done_at2 = datetime(2026, 2, 11, 0, 0, 0, tzinfo=timezone.utc)

        class _DT2:
            @staticmethod
            def now(tz=None):
                _ = tz
                return fixed_done_at2

        monkeypatch.setattr(cal_router, "datetime", _DT2, raising=True)
        done_resp2 = await client.put(
            f"/api/calendar/reminders/{r2['id']}",
            json={"is_done": True},
        )
        assert done_resp2.status_code == 200
        done_data2 = done_resp2.json()
        assert done_data2["done_at"] == done_at_1

        only_done = await client.get("/api/calendar/reminders", params={"done": True})
        assert only_done.status_code == 200
        only_done_data = only_done.json()
        assert only_done_data["total"] == 1
        assert only_done_data["items"][0]["id"] == r2["id"]

        only_undone = await client.get("/api/calendar/reminders", params={"done": False})
        assert only_undone.status_code == 200
        only_undone_data = only_undone.json()
        assert only_undone_data["total"] == 2

        to_at = await client.get("/api/calendar/reminders", params={"to_at": due2.isoformat()})
        assert to_at.status_code == 200
        to_at_data = to_at.json()
        assert to_at_data["total"] == 2
        assert [x["id"] for x in to_at_data["items"]] == [r1["id"], r2["id"]]

        page2 = await client.get("/api/calendar/reminders", params={"page": 2, "page_size": 1})
        assert page2.status_code == 200
        page2_data = page2.json()
        assert page2_data["total"] == 3
        assert len(page2_data["items"]) == 1
        assert page2_data["items"][0]["id"] == r2["id"]

        remind_at = datetime(2026, 2, 1, 12, 0, 0, tzinfo=timezone.utc)
        upd = await client.put(
            f"/api/calendar/reminders/{r1['id']}",
            json={
                "title": " new ",
                "note": "n",
                "due_at": due3.isoformat(),
                "remind_at": remind_at.isoformat(),
            },
        )
        assert upd.status_code == 200
        u = upd.json()
        assert u["title"] == " new "
        assert u["note"] == "n"
        assert u["remind_at"] is not None
        assert str(u["due_at"]).startswith("2026-02-03")

        _ = r3

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_calendar_update_and_delete_missing_returns_404(client, test_session):
    user = User(username="cal_user2", email="cal_user2@example.com", nickname="cal_user2", hashed_password="x")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user

    try:
        upd = await client.put("/api/calendar/reminders/999999", json={"title": "x"})
        assert upd.status_code == 404

        d = await client.delete("/api/calendar/reminders/999999")
        assert d.status_code == 404

    finally:
        app.dependency_overrides.pop(get_current_user, None)
