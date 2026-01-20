from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.main import app
from app.utils.deps import get_current_user, get_current_user_optional


def _comment_payload(*, comment_id: int, post_id: int, user_id: int, content: str, created_at: datetime, review_status: str | None = None, review_reason: str | None = None):
    return {
        "id": int(comment_id),
        "content": str(content),
        "post_id": int(post_id),
        "user_id": int(user_id),
        "parent_id": None,
        "like_count": 0,
        "images": [],
        "created_at": created_at,
        "review_status": review_status,
        "review_reason": review_reason,
        "reviewed_at": None,
        "author": None,
        "is_liked": False,
        "replies": [],
    }


@pytest.mark.asyncio
async def test_forum_create_comment_branches(client, monkeypatch):
    from app.routers.forum import comments as c_router

    now = datetime.now(timezone.utc)
    user = SimpleNamespace(id=1, role="user")

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user

    async def fake_apply(_db):
        return None

    async def fake_build(_db, comment, _viewer_user_id):
        return _comment_payload(
            comment_id=int(getattr(comment, "id", 0) or 0),
            post_id=int(getattr(comment, "post_id", 0) or 0),
            user_id=int(getattr(comment, "user_id", 0) or 0),
            content=str(getattr(comment, "content", "")),
            created_at=now,
            review_status=getattr(comment, "review_status", None),
            review_reason=getattr(comment, "review_reason", None),
        )

    monkeypatch.setattr(c_router.forum_service, "apply_content_filter_config_from_db", fake_apply, raising=True)
    monkeypatch.setattr(c_router, "_build_comment_response", fake_build, raising=True)

    try:
        def bad_check(_content: str):
            return False, "bad"

        monkeypatch.setattr(c_router, "check_comment_content", bad_check, raising=True)
        r1 = await client.post("/api/forum/posts/1/comments", json={"content": "x"})
        assert r1.status_code == 400
        assert r1.json().get("detail") == "bad"

        def ok_check(_content: str):
            return True, None

        monkeypatch.setattr(c_router, "check_comment_content", ok_check, raising=True)

        async def get_post_none(_db, _post_id):
            return None

        monkeypatch.setattr(c_router.forum_service, "get_post", get_post_none, raising=True)
        r2 = await client.post("/api/forum/posts/1/comments", json={"content": "x"})
        assert r2.status_code == 404

        post = SimpleNamespace(id=1, user_id=1, is_deleted=False)

        async def get_post_ok(_db, _post_id):
            return post

        monkeypatch.setattr(c_router.forum_service, "get_post", get_post_ok, raising=True)

        async def get_comment_none(_db, _cid):
            return None

        monkeypatch.setattr(c_router.forum_service, "get_comment", get_comment_none, raising=True)
        r3 = await client.post(
            "/api/forum/posts/1/comments",
            json={"content": "x", "parent_id": 1},
        )
        assert r3.status_code == 400
        assert r3.json().get("detail") == "父评论不存在"

        parent_wrong_post = SimpleNamespace(id=1, post_id=2)

        async def get_comment_wrong(_db, _cid):
            return parent_wrong_post

        monkeypatch.setattr(c_router.forum_service, "get_comment", get_comment_wrong, raising=True)
        r4 = await client.post(
            "/api/forum/posts/1/comments",
            json={"content": "x", "parent_id": 1},
        )
        assert r4.status_code == 400

        comment = SimpleNamespace(
            id=10,
            post_id=1,
            user_id=1,
            content="ok",
            review_status="pending",
            review_reason="r",
        )

        async def create_comment(_db, _post_id, _user_id, _comment_data):
            return comment

        monkeypatch.setattr(c_router.forum_service, "create_comment", create_comment, raising=True)

        notified: dict[str, object] = {}

        def fake_notify(_db, **kwargs):
            notified.update(kwargs)

        monkeypatch.setattr(c_router, "_create_notification", fake_notify, raising=True)

        r5 = await client.post("/api/forum/posts/1/comments", json={"content": "ok"})
        assert r5.status_code == 200
        assert notified.get("title") == "你的评论已提交审核"

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_forum_get_comments_owner_can_view_post_any(client, monkeypatch):
    from app.routers.forum import comments as c_router

    user = SimpleNamespace(id=1, role="user")

    async def override_user():
        return user

    app.dependency_overrides[get_current_user_optional] = override_user
    try:
        async def get_post_none(_db, _post_id):
            return None

        post_any = SimpleNamespace(id=1, user_id=1, is_deleted=False)

        async def get_post_any(_db, _post_id):
            return post_any

        async def get_visible(_db, _post_id, _page, _page_size, viewer_user_id, viewer_role, include_unapproved):
            assert int(viewer_user_id) == 1
            return [], 0

        monkeypatch.setattr(c_router.forum_service, "get_post", get_post_none, raising=True)
        monkeypatch.setattr(c_router.forum_service, "get_post_any", get_post_any, raising=True)
        monkeypatch.setattr(c_router.forum_service, "get_comments_visible", get_visible, raising=True)

        import app.utils.permissions as perm

        monkeypatch.setattr(perm, "is_owner_or_admin", lambda *_args, **_kwargs: True, raising=True)

        res = await client.get("/api/forum/posts/1/comments")
        assert res.status_code == 200
        assert res.json().get("total") == 0

    finally:
        app.dependency_overrides.pop(get_current_user_optional, None)


