"""API接口测试"""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from typing import cast

from _pytest.monkeypatch import MonkeyPatch


class TestRootAPI:
    """根路由测试"""
    
    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient):
        """测试根路由"""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
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
        data = response.json()
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
        assert res.json().get("message") == "ok"

        ann_res = await test_session.execute(
            select(NewsAIAnnotation).where(NewsAIAnnotation.news_id == int(news.id))
        )
        ann = ann_res.scalar_one_or_none()
        assert ann is not None
        assert ann.summary == "AI摘要"
        assert ann.processed_at is not None


class TestForumAPI:
    """论坛API测试"""
    
    @pytest.mark.asyncio
    async def test_get_posts_list(self, client: AsyncClient):
        """测试获取帖子列表"""
        response = await client.get("/api/forum/posts")
        assert response.status_code == 200
        data = response.json()
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
        post = post_res.json()
        post_id = int(post["id"])

        comment_res = await client.post(
            f"/api/forum/posts/{post_id}/comments",
            json={"content": "联系我 13800138000"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert comment_res.status_code == 200
        comment = comment_res.json()
        comment_id = int(comment["id"])
        assert comment.get("review_status") == "pending"

        comments_before = await client.get(f"/api/forum/posts/{post_id}/comments")
        assert comments_before.status_code == 200
        comments_before_data = comments_before.json()
        assert comments_before_data.get("total") == 0

        post_detail_before = await client.get(f"/api/forum/posts/{post_id}")
        assert post_detail_before.status_code == 200
        assert int(post_detail_before.json().get("comment_count") or 0) == 0

        pending_res = await client.get(
            "/api/forum/admin/pending-comments?page=1&page_size=20",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert pending_res.status_code == 200
        pending_data = pending_res.json()
        assert int(pending_data.get("total") or 0) >= 1
        pending_ids = {int(item["id"]) for item in pending_data.get("items", [])}
        assert comment_id in pending_ids

        approve_res = await client.post(
            f"/api/forum/admin/comments/{comment_id}/review",
            json={"action": "approve"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert approve_res.status_code == 200

        post_detail_after = await client.get(f"/api/forum/posts/{post_id}")
        assert post_detail_after.status_code == 200
        assert int(post_detail_after.json().get("comment_count") or 0) == 1

        comments_after = await client.get(f"/api/forum/posts/{post_id}/comments")
        assert comments_after.status_code == 200
        comments_after_data = comments_after.json()
        assert int(comments_after_data.get("total") or 0) >= 1
        ids_after = {int(item["id"]) for item in comments_after_data.get("items", [])}
        assert comment_id in ids_after


class TestLawFirmAPI:
    """律所API测试"""
    
    @pytest.mark.asyncio
    async def test_get_lawfirms_list(self, client: AsyncClient):
        """测试获取律所列表"""
        response = await client.get("/api/lawfirm/firms")
        assert response.status_code == 200
        data = response.json()
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
        assert pay_res.json().get("trade_no")

        detail_res = await client.get(
            f"/api/payment/orders/{order_no}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail_res.status_code == 200
        assert detail_res.json().get("status") == "paid"

        bal_res = await client.get(
            "/api/payment/balance",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert bal_res.status_code == 200
        bal_data = bal_res.json()
        assert abs(float(bal_data.get("balance") or 0.0) - 90.0) < 1e-6
        assert float(bal_data.get("total_consumed") or 0.0) >= 10.0

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
        assert abs(float(bal_after_pay.json().get("balance") or 0.0) - 90.0) < 1e-6

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
        assert detail_after_refund.json().get("status") == "refunded"

        bal_after_refund = await client.get(
            "/api/payment/balance",
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert bal_after_refund.status_code == 200
        assert abs(float(bal_after_refund.json().get("balance") or 0.0) - 100.0) < 1e-6

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
        assert abs(float(bal_after_refund2.json().get("balance") or 0.0) - 100.0) < 1e-6

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
        bal_data = bal_res.json()
        assert abs(float(bal_data.get("balance") or 0.0) - 10.0) < 1e-6
        assert float(bal_data.get("total_recharged") or 0.0) >= 10.0

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
        assert detail_res.json().get("status") == "paid"


class TestDocumentAPI:
    """文书生成API测试"""
    
    @pytest.mark.asyncio
    async def test_get_document_types(self, client: AsyncClient):
        """测试获取文书类型"""
        response = await client.get("/api/documents/types")
        assert response.status_code == 200
        raw = response.json()
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
