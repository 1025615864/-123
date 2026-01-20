from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.main import app
from app.utils.deps import get_current_user, get_current_user_optional


@pytest.mark.asyncio
async def test_news_topics_list_and_detail(client, monkeypatch):
    from app.routers.news import topics as topics_router

    now = datetime.now(timezone.utc)

    topic = SimpleNamespace(
        id=1,
        title="专题",
        description=None,
        cover_image=None,
        is_active=True,
        sort_order=0,
        auto_category=None,
        auto_keyword=None,
        auto_limit=0,
        created_at=now,
        updated_at=now,
    )

    async def fake_list_topics(db, active_only=True):
        assert active_only is True
        return [topic]

    async def fake_get_topic(db, topic_id):
        return topic if int(topic_id) == 1 else None

    n1 = SimpleNamespace(
        id=11,
        title="n1",
        summary=None,
        cover_image=None,
        category="cat",
        source=None,
        source_url=None,
        source_site=None,
        author=None,
        view_count=0,
        is_top=False,
        published_at=now,
        created_at=now,
    )

    async def fake_get_topic_news(db, topic_id, page, page_size, published_only=True):
        assert int(topic_id) == 1
        assert published_only is True
        return [n1], 1

    async def fake_get_favorite_stats(db, ids, user_id):
        assert ids == [11]
        assert user_id is None
        return {11: (3, False)}

    async def fake_risk_levels(db, ids):
        return {11: "low"}

    async def fake_keywords(db, ids):
        return {11: ["k1", "k2"]}

    monkeypatch.setattr(topics_router.news_service, "list_topics", fake_list_topics, raising=True)
    monkeypatch.setattr(topics_router.news_service, "get_topic", fake_get_topic, raising=True)
    monkeypatch.setattr(topics_router.news_service, "get_topic_news", fake_get_topic_news, raising=True)
    monkeypatch.setattr(topics_router.news_service, "get_favorite_stats", fake_get_favorite_stats, raising=True)
    monkeypatch.setattr(topics_router, "_get_ai_risk_levels", fake_risk_levels, raising=True)
    monkeypatch.setattr(topics_router, "_get_ai_keywords", fake_keywords, raising=True)

    async def override_none():
        return None

    app.dependency_overrides[get_current_user_optional] = override_none
    try:
        res = await client.get("/api/news/topics")
        assert res.status_code == 200
        items = res.json().get("items")
        assert isinstance(items, list) and items

        nf = await client.get("/api/news/topics/2")
        assert nf.status_code == 404

        detail = await client.get("/api/news/topics/1")
        assert detail.status_code == 200
        body = detail.json()
        assert body["topic"]["id"] == 1
        assert body["total"] == 1
        assert body["items"][0]["id"] == 11
        assert body["items"][0]["favorite_count"] == 3
        assert body["items"][0]["is_favorited"] is False
        assert body["items"][0]["ai_risk_level"] == "low"
        assert body["items"][0]["ai_keywords"] == ["k1", "k2"]

    finally:
        app.dependency_overrides.pop(get_current_user_optional, None)


