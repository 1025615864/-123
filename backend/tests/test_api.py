"""API接口测试"""
import base64
import json
import pytest
from collections.abc import AsyncGenerator
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import cast

from _pytest.monkeypatch import MonkeyPatch


def _json_dict(res: Response) -> dict[str, object]:
    raw = cast(object, res.json())
    assert isinstance(raw, dict)
    return cast(dict[str, object], raw)


def _as_int(value: object | None, default: int = 0) -> int:
    if value is None:
        return int(default)
    if isinstance(value, bool):
        return int(default)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return int(default)
        return int(s)
    return int(default)


def _as_float(value: object | None, default: float = 0.0) -> float:
    if value is None:
        return float(default)
    if isinstance(value, bool):
        return float(default)
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return float(default)
        return float(s)
    return float(default)


def _as_list(value: object | None) -> list[object]:
    if value is None:
        return []
    if isinstance(value, list):
        return cast(list[object], value)
    return []


class TestRootAPI:
    """根路由测试"""
    
    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient):
        """测试根路由"""
        response = await client.get("/")
        assert response.status_code == 200
        data = _json_dict(response)
        assert "name" in data
        assert "version" in data


class TestUserAPI:
    """用户API测试"""
    
    @pytest.mark.asyncio
    async def test_register_user(self, client: AsyncClient):
        """测试用户注册"""
        user_data = {
            "username": "testuser",
            "email": "test@example.com",
            "password": "Test123456",
            "agree_terms": True,
            "agree_privacy": True,
            "agree_ai_disclaimer": True,
        }
        response = await client.post("/api/user/register", json=user_data)
        assert response.status_code in [200, 201, 400]
    
    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, client: AsyncClient):
        """测试无效登录"""
        login_data = {
            "username": "nonexistent@example.com",
            "password": "wrongpassword"
        }
        response = await client.post("/api/user/login", json=login_data)
        assert response.status_code == 401


