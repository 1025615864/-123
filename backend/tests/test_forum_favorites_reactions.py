from types import SimpleNamespace

import pytest

from app.main import app
from app.utils.deps import get_current_user


@pytest.mark.asyncio
async def test_forum_toggle_favorite_and_list_favorites(client, monkeypatch):
    from app.routers.forum import favorites as fav_router

    user = SimpleNamespace(id=1, role="user")

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user

    post_obj = SimpleNamespace(id=1)

    async def fake_get_post(db, post_id):
        return post_obj if int(post_id) == 1 else None

    async def fake_toggle(db, post_id, user_id):
        return True, 5

    async def fake_get_user_favorites(db, user_id, page, page_size, category, keyword):
        return [], 0

    async def fake_build(db, posts, user_id):
        return []

    monkeypatch.setattr(fav_router.forum_service, "get_post", fake_get_post, raising=True)
    monkeypatch.setattr(fav_router.forum_service, "toggle_post_favorite", fake_toggle, raising=True)
    monkeypatch.setattr(fav_router.forum_service, "get_user_favorites", fake_get_user_favorites, raising=True)
    monkeypatch.setattr(fav_router, "_build_post_responses", fake_build, raising=True)

    try:
        nf = await client.post("/api/forum/posts/2/favorite")
        assert nf.status_code == 404

        ok = await client.post("/api/forum/posts/1/favorite")
        assert ok.status_code == 200
        body = ok.json()
        assert body["favorited"] is True
        assert body["favorite_count"] == 5
        assert body["message"] == "收藏成功"

        lst = await client.get("/api/forum/favorites", params={"page": 1, "page_size": 10})
        assert lst.status_code == 200
        data = lst.json()
        assert data["total"] == 0
        assert data["items"] == []

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_forum_toggle_reaction(client, monkeypatch):
    from app.routers.forum import reactions as react_router

    user = SimpleNamespace(id=1, role="user")

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user

    post_obj = SimpleNamespace(id=1)

    async def fake_get_post(db, post_id):
        return post_obj if int(post_id) == 1 else None

    async def fake_toggle(db, post_id, user_id, emoji):
        return True, [{"emoji": emoji, "count": 2}]

    monkeypatch.setattr(react_router.forum_service, "get_post", fake_get_post, raising=True)
    monkeypatch.setattr(react_router.forum_service, "toggle_reaction", fake_toggle, raising=True)

    try:
        nf = await client.post("/api/forum/posts/2/reaction", json={"emoji": "😀"})
        assert nf.status_code == 404

        ok = await client.post("/api/forum/posts/1/reaction", json={"emoji": "😀"})
        assert ok.status_code == 200
        body = ok.json()
        assert body["reacted"] is True
        assert body["emoji"] == "😀"
        assert body["message"] == "已添加反应"
        assert isinstance(body.get("reactions"), list) and body["reactions"][0]["count"] == 2

    finally:
        app.dependency_overrides.pop(get_current_user, None)
