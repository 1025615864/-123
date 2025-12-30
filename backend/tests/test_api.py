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
            "password": "Test123456"
        }
        response = await client.post("/api/user/register", json=user_data)
        assert response.status_code in [200, 201, 400, 422]  # 422 validation error
    
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


class TestPaymentAPI:
    """支付API测试"""

    @pytest.mark.asyncio
    async def test_balance_pay_order(self, client: AsyncClient, test_session: AsyncSession):
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

        bal_res = await client.get(
            "/api/payment/balance",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert bal_res.status_code == 200
        bal_data = _json_dict(bal_res)
        assert abs(_as_float(bal_data.get("balance"), 0.0) - 90.0) < 1e-6
        assert _as_float(bal_data.get("total_consumed"), 0.0) >= 10.0

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
        assert "ai_router_enabled" in data
        assert "openai_api_key_configured" in data
        assert "chat_requests_total" in data
        assert "chat_stream_requests_total" in data
        assert "errors_total" in data
        assert "top_error_codes" in data
        assert "top_endpoints" in data
        assert isinstance(data.get("top_error_codes"), list)
        assert isinstance(data.get("top_endpoints"), list)


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