class TestNewsAPI:
    """新闻API测试"""
    
    @pytest.mark.asyncio
    async def test_get_news_list(self, client: AsyncClient):
        """测试获取新闻列表"""
        response = await client.get("/api/news")
        assert response.status_code == 200
        data = _json_dict(response)
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_admin_rerun_news_ai(self, client: AsyncClient, test_session: AsyncSession, monkeypatch: MonkeyPatch):
        from sqlalchemy import select

        from app.models.news import News
        from app.models.news_ai import NewsAIAnnotation
        from app.models.user import User
        from app.services.news_ai_pipeline_service import NewsAIPipelineService
        from app.utils.security import create_access_token, hash_password

        admin = User(
            username="a_news_ai",
            email="a_news_ai@example.com",
            nickname="a_news_ai",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add(admin)
        await test_session.commit()
        await test_session.refresh(admin)

        token = create_access_token({"sub": str(admin.id)})

        news = News(
            title="单测新闻",
            summary=None,
            content="正文内容",
            category="法律动态",
            is_top=False,
            is_published=True,
            review_status="approved",
        )
        test_session.add(news)
        await test_session.commit()
        await test_session.refresh(news)

        async def fake_make_summary(
            self: object,
            _news: News,
            *,
            env_overrides: dict[str, str] | None = None,
            force_generate: bool = False,
        ):
            _ = self
            _ = env_overrides
            _ = force_generate
            return "AI摘要", True, ["要点一"], ["关键词A"]

        def fake_make_risk(self: object, _news: News):
            _ = self
            return "safe", None

        async def fake_find_duplicate_of(self: object, _db: object, _news: News):
            _ = self
            _ = _db
            return None

        monkeypatch.setattr(NewsAIPipelineService, "_make_summary", fake_make_summary, raising=True)
        monkeypatch.setattr(NewsAIPipelineService, "_make_risk", fake_make_risk, raising=True)
        monkeypatch.setattr(NewsAIPipelineService, "_find_duplicate_of", fake_find_duplicate_of, raising=True)

        res = await client.post(
            f"/api/news/admin/{int(news.id)}/ai/rerun",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert _json_dict(res).get("message") == "ok"

        ann_res = await test_session.execute(
            select(NewsAIAnnotation).where(NewsAIAnnotation.news_id == int(news.id))
        )
        ann = ann_res.scalar_one_or_none()
        assert ann is not None
        assert ann.summary == "AI摘要"
        assert ann.processed_at is not None


    @pytest.mark.asyncio
    async def test_admin_rss_sources_and_ingest_runs(self, client: AsyncClient, test_session: AsyncSession, monkeypatch: MonkeyPatch):
        from sqlalchemy import select, func
        from types import TracebackType

        from app.models.news import News, NewsSource, NewsIngestRun
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        admin = User(
            username="a_rss",
            email="a_rss@example.com",
            nickname="a_rss",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add(admin)
        await test_session.commit()
        await test_session.refresh(admin)

        token = create_access_token({"sub": str(admin.id)})

        rss_xml = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>News One</title>
      <link>https://example.com/a</link>
      <description>Summary A</description>
    </item>
    <item>
      <title>News Two</title>
      <link>https://example.com/b</link>
      <description>Summary B</description>
    </item>
  </channel>
</rss>"""

        class FakeResponse:
            status_code: int
            text: str

            def __init__(self, status_code: int, text: str):
                self.status_code = int(status_code)
                self.text = text

        class FakeAsyncClient:
            def __init__(self, *args: object, **kwargs: object):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(
                self,
                exc_type: type[BaseException] | None,
                exc: BaseException | None,
                tb: TracebackType | None,
            ) -> bool:
                return False

            async def get(self, _url: str) -> FakeResponse:
                return FakeResponse(200, rss_xml)

        import httpx as httpx_mod

        monkeypatch.setattr(httpx_mod, "AsyncClient", FakeAsyncClient, raising=True)

        res = await client.post(
            "/api/news/admin/sources",
            json={
                "name": "Test RSS",
                "feed_url": "https://example.com/rss",
                "site": "example.com",
                "category": "general",
                "is_enabled": True,
                "max_items_per_feed": 10,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        source_id_raw = _json_dict(res).get("id")
        assert isinstance(source_id_raw, int | str)
        source_id = int(source_id_raw)

        res2 = await client.get(
            "/api/news/admin/sources",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res2.status_code == 200
        items = _as_list(_json_dict(res2).get("items"))
        assert len(items) >= 1

        res3 = await client.post(
            f"/api/news/admin/sources/{source_id}/ingest/run-once",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res3.status_code == 200
        assert _json_dict(res3).get("message") == "ok"

        news_cnt_res = await test_session.execute(select(func.count(News.id)))
        assert int(news_cnt_res.scalar() or 0) >= 2

        runs_cnt_res = await test_session.execute(select(func.count(NewsIngestRun.id)))
        assert int(runs_cnt_res.scalar() or 0) >= 1

        src_res = await test_session.execute(select(NewsSource).where(NewsSource.id == int(source_id)))
        src = src_res.scalar_one_or_none()
        assert src is not None
        assert src.last_run_at is not None

        res4 = await client.get(
            f"/api/news/admin/ingest-runs?source_id={source_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res4.status_code == 200
        assert _as_int(_json_dict(res4).get("total"), 0) >= 1

        res4b = await client.get(
            f"/api/news/admin/ingest-runs?source_id={source_id}&from=2999-01-01T00:00:00Z",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res4b.status_code == 200
        assert _as_int(_json_dict(res4b).get("total"), 0) == 0

        res5 = await client.delete(
            f"/api/news/admin/sources/{source_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res5.status_code == 200

        res6 = await client.get(
            f"/api/news/admin/ingest-runs?source_id={source_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res6.status_code == 200
        assert _as_int(_json_dict(res6).get("total"), 0) == 0


class TestSystemConfigAPI:
    @pytest.mark.asyncio
    async def test_system_config_reject_openai_api_key_single(self, client: AsyncClient, test_session: AsyncSession):
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        admin = User(
            username="a_sys_cfg",
            email="a_sys_cfg@example.com",
            nickname="a_sys_cfg",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add(admin)
        await test_session.commit()
        await test_session.refresh(admin)

        token = create_access_token({"sub": str(admin.id)})

        res = await client.put(
            "/api/system/configs/openai_api_key",
            json={"key": "openai_api_key", "value": "sk-should-not-store", "category": "ai"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "Secret values must not be stored" in str(_json_dict(res).get("detail"))

    @pytest.mark.asyncio
    async def test_system_config_reject_providers_json_contains_api_key_env_suffix_single(
        self, client: AsyncClient, test_session: AsyncSession
    ):
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        admin = User(
            username="a_sys_cfg2_prod",
            email="a_sys_cfg2_prod@example.com",
            nickname="a_sys_cfg2_prod",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add(admin)
        await test_session.commit()
        await test_session.refresh(admin)

        token = create_access_token({"sub": str(admin.id)})

        providers_json = json.dumps(
            [{"name": "p1", "base_url": "http://x", "api_key": "k1", "model": "m"}],
            ensure_ascii=False,
        )
        res = await client.put(
            "/api/system/configs/news_ai_summary_llm_providers_json_prod",
            json={
                "key": "news_ai_summary_llm_providers_json_prod",
                "value": providers_json,
                "category": "news_ai",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "providers config must not include api_key" in str(_json_dict(res).get("detail")).lower()

    @pytest.mark.asyncio
    async def test_system_config_reject_providers_json_contains_api_key_single(
        self, client: AsyncClient, test_session: AsyncSession
    ):
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        admin = User(
            username="a_sys_cfg2",
            email="a_sys_cfg2@example.com",
            nickname="a_sys_cfg2",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add(admin)
        await test_session.commit()
        await test_session.refresh(admin)

        token = create_access_token({"sub": str(admin.id)})

        providers_json = json.dumps(
            [{"name": "p1", "base_url": "http://x", "api_key": "k1", "model": "m"}],
            ensure_ascii=False,
        )
        res = await client.put(
            "/api/system/configs/news_ai_summary_llm_providers_json",
            json={"key": "news_ai_summary_llm_providers_json", "value": providers_json, "category": "news_ai"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "providers config must not include api_key" in str(_json_dict(res).get("detail")).lower()

    @pytest.mark.asyncio
    async def test_system_config_reject_providers_b64_invalid_base64_single(
        self, client: AsyncClient, test_session: AsyncSession
    ):
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        admin = User(
            username="a_sys_cfg3",
            email="a_sys_cfg3@example.com",
            nickname="a_sys_cfg3",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add(admin)
        await test_session.commit()
        await test_session.refresh(admin)

        token = create_access_token({"sub": str(admin.id)})

        res = await client.put(
            "/api/system/configs/news_ai_summary_llm_providers_b64",
            json={"key": "news_ai_summary_llm_providers_b64", "value": "not-base64!!!", "category": "news_ai"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "must be valid base64" in str(_json_dict(res).get("detail")).lower()

    @pytest.mark.asyncio
    async def test_system_config_reject_providers_b64_contains_api_key_single(
        self, client: AsyncClient, test_session: AsyncSession
    ):
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        admin = User(
            username="a_sys_cfg4",
            email="a_sys_cfg4@example.com",
            nickname="a_sys_cfg4",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add(admin)
        await test_session.commit()
        await test_session.refresh(admin)

        token = create_access_token({"sub": str(admin.id)})

        decoded = json.dumps(
            [{"name": "p1", "base_url": "http://x", "api_key": "k1", "model": "m"}],
            ensure_ascii=False,
        ).encode("utf-8")
        b64 = base64.b64encode(decoded).decode("utf-8")

        res = await client.put(
            "/api/system/configs/news_ai_summary_llm_providers_b64",
            json={"key": "news_ai_summary_llm_providers_b64", "value": b64, "category": "news_ai"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "must not include api_key" in str(_json_dict(res).get("detail")).lower()

    @pytest.mark.asyncio
    async def test_system_config_reject_providers_b64_contains_api_key_env_suffix_single(
        self, client: AsyncClient, test_session: AsyncSession
    ):
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        admin = User(
            username="a_sys_cfg4_prod",
            email="a_sys_cfg4_prod@example.com",
            nickname="a_sys_cfg4_prod",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add(admin)
        await test_session.commit()
        await test_session.refresh(admin)

        token = create_access_token({"sub": str(admin.id)})

        decoded = json.dumps(
            [{"name": "p1", "base_url": "http://x", "api_key": "k1", "model": "m"}],
            ensure_ascii=False,
        ).encode("utf-8")
        b64 = base64.b64encode(decoded).decode("utf-8")

        res = await client.put(
            "/api/system/configs/news_ai_summary_llm_providers_b64_prod",
            json={
                "key": "news_ai_summary_llm_providers_b64_prod",
                "value": b64,
                "category": "news_ai",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "must not include api_key" in str(_json_dict(res).get("detail")).lower()

    @pytest.mark.asyncio
    async def test_system_config_reject_secrets_in_batch(self, client: AsyncClient, test_session: AsyncSession):
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        admin = User(
            username="a_sys_cfg5",
            email="a_sys_cfg5@example.com",
            nickname="a_sys_cfg5",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add(admin)
        await test_session.commit()
        await test_session.refresh(admin)

        token = create_access_token({"sub": str(admin.id)})

        res = await client.post(
            "/api/system/configs/batch",
            json={
                "items": [
                    {"key": "site_name", "value": "x", "category": "general"},
                    {"key": "openai_api_key", "value": "sk-should-not-store", "category": "ai"},
                ]
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "secret" in str(_json_dict(res).get("detail")).lower()

    @pytest.mark.asyncio
    async def test_system_config_reject_providers_json_contains_api_key_env_suffix_in_batch(
        self, client: AsyncClient, test_session: AsyncSession
    ):
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        admin = User(
            username="a_sys_cfg_batch_prod",
            email="a_sys_cfg_batch_prod@example.com",
            nickname="a_sys_cfg_batch_prod",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add(admin)
        await test_session.commit()
        await test_session.refresh(admin)

        token = create_access_token({"sub": str(admin.id)})

        providers_json = json.dumps(
            [{"name": "p1", "base_url": "http://x", "api_key": "k1", "model": "m"}],
            ensure_ascii=False,
        )
        res = await client.post(
            "/api/system/configs/batch",
            json={
                "items": [
                    {
                        "key": "news_ai_summary_llm_providers_json_prod",
                        "value": providers_json,
                        "category": "news_ai",
                    }
                ]
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 400
        assert "must not include api_key" in str(_json_dict(res).get("detail")).lower()


class TestForumAPI:
    """论坛API测试"""
    
    @pytest.mark.asyncio
    async def test_get_posts_list(self, client: AsyncClient):
        """测试获取帖子列表"""
        response = await client.get("/api/forum/posts")
        assert response.status_code == 200
        data = _json_dict(response)
        assert "items" in data
        assert "total" in data

    @pytest.mark.asyncio
    async def test_comment_moderation_flow(self, client: AsyncClient, test_session: AsyncSession):
        from app.models.user import User
        from app.utils.security import hash_password, create_access_token

        user = User(
            username="u_forum_mod",
            email="u_forum_mod@example.com",
            nickname="u_forum_mod",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        admin = User(
            username="a_forum_mod",
            email="a_forum_mod@example.com",
            nickname="a_forum_mod",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add_all([user, admin])
        await test_session.commit()
        await test_session.refresh(user)
        await test_session.refresh(admin)

        user_token = create_access_token({"sub": str(user.id)})
        admin_token = create_access_token({"sub": str(admin.id)})

        post_res = await client.post(
            "/api/forum/posts",
            json={"title": "t", "content": "c", "category": "general"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert post_res.status_code == 200
        post = _json_dict(post_res)
        post_id = _as_int(post.get("id"), 0)
        assert post_id > 0

        comment_res = await client.post(
            f"/api/forum/posts/{post_id}/comments",
            json={"content": "联系我 13800138000"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert comment_res.status_code == 200
        comment = _json_dict(comment_res)
        comment_id = _as_int(comment.get("id"), 0)
        assert comment_id > 0
        assert comment.get("review_status") == "pending"

        comments_before = await client.get(f"/api/forum/posts/{post_id}/comments")
        assert comments_before.status_code == 200
        comments_before_data = _json_dict(comments_before)
        assert _as_int(comments_before_data.get("total"), 0) == 0

        post_detail_before = await client.get(f"/api/forum/posts/{post_id}")
        assert post_detail_before.status_code == 200
        assert _as_int(_json_dict(post_detail_before).get("comment_count"), 0) == 0

        pending_res = await client.get(
            "/api/forum/admin/pending-comments?page=1&page_size=20",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert pending_res.status_code == 200
        pending_data = _json_dict(pending_res)
        assert _as_int(pending_data.get("total"), 0) >= 1
        pending_items = _as_list(pending_data.get("items"))
        pending_ids: set[int] = set()
        for item in pending_items:
            if isinstance(item, dict):
                pending_ids.add(_as_int(cast(dict[str, object], item).get("id"), 0))
        assert comment_id in pending_ids

        approve_res = await client.post(
            f"/api/forum/admin/comments/{comment_id}/review",
            json={"action": "approve"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert approve_res.status_code == 200

        post_detail_after = await client.get(f"/api/forum/posts/{post_id}")
        assert post_detail_after.status_code == 200
        assert _as_int(_json_dict(post_detail_after).get("comment_count"), 0) == 1

        comments_after = await client.get(f"/api/forum/posts/{post_id}/comments")
        assert comments_after.status_code == 200
        comments_after_data = _json_dict(comments_after)
        assert _as_int(comments_after_data.get("total"), 0) >= 1
        after_items = _as_list(comments_after_data.get("items"))
        ids_after: set[int] = set()
        for item in after_items:
            if isinstance(item, dict):
                ids_after.add(_as_int(cast(dict[str, object], item).get("id"), 0))
        assert comment_id in ids_after


class TestLawFirmAPI:
    """律所API测试"""
    
    @pytest.mark.asyncio
    async def test_get_lawfirms_list(self, client: AsyncClient):
        """测试获取律所列表"""
        response = await client.get("/api/lawfirm/firms")
        assert response.status_code == 200
        data = _json_dict(response)
        assert "items" in data
        assert "total" in data


class TestLawFirmConsultationsAPI:
    """律所咨询预约 API 测试"""

    @pytest.mark.asyncio
    async def test_consultation_cancel_and_permissions(self, client: AsyncClient, test_session: AsyncSession):
        from sqlalchemy import select

        from app.models.lawfirm import Lawyer, LawyerConsultation
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        user1 = User(
            username="u_lawfirm_consult_1",
            email="u_lawfirm_consult_1@example.com",
            nickname="u_lawfirm_consult_1",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        user2 = User(
            username="u_lawfirm_consult_2",
            email="u_lawfirm_consult_2@example.com",
            nickname="u_lawfirm_consult_2",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add_all([user1, user2])
        await test_session.commit()
        await test_session.refresh(user1)
        await test_session.refresh(user2)

        lawyer = Lawyer(name="律师A")
        test_session.add(lawyer)
        await test_session.commit()
        await test_session.refresh(lawyer)

        token1 = create_access_token({"sub": str(user1.id)})
        token2 = create_access_token({"sub": str(user2.id)})

        create_res = await client.post(
            "/api/lawfirm/consultations",
            json={
                "lawyer_id": int(lawyer.id),
                "subject": "我的劳动纠纷咨询",
                "contact_phone": "13800000000",
            },
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert create_res.status_code == 200
        create_data = _json_dict(create_res)
        consultation_id = _as_int(create_data.get("id"), 0)
        assert consultation_id > 0
        assert create_data.get("status") == "pending"

        list_res = await client.get(
            "/api/lawfirm/consultations",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert list_res.status_code == 200
        list_data = _json_dict(list_res)
        items = _as_list(list_data.get("items"))
        ids = {_as_int(item.get("id"), 0) for item in items if isinstance(item, dict)}
        assert consultation_id in ids

        cancel_res = await client.post(
            f"/api/lawfirm/consultations/{consultation_id}/cancel",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert cancel_res.status_code == 200
        assert _json_dict(cancel_res).get("status") == "cancelled"

        cancel_again_res = await client.post(
            f"/api/lawfirm/consultations/{consultation_id}/cancel",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert cancel_again_res.status_code == 200
        assert _json_dict(cancel_again_res).get("status") == "cancelled"

        cancel_other_user_res = await client.post(
            f"/api/lawfirm/consultations/{consultation_id}/cancel",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert cancel_other_user_res.status_code == 404

        create_res2 = await client.post(
            "/api/lawfirm/consultations",
            json={
                "lawyer_id": int(lawyer.id),
                "subject": "合同纠纷咨询",
            },
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert create_res2.status_code == 200
        consultation_id2 = _as_int(_json_dict(create_res2).get("id"), 0)
        assert consultation_id2 > 0

        c_res = await test_session.execute(
            select(LawyerConsultation).where(LawyerConsultation.id == int(consultation_id2))
        )
        c = c_res.scalar_one()
        c.status = "completed"
        test_session.add(c)
        await test_session.commit()

        cancel_completed_res = await client.post(
            f"/api/lawfirm/consultations/{consultation_id2}/cancel",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert cancel_completed_res.status_code == 400

    @pytest.mark.asyncio
    async def test_consultation_cancel_paid_balance_auto_refund_idempotent(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        from sqlalchemy import select, func

        from app.models.lawfirm import Lawyer
        from app.models.payment import PaymentOrder, UserBalance, BalanceTransaction
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        user = User(
            username="u_consult_cancel_refund",
            email="u_consult_cancel_refund@example.com",
            nickname="u_consult_cancel_refund",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        user_id = int(user.id)

        bal = UserBalance(
            user_id=user_id,
            balance=50.0,
            frozen=0.0,
            total_recharged=50.0,
            total_consumed=0.0,
        )
        test_session.add(bal)
        await test_session.commit()

        lawyer = Lawyer(name="律师退款", consultation_fee=10.0)
        test_session.add(lawyer)
        await test_session.commit()
        await test_session.refresh(lawyer)

        token = create_access_token({"sub": str(user_id)})

        create_res = await client.post(
            "/api/lawfirm/consultations",
            json={
                "lawyer_id": int(lawyer.id),
                "subject": "取消退款咨询",
                "contact_phone": "13800000000",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_res.status_code == 200
        create_data = _json_dict(create_res)
        consultation_id = _as_int(create_data.get("id"), 0)
        assert consultation_id > 0
        order_no = str(create_data.get("payment_order_no") or "").strip()
        assert order_no

        pay_res = await client.post(
            f"/api/payment/orders/{order_no}/pay",
            json={"payment_method": "balance"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pay_res.status_code == 200

        bal_before_res = await test_session.execute(
            select(UserBalance).where(UserBalance.user_id == int(user_id))
        )
        bal_before = bal_before_res.scalar_one()
        before_amount = float(bal_before.balance)

        cancel_res = await client.post(
            f"/api/lawfirm/consultations/{consultation_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert cancel_res.status_code == 200
        cancel_data = _json_dict(cancel_res)
        assert str(cancel_data.get("status")) == "cancelled"
        assert str(cancel_data.get("payment_status") or "").lower() in {"refunded", "paid"}

        order_res = await test_session.execute(
            select(PaymentOrder).where(PaymentOrder.order_no == str(order_no))
        )
        order = order_res.scalar_one()
        assert str(order.status) == "refunded"

        bal_after_res = await test_session.execute(
            select(UserBalance).where(UserBalance.user_id == int(user_id))
        )
        bal_after = bal_after_res.scalar_one()
        assert float(bal_after.balance) >= before_amount

        refund_count_res = await test_session.execute(
            select(func.count(BalanceTransaction.id)).where(
                BalanceTransaction.user_id == int(user_id),
                BalanceTransaction.order_id == int(order.id),
                BalanceTransaction.type == "refund",
            )
        )
        refund_count_1 = int(refund_count_res.scalar() or 0)
        assert refund_count_1 == 1

        cancel_res2 = await client.post(
            f"/api/lawfirm/consultations/{consultation_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert cancel_res2.status_code == 200

        refund_count_res2 = await test_session.execute(
            select(func.count(BalanceTransaction.id)).where(
                BalanceTransaction.user_id == int(user.id),
                BalanceTransaction.order_id == int(order.id),
                BalanceTransaction.type == "refund",
            )
        )
        refund_count_2 = int(refund_count_res2.scalar() or 0)
        assert refund_count_2 == 1

    @pytest.mark.asyncio
    async def test_consultation_paid_confirms(self, client: AsyncClient, test_session: AsyncSession):
        from sqlalchemy import select

        from app.models.lawfirm import Lawyer, LawyerConsultation
        from app.models.payment import UserBalance, PaymentOrder
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        user = User(
            username="u_lawfirm_pay",
            email="u_lawfirm_pay@example.com",
            nickname="u_lawfirm_pay",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        balance = UserBalance(
            user_id=user.id,
            balance=100.0,
            frozen=0.0,
            total_recharged=100.0,
            total_consumed=0.0,
        )
        test_session.add(balance)
        await test_session.commit()

        lawyer = Lawyer(name="律师付费", consultation_fee=10.0)
        test_session.add(lawyer)
        await test_session.commit()
        await test_session.refresh(lawyer)

        lawyer_user = User(
            username="u_lawyer_pay",
            email="u_lawyer_pay@example.com",
            nickname="u_lawyer_pay",
            hashed_password=hash_password("Test123456"),
            role="lawyer",
            is_active=True,
        )
        test_session.add(lawyer_user)
        await test_session.commit()
        await test_session.refresh(lawyer_user)

        lawyer.user_id = int(lawyer_user.id)
        test_session.add(lawyer)
        await test_session.commit()
        await test_session.refresh(lawyer)

        token = create_access_token({"sub": str(user.id)})

        create_res = await client.post(
            "/api/lawfirm/consultations",
            json={
                "lawyer_id": int(lawyer.id),
                "subject": "付费咨询",
                "contact_phone": "13800000000",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_res.status_code == 200
        create_data = _json_dict(create_res)
        consultation_id = _as_int(create_data.get("id"), 0)
        assert consultation_id > 0
        assert str(create_data.get("status")) == "pending"

        order_no = str(create_data.get("payment_order_no") or "").strip()
        assert order_no
        assert str(create_data.get("payment_status") or "").strip().lower() == "pending"

        pay_res = await client.post(
            f"/api/payment/orders/{order_no}/pay",
            json={"payment_method": "balance"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pay_res.status_code == 200

        list_res = await client.get(
            "/api/lawfirm/consultations?page=1&page_size=20",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert list_res.status_code == 200
        list_data = _json_dict(list_res)
        items = _as_list(list_data.get("items"))
        found = None
        for it in items:
            if isinstance(it, dict) and _as_int(it.get("id"), 0) == consultation_id:
                found = it
                break
        assert found is not None

        assert str(found.get("status") or "").lower() == "confirmed"
        assert str(found.get("payment_status") or "").lower() == "paid"

        lawyer_token = create_access_token({"sub": str(lawyer_user.id)})
        accept_res = await client.post(
            f"/api/lawfirm/lawyer/consultations/{consultation_id}/accept",
            headers={"Authorization": f"Bearer {lawyer_token}"},
        )
        assert accept_res.status_code == 200
        accept_data = _json_dict(accept_res)
        assert str(accept_data.get("status") or "").lower() == "confirmed"

        c_res = await test_session.execute(
            select(LawyerConsultation).where(LawyerConsultation.id == int(consultation_id))
        )
        c = c_res.scalar_one()
        assert c.status == "confirmed"

        o_res = await test_session.execute(
            select(PaymentOrder).where(PaymentOrder.order_no == order_no)
        )
        o = o_res.scalar_one()
        assert o.status == "paid"


class TestLawFirmConsultationMessagesAPI:
    """律所咨询留言 API 测试"""

    @pytest.mark.asyncio
    async def test_consultation_messages_permissions_and_flow(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        from sqlalchemy import select

        from app.models.lawfirm import Lawyer, LawyerConsultationMessage
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        user1 = User(
            username="u_lawfirm_msg_1",
            email="u_lawfirm_msg_1@example.com",
            nickname="u_lawfirm_msg_1",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        user2 = User(
            username="u_lawfirm_msg_2",
            email="u_lawfirm_msg_2@example.com",
            nickname="u_lawfirm_msg_2",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        lawyer_user = User(
            username="u_lawfirm_msg_lawyer",
            email="u_lawfirm_msg_lawyer@example.com",
            nickname="u_lawfirm_msg_lawyer",
            hashed_password=hash_password("Test123456"),
            role="lawyer",
            is_active=True,
        )
        test_session.add_all([user1, user2, lawyer_user])
        await test_session.commit()
        await test_session.refresh(user1)
        await test_session.refresh(user2)
        await test_session.refresh(lawyer_user)

        lawyer = Lawyer(name="律师留言", consultation_fee=0.0, user_id=int(lawyer_user.id))
        test_session.add(lawyer)
        await test_session.commit()
        await test_session.refresh(lawyer)

        token1 = create_access_token({"sub": str(user1.id)})
        token2 = create_access_token({"sub": str(user2.id)})
        token_lawyer = create_access_token({"sub": str(lawyer_user.id)})

        create_res = await client.post(
            "/api/lawfirm/consultations",
            json={
                "lawyer_id": int(lawyer.id),
                "subject": "留言测试咨询",
                "contact_phone": "13800000000",
            },
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert create_res.status_code == 200
        consultation_id = _as_int(_json_dict(create_res).get("id"), 0)
        assert consultation_id > 0

        send_res = await client.post(
            f"/api/lawfirm/consultations/{consultation_id}/messages",
            json={"content": "hello"},
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert send_res.status_code == 200
        send_data = _json_dict(send_res)
        assert str(send_data.get("content")) == "hello"
        assert str(send_data.get("sender_role")) == "user"

        list_res_user = await client.get(
            f"/api/lawfirm/consultations/{consultation_id}/messages?page=1&page_size=50",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert list_res_user.status_code == 200
        list_data_user = _json_dict(list_res_user)
        assert _as_int(list_data_user.get("total"), 0) >= 1

        list_res_other = await client.get(
            f"/api/lawfirm/consultations/{consultation_id}/messages?page=1&page_size=50",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert list_res_other.status_code == 404

        list_res_lawyer = await client.get(
            f"/api/lawfirm/consultations/{consultation_id}/messages?page=1&page_size=50",
            headers={"Authorization": f"Bearer {token_lawyer}"},
        )
        assert list_res_lawyer.status_code == 200

        reply_res = await client.post(
            f"/api/lawfirm/consultations/{consultation_id}/messages",
            json={"content": "reply"},
            headers={"Authorization": f"Bearer {token_lawyer}"},
        )
        assert reply_res.status_code == 200
        reply_data = _json_dict(reply_res)
        assert str(reply_data.get("content")) == "reply"
        assert str(reply_data.get("sender_role")) == "lawyer"

        db_res = await test_session.execute(
            select(LawyerConsultationMessage).where(
                LawyerConsultationMessage.consultation_id == int(consultation_id)
            )
        )
        assert len(list(db_res.scalars().all())) >= 2


class TestLawFirmReviewsAPI:
    """律所评价 API 测试"""

    @pytest.mark.asyncio
    async def test_review_requires_completed_and_unique_per_consultation(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        from sqlalchemy import select

        from app.models.lawfirm import Lawyer, LawyerConsultation, LawyerReview
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        user1 = User(
            username="u_lawfirm_review_1",
            email="u_lawfirm_review_1@example.com",
            nickname="u_lawfirm_review_1",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        user2 = User(
            username="u_lawfirm_review_2",
            email="u_lawfirm_review_2@example.com",
            nickname="u_lawfirm_review_2",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add_all([user1, user2])
        await test_session.commit()
        await test_session.refresh(user1)
        await test_session.refresh(user2)

        lawyer = Lawyer(name="律师评价", consultation_fee=0.0)
        test_session.add(lawyer)
        await test_session.commit()
        await test_session.refresh(lawyer)

        token1 = create_access_token({"sub": str(user1.id)})
        token2 = create_access_token({"sub": str(user2.id)})

        create_res = await client.post(
            "/api/lawfirm/consultations",
            json={
                "lawyer_id": int(lawyer.id),
                "subject": "评价测试咨询",
                "contact_phone": "13800000000",
            },
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert create_res.status_code == 200
        consultation_id = _as_int(_json_dict(create_res).get("id"), 0)
        assert consultation_id > 0

        # pending 状态不能评价
        bad_res = await client.post(
            "/api/lawfirm/reviews",
            json={
                "lawyer_id": int(lawyer.id),
                "consultation_id": int(consultation_id),
                "rating": 5,
                "content": "不错",
            },
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert bad_res.status_code == 400

        c_res = await test_session.execute(
            select(LawyerConsultation).where(LawyerConsultation.id == int(consultation_id))
        )
        c = c_res.scalar_one()
        c.status = "completed"
        test_session.add(c)
        await test_session.commit()

        list_before = await client.get(
            "/api/lawfirm/consultations?page=1&page_size=50",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert list_before.status_code == 200
        before_items = _as_list(_json_dict(list_before).get("items"))
        found_before = None
        for it in before_items:
            if isinstance(it, dict) and _as_int(it.get("id"), 0) == consultation_id:
                found_before = it
                break
        assert found_before is not None
        assert bool(found_before.get("can_review")) is True

        ok_res = await client.post(
            "/api/lawfirm/reviews",
            json={
                "lawyer_id": int(lawyer.id),
                "consultation_id": int(consultation_id),
                "rating": 5,
                "content": "不错",
            },
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert ok_res.status_code == 200
        review_id = _as_int(_json_dict(ok_res).get("id"), 0)
        assert review_id > 0

        dup_res = await client.post(
            "/api/lawfirm/reviews",
            json={
                "lawyer_id": int(lawyer.id),
                "consultation_id": int(consultation_id),
                "rating": 5,
                "content": "重复",
            },
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert dup_res.status_code == 400

        other_res = await client.post(
            "/api/lawfirm/reviews",
            json={
                "lawyer_id": int(lawyer.id),
                "consultation_id": int(consultation_id),
                "rating": 4,
                "content": "越权",
            },
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert other_res.status_code == 404

        list_after = await client.get(
            "/api/lawfirm/consultations?page=1&page_size=50",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert list_after.status_code == 200
        after_items = _as_list(_json_dict(list_after).get("items"))
        found_after = None
        for it in after_items:
            if isinstance(it, dict) and _as_int(it.get("id"), 0) == consultation_id:
                found_after = it
                break
        assert found_after is not None
        assert bool(found_after.get("can_review")) is False
        assert _as_int(found_after.get("review_id"), 0) == review_id

        r_res = await test_session.execute(
            select(LawyerReview).where(LawyerReview.id == int(review_id))
        )
        assert r_res.scalar_one_or_none() is not None


class TestPaymentAPI:
    """支付API测试"""

    @pytest.mark.asyncio
    async def test_alipay_rsa2_notify_callback(self, client: AsyncClient, test_session: AsyncSession, monkeypatch: MonkeyPatch):
        from app.models.user import User
        from app.models.payment import UserBalance
        from app.utils.security import hash_password, create_access_token

        user = User(
            username="u_payment_test",
            email="u_payment_test@example.com",
            nickname="u_payment_test",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        balance = UserBalance(
            user_id=user.id,
            balance=100.0,
            frozen=0.0,
            total_recharged=100.0,
            total_consumed=0.0,
        )
        test_session.add(balance)
        await test_session.commit()

        token = create_access_token({"sub": str(user.id)})

        create_res = await client.post(
            "/api/payment/orders",
            json={"order_type": "service", "amount": 10.0, "title": "t"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_res.status_code == 200
        order_no = str(create_res.json()["order_no"])

        pay_res = await client.post(
            f"/api/payment/orders/{order_no}/pay",
            json={"payment_method": "balance"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pay_res.status_code == 200
        assert _json_dict(pay_res).get("trade_no")

        detail_res = await client.get(
            f"/api/payment/orders/{order_no}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail_res.status_code == 200
        assert _json_dict(detail_res).get("status") == "paid"

    @pytest.mark.asyncio
    async def test_wechat_notify_ai_pack_document_generate_grants_credits_idempotent(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        import base64
        import json
        import time
        from datetime import datetime, timedelta

        from sqlalchemy import select, func

        from app.models.user import User
        from app.models.system import SystemConfig
        from app.models.payment import PaymentCallbackEvent
        from app.models.user_quota import UserQuotaPackBalance
        from app.routers import payment as payment_router
        from app.utils.security import hash_password, create_access_token

        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography import x509
        from cryptography.x509.oid import NameOID

        from app.utils.wechatpay_v3 import WeChatPayPlatformCert, dump_platform_certs_json

        user = User(
            username="u_wechat_ai_pack_test",
            email="u_wechat_ai_pack_test@example.com",
            nickname="u_wechat_ai_pack_test",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        user_id = int(user.id)

        token = create_access_token({"sub": str(user_id)})

        create_res = await client.post(
            "/api/payment/orders",
            json={
                "order_type": "ai_pack",
                "amount": 0.01,
                "title": "t",
                "description": "d",
                "related_id": 10,
                "related_type": "document_generate",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_res.status_code == 200
        order_no = str(create_res.json()["order_no"])

        api_v3_key = "0123456789abcdef0123456789abcdef"
        payment_router.settings.wechatpay_api_v3_key = api_v3_key

        platform_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, "wx-platform")]
        )
        cert_obj = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(platform_private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow() - timedelta(days=1))
            .not_valid_after(datetime.utcnow() + timedelta(days=365))
            .sign(platform_private_key, hashes.SHA256())
        )
        cert_pem = cert_obj.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        serial_no = "TEST_SERIAL_PACK_1"
        cfg_json = dump_platform_certs_json([WeChatPayPlatformCert(serial_no=serial_no, pem=cert_pem)])
        test_session.add(SystemConfig(key="WECHATPAY_PLATFORM_CERTS_JSON", value=cfg_json, category="payment"))
        await test_session.commit()

        trade_no = "WX_T_PACK_1"
        resource_plain = {
            "out_trade_no": order_no,
            "transaction_id": trade_no,
            "trade_state": "SUCCESS",
            "amount": {"total": 1200},
        }
        resource_plain_bytes = json.dumps(resource_plain, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        resource_nonce = "0123456789ab"
        resource_ad = "transaction"
        aesgcm = AESGCM(api_v3_key.encode("utf-8"))
        cipher = aesgcm.encrypt(resource_nonce.encode("utf-8"), resource_plain_bytes, resource_ad.encode("utf-8"))
        resource_ciphertext = base64.b64encode(cipher).decode("utf-8")

        body_obj = {
            "id": "EVT_PACK_1",
            "create_time": "2020-01-01T00:00:00+08:00",
            "resource_type": "encrypt-resource",
            "event_type": "TRANSACTION.SUCCESS",
            "summary": "ok",
            "resource": {
                "algorithm": "AEAD_AES_256_GCM",
                "nonce": resource_nonce,
                "associated_data": resource_ad,
                "ciphertext": resource_ciphertext,
            },
        }
        body_bytes = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        ts = str(int(time.time()))
        header_nonce = "HDRNONCE_PACK_1"
        msg = ts.encode("utf-8") + b"\n" + header_nonce.encode("utf-8") + b"\n" + body_bytes + b"\n"
        sig = platform_private_key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
        sig_b64 = base64.b64encode(sig).decode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Wechatpay-Serial": serial_no,
            "Wechatpay-Timestamp": ts,
            "Wechatpay-Nonce": header_nonce,
            "Wechatpay-Signature": sig_b64,
            "Wechatpay-Signature-Type": "WECHATPAY2-SHA256-RSA2048",
        }

        res1 = await client.post("/api/payment/wechat/notify", content=body_bytes, headers=headers)
        assert res1.status_code == 200

        res2 = await client.post("/api/payment/wechat/notify", content=body_bytes, headers=headers)
        assert res2.status_code == 200

        evt_count_res = await test_session.execute(
            select(func.count(PaymentCallbackEvent.id)).where(
                PaymentCallbackEvent.provider == "wechat",
                PaymentCallbackEvent.trade_no == trade_no,
            )
        )
        assert int(evt_count_res.scalar() or 0) == 1

        bal_res = await test_session.execute(
            select(UserQuotaPackBalance).where(UserQuotaPackBalance.user_id == int(user_id))
        )
        bal = bal_res.scalar_one_or_none()
        assert bal is not None
        assert int(getattr(bal, "document_generate_credits", 0)) == 10


class TestQuotaPackAPI:
    @pytest.mark.asyncio
    async def test_ai_pack_balance_payment_grants_credits_and_reflected_in_quotas(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        from sqlalchemy import select

        from app.models.user import User
        from app.models.payment import UserBalance
        from app.models.user_quota import UserQuotaPackBalance
        from app.utils.security import hash_password, create_access_token

        user = User(
            username="u_ai_pack_pay",
            email="u_ai_pack_pay@example.com",
            nickname="u_ai_pack_pay",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        balance = UserBalance(
            user_id=user.id,
            balance=1000.0,
            frozen=0.0,
            total_recharged=1000.0,
            total_consumed=0.0,
        )
        test_session.add(balance)
        await test_session.commit()

        token = create_access_token({"sub": str(user.id)})

        create_res = await client.post(
            "/api/payment/orders",
            json={
                "order_type": "ai_pack",
                "amount": 0.01,
                "title": "t",
                "description": "d",
                "related_id": 10,
                "related_type": "ai_chat",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_res.status_code == 200
        order_no = str(create_res.json()["order_no"])

        pay_res = await client.post(
            f"/api/payment/orders/{order_no}/pay",
            json={"payment_method": "balance"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pay_res.status_code == 200

        bal_res = await test_session.execute(
            select(UserQuotaPackBalance).where(UserQuotaPackBalance.user_id == int(user.id))
        )
        bal = bal_res.scalar_one_or_none()
        assert bal is not None
        assert int(getattr(bal, "ai_chat_credits", 0)) >= 10

        quota_res = await client.get(
            "/api/user/me/quotas",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert quota_res.status_code == 200
        q = _json_dict(quota_res)
        assert _as_int(q.get("ai_chat_pack_remaining"), 0) >= 10

    @pytest.mark.asyncio
    async def test_document_pack_balance_payment_grants_credits_and_reflected_in_quotas(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        from sqlalchemy import select

        from app.models.user import User
        from app.models.payment import UserBalance
        from app.models.user_quota import UserQuotaPackBalance
        from app.utils.security import hash_password, create_access_token

        user = User(
            username="u_doc_pack_pay",
            email="u_doc_pack_pay@example.com",
            nickname="u_doc_pack_pay",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        balance = UserBalance(
            user_id=user.id,
            balance=1000.0,
            frozen=0.0,
            total_recharged=1000.0,
            total_consumed=0.0,
        )
        test_session.add(balance)
        await test_session.commit()

        token = create_access_token({"sub": str(user.id)})

        create_res = await client.post(
            "/api/payment/orders",
            json={
                "order_type": "ai_pack",
                "amount": 0.01,
                "title": "t",
                "description": "d",
                "related_id": 10,
                "related_type": "document_generate",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_res.status_code == 200
        order_no = str(create_res.json()["order_no"])

        pay_res = await client.post(
            f"/api/payment/orders/{order_no}/pay",
            json={"payment_method": "balance"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pay_res.status_code == 200

        bal_res = await test_session.execute(
            select(UserQuotaPackBalance).where(UserQuotaPackBalance.user_id == int(user.id))
        )
        bal = bal_res.scalar_one_or_none()
        assert bal is not None
        assert int(getattr(bal, "document_generate_credits", 0)) >= 10

        quota_res = await client.get(
            "/api/user/me/quotas",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert quota_res.status_code == 200
        q = _json_dict(quota_res)
        assert _as_int(q.get("document_generate_pack_remaining"), 0) >= 10

    @pytest.mark.asyncio
    async def test_ai_chat_consumes_pack_credits_when_daily_exhausted(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch: MonkeyPatch,
    ):
        from datetime import date

        from sqlalchemy import select

        from app.models.user import User
        from app.models.user_quota import UserQuotaDaily, UserQuotaPackBalance
        from app.services.quota_service import FREE_AI_CHAT_DAILY_LIMIT
        from app.utils.security import create_access_token, hash_password

        import app.routers.ai as ai_router

        monkeypatch.setattr(ai_router.settings, "openai_api_key", "test", raising=True)

        user = User(
            username="u_ai_pack_consume",
            email="u_ai_pack_consume@example.com",
            nickname="u_ai_pack_consume",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        today = date.today()
        test_session.add(
            UserQuotaDaily(
                user_id=int(user.id),
                day=today,
                ai_chat_count=int(FREE_AI_CHAT_DAILY_LIMIT),
                document_generate_count=0,
            )
        )
        test_session.add(
            UserQuotaPackBalance(
                user_id=int(user.id),
                ai_chat_credits=1,
                document_generate_credits=0,
            )
        )
        await test_session.commit()

        token = create_access_token({"sub": str(user.id)})

        class FakeAssistant:
            async def chat(
                self,
                *,
                message: str,
                session_id: str | None = None,
                initial_history: list[dict[str, str]] | None = None,
            ) -> tuple[str, str, list[object]]:
                _ = message
                _ = initial_history
                return (session_id or "s_pack_1"), "OK", []

        monkeypatch.setattr(ai_router, "_try_get_ai_assistant", lambda: FakeAssistant(), raising=True)

        res = await client.post(
            "/api/ai/chat",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200

        bal_res = await test_session.execute(
            select(UserQuotaPackBalance).where(UserQuotaPackBalance.user_id == int(user.id))
        )
        bal = bal_res.scalar_one_or_none()
        assert bal is not None
        assert int(getattr(bal, "ai_chat_credits", 0)) == 0

    @pytest.mark.asyncio
    async def test_document_generate_consumes_pack_credits_when_daily_exhausted(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        from datetime import date

        from sqlalchemy import select

        from app.models.user import User
        from app.models.user_quota import UserQuotaDaily, UserQuotaPackBalance
        from app.services.quota_service import FREE_DOCUMENT_GENERATE_DAILY_LIMIT
        from app.utils.security import create_access_token, hash_password

        user = User(
            username="u_doc_pack_consume",
            email="u_doc_pack_consume@example.com",
            nickname="u_doc_pack_consume",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        today = date.today()
        test_session.add(
            UserQuotaDaily(
                user_id=int(user.id),
                day=today,
                ai_chat_count=0,
                document_generate_count=int(FREE_DOCUMENT_GENERATE_DAILY_LIMIT),
            )
        )
        test_session.add(
            UserQuotaPackBalance(
                user_id=int(user.id),
                ai_chat_credits=0,
                document_generate_credits=1,
            )
        )
        await test_session.commit()

        token = create_access_token({"sub": str(user.id)})

        res = await client.post(
            "/api/documents/generate",
            json={
                "document_type": "complaint",
                "case_type": "合同纠纷",
                "plaintiff_name": "A",
                "defendant_name": "B",
                "facts": "f",
                "claims": "c",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200

        bal_res = await test_session.execute(
            select(UserQuotaPackBalance).where(UserQuotaPackBalance.user_id == int(user.id))
        )
        bal = bal_res.scalar_one_or_none()
        assert bal is not None
        assert int(getattr(bal, "document_generate_credits", 0)) == 0


class TestPaymentWeChatNotifyAPI:

    @pytest.mark.asyncio
    async def test_wechat_notify_marks_order_paid_and_records_event_idempotent(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        import base64
        import json
        import time
        from sqlalchemy import select, func

        from app.models.user import User
        from app.models.system import SystemConfig
        from app.models.payment import PaymentCallbackEvent
        from app.routers import payment as payment_router
        from app.utils.security import hash_password, create_access_token

        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from datetime import datetime, timedelta

        from app.utils.wechatpay_v3 import WeChatPayPlatformCert, dump_platform_certs_json

        user = User(
            username="u_wechat_notify_test",
            email="u_wechat_notify_test@example.com",
            nickname="u_wechat_notify_test",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        token = create_access_token({"sub": str(user.id)})

        create_res = await client.post(
            "/api/payment/orders",
            json={"order_type": "service", "amount": 10.0, "title": "svc"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_res.status_code == 200
        order_no = str(create_res.json()["order_no"])

        api_v3_key = "0123456789abcdef0123456789abcdef"
        payment_router.settings.wechatpay_api_v3_key = api_v3_key

        platform_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, "wx-platform")]
        )
        cert_obj = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(platform_private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow() - timedelta(days=1))
            .not_valid_after(datetime.utcnow() + timedelta(days=365))
            .sign(platform_private_key, hashes.SHA256())
        )
        cert_pem = cert_obj.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        serial_no = "TEST_SERIAL_1"
        cfg_json = dump_platform_certs_json([WeChatPayPlatformCert(serial_no=serial_no, pem=cert_pem)])
        test_session.add(SystemConfig(key="WECHATPAY_PLATFORM_CERTS_JSON", value=cfg_json, category="payment"))
        await test_session.commit()

        trade_no = "WX_T_1"
        resource_plain = {
            "out_trade_no": order_no,
            "transaction_id": trade_no,
            "trade_state": "SUCCESS",
            "amount": {"total": 1000},
        }
        resource_plain_bytes = json.dumps(resource_plain, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        resource_nonce = "0123456789ab"
        resource_ad = "transaction"
        aesgcm = AESGCM(api_v3_key.encode("utf-8"))
        cipher = aesgcm.encrypt(resource_nonce.encode("utf-8"), resource_plain_bytes, resource_ad.encode("utf-8"))
        resource_ciphertext = base64.b64encode(cipher).decode("utf-8")

        body_obj = {
            "id": "EVT_1",
            "create_time": "2020-01-01T00:00:00+08:00",
            "resource_type": "encrypt-resource",
            "event_type": "TRANSACTION.SUCCESS",
            "summary": "ok",
            "resource": {
                "algorithm": "AEAD_AES_256_GCM",
                "nonce": resource_nonce,
                "associated_data": resource_ad,
                "ciphertext": resource_ciphertext,
            },
        }
        body_bytes = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

        ts = str(int(time.time()))
        header_nonce = "HDRNONCE_123"
        msg = ts.encode("utf-8") + b"\n" + header_nonce.encode("utf-8") + b"\n" + body_bytes + b"\n"
        sig = platform_private_key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
        sig_b64 = base64.b64encode(sig).decode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Wechatpay-Serial": serial_no,
            "Wechatpay-Timestamp": ts,
            "Wechatpay-Nonce": header_nonce,
            "Wechatpay-Signature": sig_b64,
            "Wechatpay-Signature-Type": "WECHATPAY2-SHA256-RSA2048",
        }

        res1 = await client.post("/api/payment/wechat/notify", content=body_bytes, headers=headers)
        assert res1.status_code == 200

        res2 = await client.post("/api/payment/wechat/notify", content=body_bytes, headers=headers)
        assert res2.status_code == 200

        evt_count_res = await test_session.execute(
            select(func.count(PaymentCallbackEvent.id)).where(
                PaymentCallbackEvent.provider == "wechat",
                PaymentCallbackEvent.trade_no == trade_no,
            )
        )
        assert int(evt_count_res.scalar() or 0) == 1

        detail_res = await client.get(
            f"/api/payment/orders/{order_no}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail_res.status_code == 200
        assert _json_dict(detail_res).get("status") == "paid"


class TestPaymentCallbackAdminAPI:
    """支付回调审计 API 测试"""

    @pytest.mark.asyncio
    async def test_admin_callback_events_list_and_stats(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        from app.models.user import User
        from app.utils.security import hash_password, create_access_token

        admin = User(
            username="a_cb_evt",
            email="a_cb_evt@example.com",
            nickname="a_cb_evt",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add(admin)
        await test_session.commit()
        await test_session.refresh(admin)

        admin_token = create_access_token({"sub": str(admin.id)})

        list_res = await client.get(
            "/api/payment/admin/callback-events?page=1&page_size=50",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert list_res.status_code == 200
        data = _json_dict(list_res)
        assert "items" in data
        assert "total" in data

        stats_res = await client.get(
            "/api/payment/admin/callback-events/stats?minutes=60",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert stats_res.status_code == 200
        stats = _json_dict(stats_res)
        assert "all_total" in stats
        assert "window_total" in stats

    @pytest.mark.asyncio
    async def test_admin_reconcile_order_amount_mismatch(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch: MonkeyPatch,
    ):
        import base64
        import json
        import time
        from datetime import datetime, timedelta

        from cryptography.hazmat.primitives.asymmetric import rsa, padding
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from cryptography import x509
        from cryptography.x509.oid import NameOID

        from app.models.user import User
        from app.models.system import SystemConfig
        from app.routers import payment as payment_router
        from app.utils.security import hash_password, create_access_token
        from app.utils.wechatpay_v3 import WeChatPayPlatformCert, dump_platform_certs_json

        admin = User(
            username="a_reconcile",
            email="a_reconcile@example.com",
            nickname="a_reconcile",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        user = User(
            username="u_reconcile",
            email="u_reconcile@example.com",
            nickname="u_reconcile",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add_all([admin, user])
        await test_session.commit()
        await test_session.refresh(admin)
        await test_session.refresh(user)

        admin_token = create_access_token({"sub": str(admin.id)})
        user_token = create_access_token({"sub": str(user.id)})

        create_res = await client.post(
            "/api/payment/orders",
            json={"order_type": "service", "amount": 10.0, "title": "svc"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert create_res.status_code == 200
        order_no = str(create_res.json()["order_no"])

        api_v3_key = "0123456789abcdef0123456789abcdef"
        payment_router.settings.wechatpay_api_v3_key = api_v3_key

        platform_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = issuer = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, "wx-platform")]
        )
        cert_obj = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(platform_private_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(datetime.utcnow() - timedelta(days=1))
            .not_valid_after(datetime.utcnow() + timedelta(days=365))
            .sign(platform_private_key, hashes.SHA256())
        )
        cert_pem = cert_obj.public_bytes(serialization.Encoding.PEM).decode("utf-8")
        serial_no = "TEST_SERIAL_2"
        cfg_json = dump_platform_certs_json([WeChatPayPlatformCert(serial_no=serial_no, pem=cert_pem)])
        test_session.add(SystemConfig(key="WECHATPAY_PLATFORM_CERTS_JSON", value=cfg_json, category="payment"))
        await test_session.commit()

        trade_no = "WX_M_1"
        resource_plain = {
            "out_trade_no": order_no,
            "transaction_id": trade_no,
            "trade_state": "SUCCESS",
            "amount": {"total": 1100},
        }
        resource_plain_bytes = json.dumps(resource_plain, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        resource_nonce = "0123456789ab"
        resource_ad = "transaction"
        aesgcm = AESGCM(api_v3_key.encode("utf-8"))
        cipher = aesgcm.encrypt(resource_nonce.encode("utf-8"), resource_plain_bytes, resource_ad.encode("utf-8"))
        resource_ciphertext = base64.b64encode(cipher).decode("utf-8")

        body_obj = {
            "id": "EVT_2",
            "create_time": "2020-01-01T00:00:00+08:00",
            "resource_type": "encrypt-resource",
            "event_type": "TRANSACTION.SUCCESS",
            "summary": "ok",
            "resource": {
                "algorithm": "AEAD_AES_256_GCM",
                "nonce": resource_nonce,
                "associated_data": resource_ad,
                "ciphertext": resource_ciphertext,
            },
        }
        body_bytes = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ts = str(int(time.time()))
        header_nonce = "HDRNONCE_456"
        msg = ts.encode("utf-8") + b"\n" + header_nonce.encode("utf-8") + b"\n" + body_bytes + b"\n"
        sig = platform_private_key.sign(msg, padding.PKCS1v15(), hashes.SHA256())
        sig_b64 = base64.b64encode(sig).decode("utf-8")

        headers = {
            "Content-Type": "application/json",
            "Wechatpay-Serial": serial_no,
            "Wechatpay-Timestamp": ts,
            "Wechatpay-Nonce": header_nonce,
            "Wechatpay-Signature": sig_b64,
            "Wechatpay-Signature-Type": "WECHATPAY2-SHA256-RSA2048",
        }

        notify_res = await client.post("/api/payment/wechat/notify", content=body_bytes, headers=headers)
        assert notify_res.status_code == 200

        recon_res = await client.get(
            f"/api/payment/admin/reconcile/{order_no}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert recon_res.status_code == 200
        recon = _json_dict(recon_res)
        assert recon.get("diagnosis") == "amount_mismatch"
        assert "recent_events" in recon

    @pytest.mark.asyncio
    async def test_admin_refresh_wechat_platform_certs_monkeypatch(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch: MonkeyPatch,
    ):
        from app.models.user import User
        from app.routers import payment as payment_router
        from app.utils.security import hash_password, create_access_token

        from app.utils.wechatpay_v3 import WeChatPayPlatformCert

        admin = User(
            username="a_wx_cert",
            email="a_wx_cert@example.com",
            nickname="a_wx_cert",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add(admin)
        await test_session.commit()
        await test_session.refresh(admin)

        admin_token = create_access_token({"sub": str(admin.id)})

        payment_router.settings.wechatpay_mch_id = "mch"
        payment_router.settings.wechatpay_mch_serial_no = "serial"
        payment_router.settings.wechatpay_private_key = "key"
        payment_router.settings.wechatpay_api_v3_key = "0123456789abcdef0123456789abcdef"

        async def _fake_fetch(**_kwargs):
            return [WeChatPayPlatformCert(serial_no="SER1", pem="-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n")]

        monkeypatch.setattr(payment_router, "fetch_platform_certificates", _fake_fetch)

        refresh_res = await client.post(
            "/api/payment/admin/wechat/platform-certs/refresh",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert refresh_res.status_code == 200

        list_res = await client.get(
            "/api/payment/admin/wechat/platform-certs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert list_res.status_code == 200

    @pytest.mark.asyncio
    async def test_admin_payment_channel_status(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch: MonkeyPatch,
    ):
        from app.models.user import User
        from app.routers import payment as payment_router
        from app.utils.security import hash_password, create_access_token

        admin = User(
            username="a_pay_status",
            email="a_pay_status@example.com",
            nickname="a_pay_status",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add(admin)
        await test_session.commit()
        await test_session.refresh(admin)

        admin_token = create_access_token({"sub": str(admin.id)})

        monkeypatch.setattr(payment_router.settings, "alipay_app_id", "", raising=False)
        monkeypatch.setattr(payment_router.settings, "alipay_public_key", "", raising=False)
        monkeypatch.setattr(payment_router.settings, "wechatpay_mch_id", "", raising=False)
        monkeypatch.setattr(payment_router.settings, "wechatpay_mch_serial_no", "", raising=False)
        monkeypatch.setattr(payment_router.settings, "wechatpay_private_key", "", raising=False)
        monkeypatch.setattr(payment_router.settings, "wechatpay_api_v3_key", "", raising=False)

        res = await client.get(
            "/api/payment/admin/channel-status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert res.status_code == 200
        data = _json_dict(res)
        assert "alipay_configured" in data
        assert "wechatpay_configured" in data
        assert "wechatpay_platform_certs_total" in data

    @pytest.mark.asyncio
    async def test_admin_import_wechat_platform_certs_json(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        from app.models.user import User
        from app.utils.security import hash_password, create_access_token
        from app.utils.wechatpay_v3 import WeChatPayPlatformCert, dump_platform_certs_json

        admin = User(
            username="a_wx_import",
            email="a_wx_import@example.com",
            nickname="a_wx_import",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add(admin)
        await test_session.commit()
        await test_session.refresh(admin)

        admin_token = create_access_token({"sub": str(admin.id)})

        raw = dump_platform_certs_json(
            [
                WeChatPayPlatformCert(
                    serial_no="SER_IMPORT_1",
                    pem="-----BEGIN CERTIFICATE-----\nMIIB\n-----END CERTIFICATE-----\n",
                    expire_time="2099-01-01T00:00:00+00:00",
                )
            ]
        )

        import_res = await client.post(
            "/api/payment/admin/wechat/platform-certs/import",
            json={"platform_certs_json": raw, "merge": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert import_res.status_code == 200

        list_res = await client.get(
            "/api/payment/admin/wechat/platform-certs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert list_res.status_code == 200
        payload = _json_dict(list_res)
        assert _as_int(payload.get("total"), 0) >= 1

    @pytest.mark.asyncio
    async def test_alipay_notify_marks_order_paid_and_records_event_idempotent(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch: MonkeyPatch,
    ):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from sqlalchemy import select, func

        from app.models.user import User
        from app.models.payment import PaymentOrder, PaymentCallbackEvent
        from app.routers import payment as payment_router
        from app.utils.security import hash_password, create_access_token

        user = User(
            username="u_alipay_notify_test",
            email="u_alipay_notify_test@example.com",
            nickname="u_alipay_notify_test",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        token = create_access_token({"sub": str(user.id)})

        create_res = await client.post(
            "/api/payment/orders",
            json={"order_type": "service", "amount": 10.0, "title": "svc"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_res.status_code == 200
        order_no = str(create_res.json()["order_no"])

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        monkeypatch.setattr(payment_router.settings, "alipay_public_key", public_pem, raising=False)
        monkeypatch.setattr(payment_router.settings, "alipay_app_id", "test_app", raising=False)

        trade_no = "ALI_T_1"
        params = {
            "app_id": "test_app",
            "out_trade_no": order_no,
            "trade_no": trade_no,
            "total_amount": "10.00",
            "trade_status": "TRADE_SUCCESS",
            "sign_type": "RSA2",
            "charset": "utf-8",
        }
        params["sign"] = payment_router._alipay_sign_rsa2(params, private_pem)

        notify_res = await client.post("/api/payment/alipay/notify", data=params)
        assert notify_res.status_code == 200
        assert notify_res.text.strip() == "success"

        detail_res = await client.get(
            f"/api/payment/orders/{order_no}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail_res.status_code == 200
        assert _json_dict(detail_res).get("status") == "paid"
        assert _json_dict(detail_res).get("payment_method") == "alipay"

        order_db_res = await test_session.execute(
            select(PaymentOrder).where(PaymentOrder.order_no == order_no)
        )
        order_db = order_db_res.scalar_one_or_none()
        assert order_db is not None
        assert str(order_db.trade_no or "") == trade_no

        evt_count_res = await test_session.execute(
            select(func.count(PaymentCallbackEvent.id)).where(
                PaymentCallbackEvent.provider == "alipay",
                PaymentCallbackEvent.trade_no == trade_no,
            )
        )
        assert int(evt_count_res.scalar() or 0) == 1

        notify_res2 = await client.post("/api/payment/alipay/notify", data=params)
        assert notify_res2.status_code == 200
        assert notify_res2.text.strip() == "success"

        evt_count_res2 = await test_session.execute(
            select(func.count(PaymentCallbackEvent.id)).where(
                PaymentCallbackEvent.provider == "alipay",
                PaymentCallbackEvent.trade_no == trade_no,
            )
        )
        assert int(evt_count_res2.scalar() or 0) == 1

    @pytest.mark.asyncio
    async def test_alipay_notify_invalid_signature_records_event_and_keeps_pending(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch: MonkeyPatch,
    ):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from sqlalchemy import select, func

        from app.models.user import User
        from app.models.payment import PaymentOrder, PaymentCallbackEvent
        from app.routers import payment as payment_router
        from app.utils.security import hash_password, create_access_token

        user = User(
            username="u_alipay_bad_sig",
            email="u_alipay_bad_sig@example.com",
            nickname="u_alipay_bad_sig",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        token = create_access_token({"sub": str(user.id)})

        create_res = await client.post(
            "/api/payment/orders",
            json={"order_type": "service", "amount": 10.0, "title": "svc"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_res.status_code == 200
        order_no = str(create_res.json()["order_no"])

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode("utf-8")
        public_pem = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

        monkeypatch.setattr(payment_router.settings, "alipay_public_key", public_pem, raising=False)
        monkeypatch.setattr(payment_router.settings, "alipay_app_id", "test_app", raising=False)

        params = {
            "app_id": "test_app",
            "out_trade_no": order_no,
            "trade_no": "ALI_BAD_1",
            "total_amount": "10.00",
            "trade_status": "TRADE_SUCCESS",
            "sign_type": "RSA2",
            "charset": "utf-8",
        }
        params["sign"] = payment_router._alipay_sign_rsa2(params, private_pem)
        params["sign"] = params["sign"][:-3] + "abc"

        notify_res = await client.post("/api/payment/alipay/notify", data=params)
        assert notify_res.status_code == 400
        assert notify_res.text.strip() == "failure"

        order_res = await test_session.execute(
            select(PaymentOrder).where(PaymentOrder.order_no == order_no)
        )
        order = order_res.scalar_one_or_none()
        assert order is not None
        assert str(order.status) == "pending"

        evt_count_res = await test_session.execute(
            select(func.count(PaymentCallbackEvent.id)).where(
                PaymentCallbackEvent.provider == "alipay",
                PaymentCallbackEvent.order_no == order_no,
                PaymentCallbackEvent.verified == 0,
            )
        )
        assert int(evt_count_res.scalar() or 0) >= 1

    @pytest.mark.asyncio
    async def test_consultation_order_paid_confirms_consultation(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        from sqlalchemy import select

        from app.models.user import User
        from app.models.payment import UserBalance, PaymentOrder
        from app.models.lawfirm import Lawyer, LawyerConsultation
        from app.utils.security import hash_password, create_access_token

        user = User(
            username="u_consult_pay",
            email="u_consult_pay@example.com",
            nickname="u_consult_pay",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        bal = UserBalance(
            user_id=user.id,
            balance=50.0,
            frozen=0.0,
            total_recharged=50.0,
            total_consumed=0.0,
        )
        test_session.add(bal)

        lawyer = Lawyer(name="L1", consultation_fee=10.0)
        test_session.add(lawyer)
        await test_session.commit()
        await test_session.refresh(lawyer)

        token = create_access_token({"sub": str(user.id)})

        c_res = await client.post(
            "/api/lawfirm/consultations",
            json={
                "lawyer_id": int(lawyer.id),
                "subject": "咨询",
                "contact_phone": "13800000000",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert c_res.status_code == 200
        c_data = _json_dict(c_res)
        consultation_id = _as_int(c_data.get("id"))
        assert consultation_id > 0
        order_no_obj = c_data.get("payment_order_no")
        assert isinstance(order_no_obj, str)
        order_no = order_no_obj

        pay_res = await client.post(
            f"/api/payment/orders/{order_no}/pay",
            json={"payment_method": "balance"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert pay_res.status_code == 200

        c_db_res = await test_session.execute(
            select(LawyerConsultation).where(LawyerConsultation.id == int(consultation_id))
        )
        c_db = c_db_res.scalar_one_or_none()
        assert c_db is not None
        assert str(c_db.status) == "confirmed"

        o_db_res = await test_session.execute(
            select(PaymentOrder).where(PaymentOrder.order_no == str(order_no))
        )
        o_db = o_db_res.scalar_one_or_none()
        assert o_db is not None
        assert str(o_db.status) == "paid"

    @pytest.mark.asyncio
    async def test_admin_refund_balance_order_idempotent(self, client: AsyncClient, test_session: AsyncSession):
        from sqlalchemy import select, func

        from app.models.user import User
        from app.models.payment import UserBalance, BalanceTransaction
        from app.utils.security import hash_password, create_access_token

        user = User(
            username="u_refund_test",
            email="u_refund_test@example.com",
            nickname="u_refund_test",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        admin = User(
            username="a_refund_test",
            email="a_refund_test@example.com",
            nickname="a_refund_test",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add_all([user, admin])
        await test_session.commit()
        await test_session.refresh(user)
        await test_session.refresh(admin)

        balance = UserBalance(
            user_id=user.id,
            balance=100.0,
            frozen=0.0,
            total_recharged=100.0,
            total_consumed=0.0,
        )
        test_session.add(balance)
        await test_session.commit()

        user_token = create_access_token({"sub": str(user.id)})
        admin_token = create_access_token({"sub": str(admin.id)})

        create_res = await client.post(
            "/api/payment/orders",
            json={"order_type": "service", "amount": 10.0, "title": "svc"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert create_res.status_code == 200
        order_no = str(create_res.json()["order_no"])

        pay_res = await client.post(
            f"/api/payment/orders/{order_no}/pay",
            json={"payment_method": "balance"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert pay_res.status_code == 200

        bal_after_pay = await client.get(
            "/api/payment/balance",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert bal_after_pay.status_code == 200
        assert abs(_as_float(_json_dict(bal_after_pay).get("balance"), 0.0) - 90.0) < 1e-6

        refund_res = await client.post(
            f"/api/payment/admin/refund/{order_no}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert refund_res.status_code == 200

        detail_after_refund = await client.get(
            f"/api/payment/orders/{order_no}",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert detail_after_refund.status_code == 200
        assert _json_dict(detail_after_refund).get("status") == "refunded"

        bal_after_refund = await client.get(
            "/api/payment/balance",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert bal_after_refund.status_code == 200
        assert abs(_as_float(_json_dict(bal_after_refund).get("balance"), 0.0) - 100.0) < 1e-6

        refund_res2 = await client.post(
            f"/api/payment/admin/refund/{order_no}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert refund_res2.status_code == 200

        bal_after_refund2 = await client.get(
            "/api/payment/balance",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert bal_after_refund2.status_code == 200
        assert abs(_as_float(_json_dict(bal_after_refund2).get("balance"), 0.0) - 100.0) < 1e-6

        refund_tx_count_result = await test_session.execute(
            select(func.count(BalanceTransaction.id)).where(
                BalanceTransaction.user_id == user.id,
                BalanceTransaction.type == "refund",
            )
        )
        refund_tx_count = int(refund_tx_count_result.scalar() or 0)
        assert refund_tx_count == 1

    @pytest.mark.asyncio
    async def test_recharge_order_mark_paid_credits_balance(self, client: AsyncClient, test_session: AsyncSession):
        from app.models.user import User
        from app.utils.security import hash_password, create_access_token

        user = User(
            username="u_recharge_test",
            email="u_recharge_test@example.com",
            nickname="u_recharge_test",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        admin = User(
            username="a_recharge_test",
            email="a_recharge_test@example.com",
            nickname="a_recharge_test",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add_all([user, admin])
        await test_session.commit()
        await test_session.refresh(user)
        await test_session.refresh(admin)

        user_token = create_access_token({"sub": str(user.id)})
        admin_token = create_access_token({"sub": str(admin.id)})

        create_res = await client.post(
            "/api/payment/orders",
            json={"order_type": "recharge", "amount": 10.0, "title": "recharge"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert create_res.status_code == 200
        order_no = str(create_res.json()["order_no"])

        mark_paid_res = await client.post(
            f"/api/payment/admin/orders/{order_no}/mark-paid",
            json={"payment_method": "alipay"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert mark_paid_res.status_code == 200

        bal_res = await client.get(
            "/api/payment/balance",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert bal_res.status_code == 200
        bal_data = _json_dict(bal_res)
        assert abs(_as_float(bal_data.get("balance"), 0.0) - 10.0) < 1e-6
        assert _as_float(bal_data.get("total_recharged"), 0.0) >= 10.0

    @pytest.mark.asyncio
    async def test_payment_webhook_duplicate_callback_idempotent(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        import hashlib
        import hmac
        from sqlalchemy import select, func

        from app.models.user import User
        from app.models.payment import PaymentCallbackEvent
        from app.utils.security import hash_password, create_access_token

        user = User(
            username="u_webhook_dup_test",
            email="u_webhook_dup_test@example.com",
            nickname="u_webhook_dup_test",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        token = create_access_token({"sub": str(user.id)})

        create_res = await client.post(
            "/api/payment/orders",
            json={"order_type": "service", "amount": 10.0, "title": "svc"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_res.status_code == 200
        order_no = str(create_res.json()["order_no"])

        trade_no = "T_WEBHOOK_DUP_1"
        payment_method = "alipay"
        amount_str = "10.00"

        payload = f"{order_no}|{trade_no}|{payment_method}|{amount_str}".encode("utf-8")
        signature = hmac.new(b"", payload, hashlib.sha256).hexdigest()

        webhook_payload = {
            "order_no": order_no,
            "trade_no": trade_no,
            "payment_method": payment_method,
            "amount": 10.0,
            "signature": signature,
        }

        res1 = await client.post("/api/payment/webhook", json=webhook_payload)
        assert res1.status_code == 200

        res2 = await client.post("/api/payment/webhook", json=webhook_payload)
        assert res2.status_code == 200

        evt_count_res = await test_session.execute(
            select(func.count(PaymentCallbackEvent.id)).where(
                PaymentCallbackEvent.provider == payment_method,
                PaymentCallbackEvent.trade_no == trade_no,
            )
        )
        assert int(evt_count_res.scalar() or 0) == 1

    @pytest.mark.asyncio
    async def test_payment_webhook_marks_order_paid(self, client: AsyncClient, test_session: AsyncSession):
        import hashlib
        import hmac

        from app.models.user import User
        from app.utils.security import hash_password, create_access_token

        user = User(
            username="u_webhook_test",
            email="u_webhook_test@example.com",
            nickname="u_webhook_test",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        token = create_access_token({"sub": str(user.id)})

        create_res = await client.post(
            "/api/payment/orders",
            json={"order_type": "service", "amount": 10.0, "title": "svc"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert create_res.status_code == 200
        order_no = str(create_res.json()["order_no"])

        trade_no = "T123"
        payment_method = "alipay"
        amount_str = "10.00"
        payload = f"{order_no}|{trade_no}|{payment_method}|{amount_str}".encode("utf-8")
        signature = hmac.new(b"", payload, hashlib.sha256).hexdigest()

        webhook_res = await client.post(
            "/api/payment/webhook",
            json={
                "order_no": order_no,
                "trade_no": trade_no,
                "payment_method": payment_method,
                "amount": 10.0,
                "signature": signature,
            },
        )
        assert webhook_res.status_code == 200

        detail_res = await client.get(
            f"/api/payment/orders/{order_no}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail_res.status_code == 200
        assert _json_dict(detail_res).get("status") == "paid"


class TestDocumentAPI:
    """文书生成API测试"""
    
    @pytest.mark.asyncio
    async def test_get_document_types(self, client: AsyncClient):
        """测试获取文书类型"""
        response = await client.get("/api/documents/types")
        assert response.status_code == 200
        raw = cast(object, response.json())
        assert isinstance(raw, list)
        data = cast(list[object], raw)
        assert len(data) > 0


class TestSystemAPI:
    """系统API测试"""
    
    @pytest.mark.asyncio
    async def test_get_admin_stats(self, client: AsyncClient):
        """测试获取管理统计（需要认证）"""
        response = await client.get("/api/admin/stats")
        # 未认证应返回401
        assert response.status_code == 401


class TestSystemAIOpsStatus:
    @pytest.mark.asyncio
    async def test_get_ai_ops_status_admin(self, client: AsyncClient, test_session: AsyncSession):
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        admin = User(
            username="a_ai_ops",
            email="a_ai_ops@example.com",
            nickname="a_ai_ops",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add(admin)
        await test_session.commit()
        await test_session.refresh(admin)

        token = create_access_token({"sub": str(admin.id)})

        res = await client.get(
            "/api/system/ai/status",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = _json_dict(res)
        assert isinstance(data.get("providers"), list)
        assert "top_endpoints" in data
        assert isinstance(data.get("top_error_codes"), list)
        assert isinstance(data.get("top_endpoints"), list)


class TestSystemAiFeedbackStats:
    @pytest.mark.asyncio
    async def test_ai_feedback_stats_requires_admin(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        from datetime import datetime, timedelta, timezone

        from app.models.consultation import Consultation, ChatMessage
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        user = User(
            username="ai_fb_user",
            email="ai_fb_user@example.com",
            nickname="ai_fb_user",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        admin = User(
            username="ai_fb_admin",
            email="ai_fb_admin@example.com",
            nickname="ai_fb_admin",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add_all([user, admin])
        await test_session.commit()
        await test_session.refresh(user)
        await test_session.refresh(admin)

        token_user = create_access_token({"sub": str(user.id)})
        token_admin = create_access_token({"sub": str(admin.id)})

        now = datetime.now(timezone.utc)

        cons = Consultation(
            user_id=user.id,
            session_id="ai_fb_sid_1",
            title="t",
            created_at=now - timedelta(days=1),
        )
        test_session.add(cons)
        await test_session.commit()
        await test_session.refresh(cons)

        m_user = ChatMessage(
            consultation_id=cons.id,
            role="user",
            content="hi",
            created_at=now - timedelta(hours=3),
        )
        m_good = ChatMessage(
            consultation_id=cons.id,
            role="assistant",
            content="a1",
            rating=3,
            feedback="不错",
            created_at=now - timedelta(hours=2),
        )
        m_bad = ChatMessage(
            consultation_id=cons.id,
            role="assistant",
            content="a2",
            rating=1,
            feedback=None,
            created_at=now - timedelta(hours=1),
        )
        test_session.add_all([m_user, m_good, m_bad])
        await test_session.commit()
        await test_session.refresh(m_good)
        await test_session.refresh(m_bad)

        res_anon = await client.get("/api/system/stats/ai-feedback")
        assert res_anon.status_code == 401

        res_user = await client.get(
            "/api/system/stats/ai-feedback",
            headers={"Authorization": f"Bearer {token_user}"},
        )
        assert res_user.status_code == 403

        res_admin = await client.get(
            "/api/system/stats/ai-feedback",
            params={"days": 30, "limit": 10},
            headers={"Authorization": f"Bearer {token_admin}"},
        )
        assert res_admin.status_code == 200
        data = _json_dict(res_admin)

        assert _as_int(data.get("days")) == 30
        assert isinstance(data.get("since"), str)
        assert _as_int(data.get("consultations_total")) == 1
        assert _as_int(data.get("messages_total")) == 3
        assert _as_int(data.get("assistant_messages_total")) == 2
        assert _as_int(data.get("total_rated")) == 2
        assert _as_int(data.get("good")) == 1
        assert _as_int(data.get("neutral")) == 0
        assert _as_int(data.get("bad")) == 1
        assert abs(_as_float(data.get("satisfaction_rate"), 0.0) - 50.0) < 1e-6
        assert abs(_as_float(data.get("rating_rate"), 0.0) - 100.0) < 1e-6

        rr = data.get("recent_ratings")
        assert isinstance(rr, list)
        assert len(rr) == 2
        first = cast(dict[str, object], rr[0])
        assert _as_int(first.get("message_id")) == m_bad.id
        assert _as_int(first.get("consultation_id")) == cons.id
        assert _as_int(first.get("rating")) == 1
        assert first.get("feedback") is None


class TestSystemFaqAutogen:
    @pytest.mark.asyncio
    async def test_faq_generate_and_public_read(self, client: AsyncClient, test_session: AsyncSession):
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import select

        from app.models.consultation import Consultation, ChatMessage
        from app.models.system import SystemConfig
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        user = User(
            username="faq_u",
            email="faq_u@example.com",
            nickname="faq_u",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        admin = User(
            username="faq_admin",
            email="faq_admin@example.com",
            nickname="faq_admin",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add_all([user, admin])
        await test_session.commit()
        await test_session.refresh(user)
        await test_session.refresh(admin)

        token_user = create_access_token({"sub": str(user.id)})
        token_admin = create_access_token({"sub": str(admin.id)})

        now = datetime.now(timezone.utc)
        cons = Consultation(
            user_id=user.id,
            session_id="faq_sid_1",
            title="t",
            created_at=now - timedelta(days=1),
        )
        test_session.add(cons)
        await test_session.commit()
        await test_session.refresh(cons)

        q_msg = ChatMessage(
            consultation_id=cons.id,
            role="user",
            content="劳动合同试用期最长多久？",
            created_at=now - timedelta(hours=2),
        )
        a_msg = ChatMessage(
            consultation_id=cons.id,
            role="assistant",
            content="一般情况下，试用期最长不超过六个月...",
            rating=3,
            feedback="很有用",
            created_at=now - timedelta(hours=1),
        )
        test_session.add_all([q_msg, a_msg])
        await test_session.commit()

        res_public_before = await client.get("/api/system/public/faq")
        assert res_public_before.status_code == 200
        data_before = _json_dict(res_public_before)
        items_before = data_before.get("items")
        assert isinstance(items_before, list)

        res_gen_anon = await client.post("/api/system/faq/generate")
        assert res_gen_anon.status_code == 401

        res_gen_user = await client.post(
            "/api/system/faq/generate",
            headers={"Authorization": f"Bearer {token_user}"},
        )
        assert res_gen_user.status_code == 403

        res_gen_admin = await client.post(
            "/api/system/faq/generate",
            params={"days": 30, "max_items": 10, "scan_limit": 50},
            headers={"Authorization": f"Bearer {token_admin}"},
        )
        assert res_gen_admin.status_code == 200
        gen = _json_dict(res_gen_admin)
        assert gen.get("key") == "FAQ_PUBLIC_ITEMS_JSON"
        assert _as_int(gen.get("generated")) == 1
        items_obj = gen.get("items")
        assert isinstance(items_obj, list)
        assert len(items_obj) == 1
        first = cast(dict[str, object], items_obj[0])
        assert "劳动合同" in str(first.get("question") or "")
        assert "试用期" in str(first.get("answer") or "")

        cfg_res = await test_session.execute(
            select(SystemConfig).where(SystemConfig.key == "FAQ_PUBLIC_ITEMS_JSON")
        )
        cfg = cfg_res.scalar_one_or_none()
        assert cfg is not None
        assert isinstance(cfg.value, str)
        assert cfg.value.strip() != ""

        res_public_after = await client.get("/api/system/public/faq")
        assert res_public_after.status_code == 200
        data_after = _json_dict(res_public_after)
        items_after = data_after.get("items")
        assert isinstance(items_after, list)
        assert len(items_after) == 1
        row0 = cast(dict[str, object], items_after[0])
        assert "劳动合同" in str(row0.get("question") or "")
        assert "试用期" in str(row0.get("answer") or "")


class TestCalendarAPI:
    @pytest.mark.asyncio
    async def test_calendar_reminders_crud_and_permissions(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        from datetime import datetime, timedelta, timezone

        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        u1 = User(
            username="calendar_u1",
            email="calendar_u1@example.com",
            nickname="calendar_u1",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        u2 = User(
            username="calendar_u2",
            email="calendar_u2@example.com",
            nickname="calendar_u2",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )

        test_session.add_all([u1, u2])
        await test_session.commit()
        await test_session.refresh(u1)
        await test_session.refresh(u2)

        token_u1 = create_access_token({"sub": str(u1.id)})
        token_u2 = create_access_token({"sub": str(u2.id)})

        due_at = datetime.now(timezone.utc) + timedelta(days=1)
        remind_at = due_at - timedelta(hours=2)

        create_res = await client.post(
            "/api/calendar/reminders",
            json={
                "title": "诉讼时效提醒",
                "note": "准备材料",
                "due_at": due_at.isoformat(),
                "remind_at": remind_at.isoformat(),
            },
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert create_res.status_code == 200
        created = _json_dict(create_res)
        rid = _as_int(created.get("id"))
        assert rid > 0
        assert _as_int(created.get("user_id")) == u1.id

        list_res = await client.get(
            "/api/calendar/reminders",
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert list_res.status_code == 200
        list_data = _json_dict(list_res)
        assert _as_int(list_data.get("total")) == 1
        items = cast(list[dict[str, object]], list_data.get("items"))
        assert len(items) == 1
        assert _as_int(items[0].get("id")) == rid

        forbidden_update = await client.put(
            f"/api/calendar/reminders/{rid}",
            json={"title": "hacked"},
            headers={"Authorization": f"Bearer {token_u2}"},
        )
        assert forbidden_update.status_code == 404

        update_res = await client.put(
            f"/api/calendar/reminders/{rid}",
            json={"is_done": True},
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert update_res.status_code == 200
        updated = _json_dict(update_res)
        assert bool(updated.get("is_done")) is True
        assert updated.get("done_at") is not None

        forbidden_delete = await client.delete(
            f"/api/calendar/reminders/{rid}",
            headers={"Authorization": f"Bearer {token_u2}"},
        )
        assert forbidden_delete.status_code == 404

        delete_res = await client.delete(
            f"/api/calendar/reminders/{rid}",
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert delete_res.status_code == 200

        list_res2 = await client.get(
            "/api/calendar/reminders",
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert list_res2.status_code == 200
        list_data2 = _json_dict(list_res2)
        assert _as_int(list_data2.get("total")) == 0


class TestKnowledgeAPI:
    @pytest.mark.asyncio
    async def test_knowledge_templates_active_is_public(self, client: AsyncClient):
        res = await client.get("/api/knowledge/templates", params={"is_active": True})
        assert res.status_code == 200
        data = cast(object, res.json())
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_knowledge_templates_all_requires_admin(
        self,
        client: AsyncClient,
    ):
        res = await client.get("/api/knowledge/templates", params={"is_active": ""})
        assert res.status_code in {401, 403}

    @pytest.mark.asyncio
    async def test_knowledge_laws_requires_admin(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        user = User(
            username="kb_user",
            email="kb_user@example.com",
            nickname="kb_user",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        admin = User(
            username="kb_admin",
            email="kb_admin@example.com",
            nickname="kb_admin",
            hashed_password=hash_password("Test123456"),
            role="admin",
            is_active=True,
        )
        test_session.add_all([user, admin])
        await test_session.commit()
        await test_session.refresh(user)
        await test_session.refresh(admin)

        token_user = create_access_token({"sub": str(user.id)})
        token_admin = create_access_token({"sub": str(admin.id)})

        payload = {
            "knowledge_type": "law",
            "title": "民法典",
            "article_number": "第一条",
            "content": "为了保护民事主体的合法权益...",
            "summary": None,
            "category": "民法",
            "keywords": None,
            "source": "全国人大",
            "effective_date": "2021-01-01",
            "weight": 1.0,
            "is_active": True,
        }

        res_user = await client.post(
            "/api/knowledge/laws",
            json=payload,
            headers={"Authorization": f"Bearer {token_user}"},
        )
        assert res_user.status_code == 403

        res_admin = await client.post(
            "/api/knowledge/laws",
            json=payload,
            headers={"Authorization": f"Bearer {token_admin}"},
        )
        assert res_admin.status_code == 200
        created = _json_dict(res_admin)
        assert _as_int(created.get("id")) > 0
        assert created.get("title") == "民法典"

        list_admin = await client.get(
            "/api/knowledge/laws",
            headers={"Authorization": f"Bearer {token_admin}"},
        )
        assert list_admin.status_code == 200
        list_data = _json_dict(list_admin)
        assert _as_int(list_data.get("total")) >= 1

        stats_user = await client.get(
            "/api/knowledge/stats",
            headers={"Authorization": f"Bearer {token_user}"},
        )
        assert stats_user.status_code == 403

        stats_admin = await client.get(
            "/api/knowledge/stats",
            headers={"Authorization": f"Bearer {token_admin}"},
        )
        assert stats_admin.status_code == 200

        categories_user = await client.get(
            "/api/knowledge/categories",
            headers={"Authorization": f"Bearer {token_user}"},
        )
        assert categories_user.status_code == 403


class TestAIConsultationAPI:
    @pytest.mark.asyncio
    async def test_ai_chat_seeds_history_and_enforces_permission(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch: MonkeyPatch,
    ):
        from app.models.consultation import Consultation, ChatMessage
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        import app.routers.ai as ai_router

        # enable AI endpoints without needing real OPENAI_API_KEY
        monkeypatch.setattr(ai_router.settings, "openai_api_key", "test", raising=True)

        u1 = User(
            username="ai_u1",
            email="ai_u1@example.com",
            nickname="ai_u1",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        u2 = User(
            username="ai_u2",
            email="ai_u2@example.com",
            nickname="ai_u2",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add_all([u1, u2])
        await test_session.commit()
        await test_session.refresh(u1)
        await test_session.refresh(u2)

        token_u1 = create_access_token({"sub": str(u1.id)})
        token_u2 = create_access_token({"sub": str(u2.id)})

        sid = "seeded_session"
        cons = Consultation(user_id=u1.id, session_id=sid, title="t")
        test_session.add(cons)
        await test_session.commit()
        await test_session.refresh(cons)

        test_session.add_all(
            [
                ChatMessage(consultation_id=cons.id, role="user", content="hello"),
                ChatMessage(consultation_id=cons.id, role="assistant", content="hi"),
            ]
        )
        await test_session.commit()

        class FakeAssistant:
            async def chat(
                self,
                *,
                message: str,
                session_id: str | None = None,
                initial_history: list[dict[str, str]] | None = None,
            ) -> tuple[str, str, list[object]]:
                _ = message
                assert session_id == sid
                assert isinstance(initial_history, list)
                assert len(initial_history) >= 2
                assert initial_history[0]["role"] == "user"
                assert initial_history[0]["content"] == "hello"
                return sid, "OK", []

        monkeypatch.setattr(ai_router, "_try_get_ai_assistant", lambda: FakeAssistant(), raising=True)

        res = await client.post(
            "/api/ai/chat",
            json={"message": "next", "session_id": sid},
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert res.status_code == 200
        req_id = res.headers.get("X-Request-Id")
        assert isinstance(req_id, str)
        assert req_id.strip() != ""
        data = _json_dict(res)
        assert data.get("session_id") == sid
        assert data.get("answer") == "OK"

        # non-owner should be blocked before assistant is called
        monkeypatch.setattr(ai_router, "_try_get_ai_assistant", lambda: (_ for _ in ()).throw(RuntimeError("should_not_call")), raising=True)
        res2 = await client.post(
            "/api/ai/chat",
            json={"message": "hack", "session_id": sid},
            headers={"Authorization": f"Bearer {token_u2}"},
        )
        assert res2.status_code == 403
        assert isinstance(res2.headers.get("X-Request-Id"), str)
        assert isinstance(res2.headers.get("X-Error-Code"), str)
        payload2 = _json_dict(res2)
        assert payload2.get("error_code") == "AI_FORBIDDEN"
        assert isinstance(payload2.get("request_id"), str)

    @pytest.mark.asyncio
    async def test_ai_chat_returns_strategy_meta_when_available(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch: MonkeyPatch,
    ):
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        import app.routers.ai as ai_router

        monkeypatch.setattr(ai_router.settings, "openai_api_key", "test", raising=True)

        user = User(
            username="ai_meta_u1",
            email="ai_meta_u1@example.com",
            nickname="ai_meta_u1",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        token = create_access_token({"sub": str(user.id)})

        class FakeAssistant:
            async def chat(
                self,
                *,
                message: str,
                session_id: str | None = None,
                initial_history: list[dict[str, str]] | None = None,
            ) -> tuple[str, str, list[object], dict[str, object]]:
                _ = message
                _ = initial_history
                assert session_id is None
                return (
                    "s_meta_1",
                    "OK",
                    [],
                    {
                        "strategy_used": "general_legal",
                        "strategy_reason": "未找到直接相关法条",
                        "confidence": "low",
                        "risk_level": "safe",
                        "model_used": "test-model-b",
                        "fallback_used": True,
                        "model_attempts": ["test-model-a", "test-model-b"],
                        "intent": "labor",
                        "needs_clarification": True,
                        "clarifying_questions": ["q1"],
                        "search_quality": {
                            "total_candidates": 0,
                            "qualified_count": 0,
                            "avg_similarity": 0.0,
                            "confidence": "low",
                        },
                        "disclaimer": "d",
                    },
                )

        monkeypatch.setattr(ai_router, "_try_get_ai_assistant", lambda: FakeAssistant(), raising=True)

        res = await client.post(
            "/api/ai/chat",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = _json_dict(res)
        assert data.get("session_id") == "s_meta_1"
        assert data.get("answer") == "OK"
        assert data.get("strategy_used") == "general_legal"
        assert data.get("strategy_reason") == "未找到直接相关法条"
        assert data.get("confidence") == "low"
        assert data.get("risk_level") == "safe"
        assert data.get("disclaimer") == "d"
        assert data.get("model_used") == "test-model-b"
        assert data.get("fallback_used") is True
        assert data.get("model_attempts") == ["test-model-a", "test-model-b"]
        assert data.get("intent") == "labor"
        assert data.get("needs_clarification") is True
        assert data.get("clarifying_questions") == ["q1"]

        sq_obj = data.get("search_quality")
        assert isinstance(sq_obj, dict)
        sq = cast(dict[str, object], sq_obj)
        assert sq.get("qualified_count") == 0
        assert sq.get("confidence") == "low"

    @pytest.mark.asyncio
    async def test_ai_chat_passes_user_profile_when_supported(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch: MonkeyPatch,
    ):
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        import app.routers.ai as ai_router

        monkeypatch.setattr(ai_router.settings, "openai_api_key", "test", raising=True)

        user = User(
            username="ai_profile_u1",
            email="ai_profile_u1@example.com",
            nickname="小明",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        token = create_access_token({"sub": str(user.id)})

        expected_profile = "\n".join(["昵称：小明", "用户名：ai_profile_u1", "身份：user"])

        class FakeAssistant:
            async def chat(
                self,
                *,
                message: str,
                session_id: str | None = None,
                initial_history: list[dict[str, str]] | None = None,
                user_profile: str | None = None,
            ) -> tuple[str, str, list[object], dict[str, object]]:
                _ = message
                _ = initial_history
                assert session_id is None
                assert user_profile == expected_profile
                return ("s_profile_1", "OK", [], {})

        monkeypatch.setattr(ai_router, "_try_get_ai_assistant", lambda: FakeAssistant(), raising=True)

        res = await client.post(
            "/api/ai/chat",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        data = _json_dict(res)
        assert data.get("session_id") == "s_profile_1"
        assert data.get("answer") == "OK"


class TestAIShareAPI:
    @pytest.mark.asyncio
    async def test_share_link_create_and_public_read(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        from datetime import datetime, timedelta, timezone

        from app.models.consultation import Consultation, ChatMessage
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        u1 = User(
            username="share_u1",
            email="share_u1@example.com",
            nickname="share_u1",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        u2 = User(
            username="share_u2",
            email="share_u2@example.com",
            nickname="share_u2",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add_all([u1, u2])
        await test_session.commit()
        await test_session.refresh(u1)
        await test_session.refresh(u2)

        token_u1 = create_access_token({"sub": str(u1.id)})
        token_u2 = create_access_token({"sub": str(u2.id)})

        now = datetime.now(timezone.utc)
        sid = "share_sid_1"
        cons = Consultation(
            user_id=u1.id,
            session_id=sid,
            title="share_test",
            created_at=now - timedelta(hours=3),
        )
        test_session.add(cons)
        await test_session.commit()
        await test_session.refresh(cons)

        m1 = ChatMessage(
            consultation_id=cons.id,
            role="user",
            content="q",
            created_at=now - timedelta(hours=2),
        )
        m2 = ChatMessage(
            consultation_id=cons.id,
            role="assistant",
            content="a",
            created_at=now - timedelta(hours=1),
        )
        test_session.add_all([m1, m2])
        await test_session.commit()

        res_anon = await client.post(f"/api/ai/consultations/{sid}/share")
        assert res_anon.status_code == 401

        res_forbidden = await client.post(
            f"/api/ai/consultations/{sid}/share",
            headers={"Authorization": f"Bearer {token_u2}"},
        )
        assert res_forbidden.status_code == 403

        res_ok = await client.post(
            f"/api/ai/consultations/{sid}/share",
            params={"expires_days": 7},
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert res_ok.status_code == 200
        payload = _json_dict(res_ok)
        token = str(payload.get("token") or "")
        assert token.strip() != ""
        share_path = str(payload.get("share_path") or "")
        assert share_path.startswith("/share/")
        assert "expires_at" in payload

        res_shared = await client.get(f"/api/ai/share/{token}")
        assert res_shared.status_code == 200
        shared = _json_dict(res_shared)
        assert shared.get("session_id") == sid
        msgs = shared.get("messages")
        assert isinstance(msgs, list)
        assert len(msgs) == 2
        m0 = cast(dict[str, object], msgs[0])
        assert m0.get("role") == "user"
        assert m0.get("content") == "q"

        res_bad = await client.get("/api/ai/share/not_a_token")
        assert res_bad.status_code == 401

    @pytest.mark.asyncio
    async def test_ai_chat_stream_passes_user_profile_when_supported(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch: MonkeyPatch,
    ):
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        import app.routers.ai as ai_router

        monkeypatch.setattr(ai_router.settings, "openai_api_key", "test", raising=True)

        user = User(
            username="ai_profile_stream_u1",
            email="ai_profile_stream_u1@example.com",
            nickname=None,
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        token = create_access_token({"sub": str(user.id)})

        expected_profile = "\n".join(["用户名：ai_profile_stream_u1", "身份：user"])

        class FakeAssistant:
            async def chat_stream(
                self,
                *,
                message: str,
                session_id: str | None = None,
                initial_history: list[dict[str, str]] | None = None,
                user_profile: str | None = None,
            ):
                _ = message
                _ = initial_history
                assert session_id is None
                assert user_profile == expected_profile
                yield ("session", {"session_id": "s_profile_stream_1"})
                yield ("references", {"references": []})
                yield ("meta", {"strategy_used": "general_legal"})
                yield ("content", {"text": "OK"})
                yield ("done", {"session_id": "s_profile_stream_1"})

        monkeypatch.setattr(ai_router, "_try_get_ai_assistant", lambda: FakeAssistant(), raising=True)

        async with client.stream(
            "POST",
            "/api/ai/chat/stream",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token}"},
        ) as res:
            assert res.status_code == 200

            events: list[tuple[str, dict]] = []
            async for line in res.aiter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    event_type = line.split(":", 1)[1].strip()
                    events.append((event_type, {}))
                    continue
                if line.startswith("data:"):
                    payload = json.loads(line.split(":", 1)[1].strip())
                    last_event, _ = events[-1]
                    events[-1] = (last_event, payload)

            assert any(t == "done" for t, _ in events)

    @pytest.mark.asyncio
    async def test_ai_consultations_list_supports_q_search(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
    ):
        from app.models.consultation import Consultation, ChatMessage
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        u1 = User(
            username="ai_search_u1",
            email="ai_search_u1@example.com",
            nickname="ai_search_u1",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        u2 = User(
            username="ai_search_u2",
            email="ai_search_u2@example.com",
            nickname="ai_search_u2",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add_all([u1, u2])
        await test_session.commit()
        await test_session.refresh(u1)
        await test_session.refresh(u2)

        token_u1 = create_access_token({"sub": str(u1.id)})

        c1 = Consultation(user_id=u1.id, session_id="s_search_1", title="劳动纠纷咨询")
        c2 = Consultation(user_id=u1.id, session_id="s_search_2", title="合同纠纷")
        c_other = Consultation(user_id=u2.id, session_id="s_search_3", title="劳动相关")
        test_session.add_all([c1, c2, c_other])
        await test_session.commit()
        await test_session.refresh(c1)
        await test_session.refresh(c2)
        await test_session.refresh(c_other)

        test_session.add_all(
            [
                ChatMessage(consultation_id=c1.id, role="user", content="我被拖欠工资怎么办"),
                ChatMessage(consultation_id=c2.id, role="user", content="Contract breach details"),
                ChatMessage(consultation_id=c_other.id, role="user", content="工资"),
            ]
        )
        await test_session.commit()

        res1 = await client.get(
            "/api/ai/consultations",
            params={"q": "劳动"},
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert res1.status_code == 200
        items1 = cast(object, res1.json())
        assert isinstance(items1, list)
        sids1 = {str(x.get("session_id")) for x in cast(list[dict[str, object]], items1)}
        assert "s_search_1" in sids1
        assert "s_search_2" not in sids1
        assert "s_search_3" not in sids1

        res2 = await client.get(
            "/api/ai/consultations",
            params={"q": "CONTRACT"},
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert res2.status_code == 200
        items2 = cast(object, res2.json())
        assert isinstance(items2, list)
        sids2 = {str(x.get("session_id")) for x in cast(list[dict[str, object]], items2)}
        assert "s_search_2" in sids2
        assert "s_search_1" not in sids2

        res3 = await client.get(
            "/api/ai/consultations",
            params={"q": "工资"},
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert res3.status_code == 200
        items3 = cast(object, res3.json())
        assert isinstance(items3, list)
        sids3 = {str(x.get("session_id")) for x in cast(list[dict[str, object]], items3)}
        assert "s_search_1" in sids3
        assert "s_search_2" not in sids3

        res4 = await client.get(
            "/api/ai/consultations",
            params={"q": "no_such_keyword"},
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert res4.status_code == 200
        items4 = cast(object, res4.json())
        assert isinstance(items4, list)
        assert len(items4) == 0

    @pytest.mark.asyncio
    async def test_ai_transcribe_supports_e2e_mock(self, client: AsyncClient):
        res = await client.post(
            "/api/ai/transcribe",
            files={"file": ("test.wav", b"RIFFxxxxWAVE", "audio/wav")},
            headers={"X-E2E-Mock-AI": "1"},
        )
        assert res.status_code == 200
        payload = _json_dict(res)
        assert payload.get("text") == "这是一个E2E mock 的语音转写结果"
        assert isinstance(res.headers.get("X-Request-Id"), str)

    @pytest.mark.asyncio
    async def test_ai_files_analyze_supports_e2e_mock(self, client: AsyncClient):
        res = await client.post(
            "/api/ai/files/analyze",
            files={"file": ("test.txt", b"hello", "text/plain")},
            headers={"X-E2E-Mock-AI": "1"},
        )
        assert res.status_code == 200
        payload = _json_dict(res)
        assert payload.get("filename") == "test.txt"
        assert payload.get("summary") == "这是一个E2E mock 的文件分析结果"
        assert isinstance(payload.get("text_chars"), int)
        assert isinstance(res.headers.get("X-Request-Id"), str)

    @pytest.mark.asyncio
    async def test_ai_consultation_report_sets_rfc5987_filename(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch: MonkeyPatch,
    ):
        from app.models.consultation import Consultation, ChatMessage
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        import app.routers.ai as ai_router

        def fake_generate(_report: object) -> bytes:
            return b"%PDF-1.4\n%\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"

        monkeypatch.setattr(ai_router, "generate_consultation_report_pdf", fake_generate, raising=True)

        u1 = User(
            username="ai_report_u1",
            email="ai_report_u1@example.com",
            nickname="ai_report_u1",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(u1)
        await test_session.commit()
        await test_session.refresh(u1)

        token_u1 = create_access_token({"sub": str(u1.id)})

        sid = "s_report_\u6d4b\u8bd5 1"
        cons = Consultation(user_id=u1.id, session_id=sid, title="t")
        test_session.add(cons)
        await test_session.commit()
        await test_session.refresh(cons)

        test_session.add_all(
            [
                ChatMessage(consultation_id=cons.id, role="user", content="hello"),
                ChatMessage(consultation_id=cons.id, role="assistant", content="hi"),
            ]
        )
        await test_session.commit()

        import urllib.parse

        sid_q = urllib.parse.quote(sid, safe="")
        res = await client.get(
            f"/api/ai/consultations/{sid_q}/report",
            headers={"Authorization": f"Bearer {token_u1}"},
        )
        assert res.status_code == 200
        cd = res.headers.get("Content-Disposition")
        assert isinstance(cd, str)
        assert "attachment" in cd.lower()
        assert "filename=" in cd
        assert "filename*=" in cd

    @pytest.mark.asyncio
    async def test_ai_chat_stream_always_emits_done_on_stream_error(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch: MonkeyPatch,
    ):
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        import app.routers.ai as ai_router

        monkeypatch.setattr(ai_router.settings, "openai_api_key", "test", raising=True)

        user = User(
            username="ai_stream_u1",
            email="ai_stream_u1@example.com",
            nickname="ai_stream_u1",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add(user)
        await test_session.commit()
        await test_session.refresh(user)

        token = create_access_token({"sub": str(user.id)})

        sid = "stream_error_sid"

        class FakeAssistant:
            async def chat_stream(
                self,
                *,
                message: str,
                session_id: str | None = None,
                initial_history: list[dict[str, str]] | None = None,
            ) -> AsyncGenerator[tuple[str, dict[str, object]], None]:
                _ = message
                _ = initial_history
                yield ("session", {"session_id": cast(str, session_id)})
                yield ("content", {"text": "hi"})
                raise RuntimeError("boom")

        monkeypatch.setattr(ai_router, "_try_get_ai_assistant", lambda: FakeAssistant(), raising=True)

        async with client.stream(
            "POST",
            "/api/ai/chat/stream",
            json={"message": "hello", "session_id": sid},
            headers={"Authorization": f"Bearer {token}"},
        ) as res:
            assert res.status_code == 200
            req_id = res.headers.get("X-Request-Id")
            assert isinstance(req_id, str)
            assert req_id.strip() != ""
            raw = ""
            async for chunk in res.aiter_text():
                raw += chunk

        def _extract_done_payload(text: str) -> dict[str, object]:
            blocks = [b for b in text.split("\n\n") if b.strip()]
            for block in reversed(blocks):
                lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
                event_type = "message"
                data_line = ""
                for ln in lines:
                    if ln.startswith("event:"):
                        event_type = ln[6:].strip()
                    elif ln.startswith("data:"):
                        data_line += ln[5:].strip()
                if event_type != "done" or not data_line:
                    continue
                parsed = json.loads(data_line)
                assert isinstance(parsed, dict)
                return cast(dict[str, object], parsed)
            raise AssertionError("done event not found")

        done_payload = _extract_done_payload(raw)
        assert done_payload.get("session_id") == sid
        assert done_payload.get("persist_error") == "stream_failed"
        done_req_id = done_payload.get("request_id")
        assert isinstance(done_req_id, str)
        assert done_req_id.strip() != ""

    @pytest.mark.asyncio
    async def test_ai_chat_stream_always_emits_done_on_persist_forbidden(
        self,
        client: AsyncClient,
        test_session: AsyncSession,
        monkeypatch: MonkeyPatch,
    ):
        from app.models.consultation import Consultation
        from app.models.user import User
        from app.utils.security import create_access_token, hash_password

        import app.routers.ai as ai_router

        monkeypatch.setattr(ai_router.settings, "openai_api_key", "test", raising=True)

        u1 = User(
            username="ai_stream_owner",
            email="ai_stream_owner@example.com",
            nickname="ai_stream_owner",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        u2 = User(
            username="ai_stream_other",
            email="ai_stream_other@example.com",
            nickname="ai_stream_other",
            hashed_password=hash_password("Test123456"),
            role="user",
            is_active=True,
        )
        test_session.add_all([u1, u2])
        await test_session.commit()
        await test_session.refresh(u1)
        await test_session.refresh(u2)

        token_u2 = create_access_token({"sub": str(u2.id)})

        sid = "persist_forbidden_sid"
        cons = Consultation(user_id=u1.id, session_id=sid, title="t")
        test_session.add(cons)
        await test_session.commit()

        class FakeAssistant:
            async def chat_stream(
                self,
                *,
                message: str,
                session_id: str | None = None,
                initial_history: list[dict[str, str]] | None = None,
            ) -> AsyncGenerator[tuple[str, dict[str, object]], None]:
                _ = message
                _ = session_id
                _ = initial_history
                yield ("session", {"session_id": sid})
                yield ("content", {"text": "ok"})
                yield ("done", {"session_id": sid})

        monkeypatch.setattr(ai_router, "_try_get_ai_assistant", lambda: FakeAssistant(), raising=True)

        async with client.stream(
            "POST",
            "/api/ai/chat/stream",
            json={"message": "hello"},
            headers={"Authorization": f"Bearer {token_u2}"},
        ) as res:
            assert res.status_code == 200
            req_id = res.headers.get("X-Request-Id")
            assert isinstance(req_id, str)
            assert req_id.strip() != ""
            raw = ""
            async for chunk in res.aiter_text():
                raw += chunk

        def _extract_done_payload(text: str) -> dict[str, object]:
            blocks = [b for b in text.split("\n\n") if b.strip()]
            for block in reversed(blocks):
                lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
                event_type = "message"
                data_line = ""
                for ln in lines:
                    if ln.startswith("event:"):
                        event_type = ln[6:].strip()
                    elif ln.startswith("data:"):
                        data_line += ln[5:].strip()
                if event_type != "done" or not data_line:
                    continue
                parsed = json.loads(data_line)
                assert isinstance(parsed, dict)
                return cast(dict[str, object], parsed)
            raise AssertionError("done event not found")

        done_payload = _extract_done_payload(raw)
        assert done_payload.get("session_id") == sid
        assert done_payload.get("persist_error") == "persist_forbidden"
        done_req_id = done_payload.get("request_id")
        assert isinstance(done_req_id, str)
        assert done_req_id.strip() != ""