@pytest.mark.asyncio
async def test_forum_get_comments_not_found_when_anonymous(client, monkeypatch):
    from app.routers.forum import comments as c_router

    async def override_none():
        return None

    app.dependency_overrides[get_current_user_optional] = override_none
    try:
        async def get_post_none(_db, _post_id):
            return None

        monkeypatch.setattr(c_router.forum_service, "get_post", get_post_none, raising=True)

        res = await client.get("/api/forum/posts/1/comments")
        assert res.status_code == 404

    finally:
        app.dependency_overrides.pop(get_current_user_optional, None)


@pytest.mark.asyncio
async def test_forum_comment_delete_restore_like_branches(client, monkeypatch):
    from app.routers.forum import comments as c_router

    user = SimpleNamespace(id=1, role="user")

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user

    import app.utils.permissions as perm

    try:
        async def get_comment_none(_db, _cid):
            return None

        monkeypatch.setattr(c_router.forum_service, "get_comment", get_comment_none, raising=True)
        r1 = await client.delete("/api/forum/comments/1")
        assert r1.status_code == 404

        comment = SimpleNamespace(id=2, user_id=2)

        async def get_comment(_db, _cid):
            return comment

        monkeypatch.setattr(c_router.forum_service, "get_comment", get_comment, raising=True)
        monkeypatch.setattr(perm, "is_owner_or_admin", lambda *_args, **_kwargs: False, raising=True)
        r2 = await client.delete("/api/forum/comments/2")
        assert r2.status_code == 403

        deleted: list[int] = []

        async def delete_comment(_db, c):
            deleted.append(int(c.id))

        monkeypatch.setattr(perm, "is_owner_or_admin", lambda *_args, **_kwargs: True, raising=True)
        monkeypatch.setattr(c_router.forum_service, "delete_comment", delete_comment, raising=True)
        r3 = await client.delete("/api/forum/comments/2")
        assert r3.status_code == 200
        assert 2 in deleted

        async def get_any_none(_db, _cid):
            return None

        monkeypatch.setattr(c_router.forum_service, "get_comment_any", get_any_none, raising=True)
        r4 = await client.post("/api/forum/comments/1/restore")
        assert r4.status_code == 404

        comment_any = SimpleNamespace(id=3, user_id=2)

        async def get_any(_db, _cid):
            return comment_any

        monkeypatch.setattr(c_router.forum_service, "get_comment_any", get_any, raising=True)
        monkeypatch.setattr(perm, "is_owner_or_admin", lambda *_args, **_kwargs: False, raising=True)
        r5 = await client.post("/api/forum/comments/3/restore")
        assert r5.status_code == 403

        restored: list[int] = []

        async def restore(_db, c):
            restored.append(int(c.id))
            return True

        monkeypatch.setattr(perm, "is_owner_or_admin", lambda *_args, **_kwargs: True, raising=True)
        monkeypatch.setattr(c_router.forum_service, "restore_comment", restore, raising=True)
        r6 = await client.post("/api/forum/comments/3/restore")
        assert r6.status_code == 200
        assert r6.json().get("message") == "已恢复"
        assert 3 in restored

        async def get_comment_for_like_none(_db, _cid):
            return None

        monkeypatch.setattr(c_router.forum_service, "get_comment", get_comment_for_like_none, raising=True)
        r7 = await client.post("/api/forum/comments/1/like")
        assert r7.status_code == 404

        comment_like = SimpleNamespace(id=4, user_id=1)

        async def get_comment_for_like(_db, _cid):
            return comment_like

        monkeypatch.setattr(c_router.forum_service, "get_comment", get_comment_for_like, raising=True)

        async def toggle_like(_db, _cid, _uid):
            return True, 2

        monkeypatch.setattr(c_router.forum_service, "toggle_comment_like", toggle_like, raising=True)
        r8 = await client.post("/api/forum/comments/4/like")
        assert r8.status_code == 200
        assert r8.json().get("message") == "点赞成功"

        async def toggle_like2(_db, _cid, _uid):
            return False, 1

        monkeypatch.setattr(c_router.forum_service, "toggle_comment_like", toggle_like2, raising=True)
        r9 = await client.post("/api/forum/comments/4/like")
        assert r9.status_code == 200
        assert r9.json().get("message") == "取消点赞"

    finally:
        app.dependency_overrides.pop(get_current_user, None)