@pytest.mark.asyncio
async def test_news_comments_get_and_create_and_delete(client, monkeypatch):
    from app.routers.news import comments as comments_router

    now = datetime.now(timezone.utc)

    user = SimpleNamespace(id=1, role="user")

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user

    news_obj = SimpleNamespace(id=1)

    async def fake_get_published(db, news_id):
        return news_obj if int(news_id) == 1 else None

    async def fake_get_comments(db, news_id, page, page_size):
        c1 = SimpleNamespace(
            id=10,
            news_id=int(news_id),
            user_id=1,
            content="hi",
            review_status="approved",
            review_reason=None,
            created_at=now,
            author=None,
        )
        return [c1], 1

    created_comment = SimpleNamespace(id=11)

    async def fake_create_comment(db, news_id, user_id, content, review_status, review_reason):
        assert int(news_id) == 1
        assert int(user_id) == 1
        assert content
        assert review_status in {"approved", "pending"}
        return created_comment

    async def fake_get_comment(db, comment_id):
        if int(comment_id) == 11:
            return SimpleNamespace(
                id=11,
                news_id=1,
                user_id=1,
                content="ok",
                review_status="approved",
                review_reason=None,
                created_at=now,
                author=None,
                is_deleted=False,
            )
        if int(comment_id) == 12:
            return SimpleNamespace(
                id=12,
                news_id=1,
                user_id=2,
                content="other",
                review_status="approved",
                review_reason=None,
                created_at=now,
                author=None,
                is_deleted=False,
            )
        return None

    deleted_ids: list[int] = []

    async def fake_delete_comment(db, comment):
        deleted_ids.append(int(comment.id))

    def fake_check_comment_content(content: str):
        if content == "bad":
            return False, "bad_content"
        return True, None

    def fake_needs_review(content: str):
        if content == "need_review":
            return True, "reason"
        return False, None

    monkeypatch.setattr(comments_router.news_service, "get_published", fake_get_published, raising=True)
    monkeypatch.setattr(comments_router.news_service, "get_comments", fake_get_comments, raising=True)
    monkeypatch.setattr(comments_router.news_service, "create_comment", fake_create_comment, raising=True)
    monkeypatch.setattr(comments_router.news_service, "get_comment", fake_get_comment, raising=True)
    monkeypatch.setattr(comments_router.news_service, "delete_comment", fake_delete_comment, raising=True)
    monkeypatch.setattr(comments_router, "check_comment_content", fake_check_comment_content, raising=True)
    monkeypatch.setattr(comments_router, "needs_review", fake_needs_review, raising=True)

    import app.utils.permissions as perm

    def fake_is_owner_or_admin(current_user, owner_id: int):
        return int(getattr(current_user, "id", 0)) == int(owner_id)

    monkeypatch.setattr(perm, "is_owner_or_admin", fake_is_owner_or_admin, raising=True)

    try:
        nf = await client.get("/api/news/2/comments")
        assert nf.status_code == 404

        ok = await client.get("/api/news/1/comments")
        assert ok.status_code == 200
        body = ok.json()
        assert body["total"] == 1

        c_nf = await client.post("/api/news/2/comments", json={"content": "x"})
        assert c_nf.status_code == 404

        bad = await client.post("/api/news/1/comments", json={"content": "bad"})
        assert bad.status_code == 400
        assert bad.json().get("detail") == "bad_content"

        pending = await client.post("/api/news/1/comments", json={"content": "need_review"})
        assert pending.status_code == 200

        ok_create = await client.post("/api/news/1/comments", json={"content": "ok"})
        assert ok_create.status_code == 200
        assert ok_create.json()["id"] == 11

        del_nf = await client.delete("/api/news/comments/999")
        assert del_nf.status_code == 404

        del_forbidden = await client.delete("/api/news/comments/12")
        assert del_forbidden.status_code == 403

        del_ok = await client.delete("/api/news/comments/11")
        assert del_ok.status_code == 200
        assert del_ok.json().get("message") == "删除成功"
        assert 11 in deleted_ids

    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_news_comment_create_returns_500_when_fetch_created_comment_failed(client, monkeypatch):
    from app.routers.news import comments as comments_router

    user = SimpleNamespace(id=1, role="user")

    async def override_user():
        return user

    app.dependency_overrides[get_current_user] = override_user

    news_obj = SimpleNamespace(id=1)

    async def fake_get_published(db, news_id):
        return news_obj

    created_comment = SimpleNamespace(id=123)

    async def fake_create_comment(db, news_id, user_id, content, review_status, review_reason):
        return created_comment

    async def fake_get_comment(db, comment_id):
        return None

    def fake_check_comment_content(content: str):
        return True, None

    def fake_needs_review(content: str):
        return False, None

    monkeypatch.setattr(comments_router.news_service, "get_published", fake_get_published, raising=True)
    monkeypatch.setattr(comments_router.news_service, "create_comment", fake_create_comment, raising=True)
    monkeypatch.setattr(comments_router.news_service, "get_comment", fake_get_comment, raising=True)
    monkeypatch.setattr(comments_router, "check_comment_content", fake_check_comment_content, raising=True)
    monkeypatch.setattr(comments_router, "needs_review", fake_needs_review, raising=True)

    try:
        res = await client.post("/api/news/1/comments", json={"content": "ok"})
        assert res.status_code == 500
        assert res.json().get("detail") == "评论创建失败"
    finally:
        app.dependency_overrides.pop(get_current_user, None)
