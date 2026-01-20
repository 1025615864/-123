import pytest
from types import SimpleNamespace

from app.main import app
from app.models.forum import Post
from app.models.knowledge import LegalKnowledge
from app.models.lawfirm import LawFirm, Lawyer
from app.models.news import News
from app.models.system import SearchHistory
from app.routers import search as search_router
from app.utils.deps import get_current_user_optional


@pytest.mark.asyncio
async def test_search_router_global_search_returns_results(client, test_session):
    news = News(title="劳动合同指南", summary="x", content="劳动合同内容", is_published=True)
    post = Post(title="合同纠纷讨论", content="劳动合同", user_id=1, is_deleted=False)
    firm = LawFirm(name="合同律所", description="合同", is_active=True)
    lawyer = Lawyer(name="张律师", specialties="合同", is_active=True)
    knowledge = LegalKnowledge(
        knowledge_type="law",
        title="劳动合同法",
        content="劳动合同条文",
        category="劳动法",
        is_active=True,
    )
    test_session.add_all([news, post, firm, lawyer, knowledge])
    await test_session.commit()

    resp = await client.get("/api/search", params={"q": "合同"})
    assert resp.status_code == 200

    data = resp.json()
    assert set(data.keys()) == {"news", "posts", "lawfirms", "lawyers", "knowledge"}
    assert len(data["news"]) >= 1
    assert len(data["posts"]) >= 1
    assert len(data["lawfirms"]) >= 1
    assert len(data["lawyers"]) >= 1
    assert len(data["knowledge"]) >= 1


@pytest.mark.asyncio
async def test_search_router_record_search_exception_does_not_break_search(client, monkeypatch, test_session):
    news = News(title="劳动合同指南", summary="x", content="劳动合同内容", is_published=True)
    test_session.add(news)
    await test_session.commit()

    async def boom(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(search_router.search_service, "record_search", boom, raising=True)

    resp = await client.get("/api/search", params={"q": "合同"})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["news"]) >= 1


@pytest.mark.asyncio
async def test_search_router_suggestions_and_hot_and_history_endpoints(client, test_session):
    test_session.add_all(
        [
            News(title="劳动合同指南", summary=None, content="x", is_published=True),
            Post(title="劳动仲裁", content="x", user_id=1, is_deleted=False),
            SearchHistory(keyword="劳动合同", user_id=1, ip_address="1.1.1.1"),
            SearchHistory(keyword="劳动合同", user_id=1, ip_address="1.1.1.1"),
        ]
    )
    await test_session.commit()

    sug = await client.get("/api/search/suggestions", params={"q": "劳", "limit": 5})
    assert sug.status_code == 200
    assert "suggestions" in sug.json()

    hot = await client.get("/api/search/hot", params={"limit": 10})
    assert hot.status_code == 200
    assert "keywords" in hot.json()

    hist = await client.get("/api/search/history")
    assert hist.status_code == 200
    assert hist.json() == {"history": []}

    cleared = await client.delete("/api/search/history")
    assert cleared.status_code == 200
    assert cleared.json()["message"] == "未登录"


@pytest.mark.asyncio
async def test_search_router_history_and_clear_when_logged_in(client, test_session):
    test_session.add_all(
        [
            SearchHistory(keyword="劳动合同", user_id=1, ip_address="1.1.1.1"),
            SearchHistory(keyword="劳动合同", user_id=1, ip_address="1.1.1.1"),
            SearchHistory(keyword="劳动仲裁", user_id=1, ip_address="1.1.1.1"),
        ]
    )
    await test_session.commit()

    async def override_user():
        return SimpleNamespace(id=1)

    app.dependency_overrides[get_current_user_optional] = override_user
    try:
        hist = await client.get("/api/search/history", params={"limit": 10})
        assert hist.status_code == 200
        data = hist.json()
        assert "history" in data
        assert "劳动合同" in data["history"]

        cleared = await client.delete("/api/search/history")
        assert cleared.status_code == 200
        assert cleared.json()["message"] == "搜索历史已清除"
    finally:
        app.dependency_overrides.pop(get_current_user_optional, None)
