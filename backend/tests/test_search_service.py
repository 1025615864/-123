import pytest

from app.models.forum import Post
from app.models.knowledge import LegalKnowledge
from app.models.lawfirm import LawFirm, Lawyer
from app.models.news import News
from app.models.system import SearchHistory
from app.services.search_service import SearchService


def test_escape_like_escapes_special_chars() -> None:
    s = SearchService._escape_like(r"a%_\\b")
    assert s == r"a\%\_\\\\b"


def test_make_snippet_handles_empty_and_keyword_hit() -> None:
    assert SearchService._make_snippet(None, "x") is None
    assert SearchService._make_snippet("", "x") is None

    text = "这是一个劳动合同纠纷的示例文本，用于测试片段截取。"
    snippet = SearchService._make_snippet(text, "合同", max_len=20)
    assert snippet is not None
    assert "合同" in snippet


@pytest.mark.asyncio
async def test_global_search_returns_results_and_short_query_returns_empty(test_session) -> None:
    svc = SearchService()

    empty = await svc.global_search(test_session, "a", limit=10)
    assert empty == {"news": [], "posts": [], "lawfirms": [], "lawyers": [], "knowledge": []}

    user_id = 1

    news = News(
        title="劳动合同指南",
        summary="合同法相关",
        content="劳动合同内容",
        is_published=True,
        is_top=False,
    )
    post = Post(title="合同纠纷讨论", content="这里讨论劳动合同", user_id=user_id, is_deleted=False)
    firm = LawFirm(name="合同律所", description="专注合同纠纷", is_active=True)
    lawyer = Lawyer(name="张律师", specialties="合同", is_active=True)
    knowledge = LegalKnowledge(
        knowledge_type="law",
        title="劳动合同法",
        content="劳动合同相关条文",
        category="劳动法",
        is_active=True,
    )

    test_session.add_all([news, post, firm, lawyer, knowledge])
    await test_session.commit()

    results = await svc.global_search(test_session, "合同", limit=10)
    assert len(results["news"]) >= 1
    assert len(results["posts"]) >= 1
    assert len(results["lawfirms"]) >= 1
    assert len(results["lawyers"]) >= 1
    assert len(results["knowledge"]) >= 1


@pytest.mark.asyncio
async def test_search_suggestions_dedup_and_limit(test_session) -> None:
    svc = SearchService()

    test_session.add_all(
        [
            News(title="劳动合同指南", summary=None, content="x", is_published=True),
            News(title="劳动仲裁流程", summary=None, content="x", is_published=True),
            Post(title="劳动合同指南", content="x", user_id=1, is_deleted=False),
        ]
    )
    await test_session.commit()

    suggestions = await svc.search_suggestions(test_session, "劳", limit=2)
    assert len(suggestions) == 2
    assert suggestions[0].startswith("劳")


@pytest.mark.asyncio
async def test_hot_keywords_and_history_ops(test_session) -> None:
    svc = SearchService()

    test_session.add_all(
        [
            SearchHistory(keyword="劳动合同", user_id=1, ip_address="1.1.1.1"),
            SearchHistory(keyword="劳动合同", user_id=1, ip_address="1.1.1.1"),
            SearchHistory(keyword="离婚财产", user_id=2, ip_address="2.2.2.2"),
        ]
    )
    await test_session.commit()

    hot = await svc.get_hot_keywords(test_session, limit=10)
    assert hot
    assert hot[0]["keyword"] == "劳动合同"
    assert hot[0]["count"] == 2

    await svc.record_search(test_session, keyword="交通事故", user_id=1, ip_address="3.3.3.3")

    history = await svc.get_user_search_history(test_session, user_id=1, limit=10)
    assert "交通事故" in history

    cleared = await svc.clear_user_search_history(test_session, user_id=1)
    assert cleared is True

    history2 = await svc.get_user_search_history(test_session, user_id=1, limit=10)
    assert history2 == []
