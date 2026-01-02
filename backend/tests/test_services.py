"""服务层单元测试"""
import json
import pytest


class TestEmailService:
    """邮件服务测试"""
    
    @pytest.mark.asyncio
    async def test_generate_reset_token(self):
        """测试生成重置令牌"""
        from app.services.email_service import EmailService
        
        service = EmailService()
        token = await service.generate_reset_token(user_id=1, email="test@example.com")
        
        assert token is not None
        assert len(token) > 0
    
    @pytest.mark.asyncio
    async def test_verify_reset_token_valid(self):
        """测试验证有效令牌"""
        from app.services.email_service import EmailService
        
        service = EmailService()
        email = "test@example.com"
        token = await service.generate_reset_token(user_id=1, email=email)
        
        result = await service.verify_reset_token(token)
        assert result is not None
        assert result.get("email") == email
    
    @pytest.mark.asyncio
    async def test_verify_reset_token_invalid(self):
        """测试验证无效令牌"""
        from app.services.email_service import EmailService
        
        service = EmailService()
        result = await service.verify_reset_token("invalid_token")
        assert result is None


class TestCacheService:
    """缓存服务测试"""
    
    @pytest.mark.asyncio
    async def test_set_and_get(self):
        """测试设置和获取缓存"""
        from app.services.cache_service import cache_service
        
        await cache_service.set("test_key", "test_value", expire=60)
        result = await cache_service.get("test_key")
        
        assert result == "test_value"
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        """测试获取不存在的键"""
        from app.services.cache_service import cache_service
        
        result = await cache_service.get("nonexistent_key_12345")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete_key(self):
        """测试删除键"""
        from app.services.cache_service import cache_service
        
        await cache_service.set("delete_test", "value", expire=60)
        await cache_service.delete("delete_test")
        result = await cache_service.get("delete_test")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_set_and_get_json(self):
        """测试设置和获取JSON"""
        from app.services.cache_service import cache_service
        
        data = {"name": "test", "value": 123}
        await cache_service.set_json("json_test", data, expire=60)
        result = await cache_service.get_json("json_test")
        
        assert result == data


class TestValidators:
    """验证器测试"""
    
    def test_validate_phone_valid(self):
        """测试有效手机号"""
        from app.utils.validators import validate_phone
        
        assert validate_phone("13800138000") is True
        assert validate_phone("15912345678") is True
    
    def test_validate_phone_invalid(self):
        """测试无效手机号"""
        from app.utils.validators import validate_phone
        
        assert validate_phone("1234567890") is False
        assert validate_phone("12345678901") is False
        assert validate_phone("phone") is False
    
    def test_validate_email_valid(self):
        """测试有效邮箱"""
        from app.utils.validators import validate_email
        
        assert validate_email("test@example.com") is True
        assert validate_email("user.name@domain.org") is True
    
    def test_validate_email_invalid(self):
        """测试无效邮箱"""
        from app.utils.validators import validate_email
        
        assert validate_email("invalid") is False
        assert validate_email("@example.com") is False
        assert validate_email("test@") is False
    
    def test_validate_password_strength(self):
        """测试密码强度验证"""
        from app.utils.validators import validate_password_strength
        
        # 有效密码
        is_valid, msg = validate_password_strength("Test1234")
        assert is_valid is True
        
        # 太短
        is_valid, msg = validate_password_strength("Test1")
        assert is_valid is False
        
        # 缺少数字
        is_valid, msg = validate_password_strength("TestTest")
        assert is_valid is False
    
    def test_validate_username(self):
        """测试用户名验证"""
        from app.utils.validators import validate_username
        
        # 有效用户名
        is_valid, msg = validate_username("用户名123")
        assert is_valid is True
        
        is_valid, msg = validate_username("username_test")
        assert is_valid is True
        
        # 太短
        is_valid, msg = validate_username("a")
        assert is_valid is False
    
    def test_sanitize_html(self):
        """测试HTML清理"""
        from app.utils.validators import sanitize_html
        
        result = sanitize_html("<script>alert('xss')</script>Hello")
        assert "<script>" not in result
        assert "Hello" in result
    
    def test_input_validator_chain(self):
        """测试链式验证器"""
        from app.utils.validators import InputValidator
        
        validator = InputValidator()
        validator.required("test", "字段").min_length("test", 2, "字段")
        
        assert validator.is_valid() is True
        assert len(validator.get_errors()) == 0
        
        validator.reset().required("", "空字段")
        assert validator.is_valid() is False
        assert len(validator.get_errors()) == 1


class TestSecurity:
    """安全工具测试"""
    
    def test_hash_password(self):
        """测试密码哈希"""
        from app.utils.security import hash_password, verify_password
        
        password = "TestPassword123"
        hashed = hash_password(password)
        
        assert hashed != password
        assert verify_password(password, hashed) is True
        assert verify_password("wrong", hashed) is False
    
    def test_create_and_decode_token(self):
        """测试JWT创建和解码"""
        from app.utils.security import create_access_token, decode_token
        
        data: dict[str, object] = {"sub": "123"}
        token = create_access_token(data)
        
        decoded = decode_token(token)
        assert decoded is not None
        assert decoded.get("sub") == "123"
    
    def test_decode_invalid_token(self):
        """测试解码无效令牌"""
        from app.utils.security import decode_token
        
        result = decode_token("invalid.token.here")
        assert result is None


class TestNewsAIPipelineService:
    def test_extract_structured_output_limits(self):
        from app.services.news_ai_pipeline_service import NewsAIPipelineService

        text = json.dumps(
            {
                "summary": "  这是一个摘要  ",
                "highlights": ["  第一条要点很长很长  ", "第二条", "第三条"],
                "keywords": ["关键词A", "  关键词B  ", "关键词C", "关键词D"],
            },
            ensure_ascii=False,
        )

        summary, highlights, keywords = NewsAIPipelineService._extract_structured_output(
            text,
            highlights_max=2,
            keywords_max=3,
            item_max_chars=5,
        )
        assert summary == "这是一个摘要"
        assert highlights == ["第一条要点", "第二条"]
        assert keywords == ["关键词A", "关键词B", "关键词C"]

    @pytest.mark.asyncio
    async def test_llm_summarize_response_format_fallback(self, monkeypatch):
        import httpx

        from app.services.news_ai_pipeline_service import NewsAIPipelineService

        monkeypatch.setenv("NEWS_AI_SUMMARY_LLM_RESPONSE_FORMAT", "json_object")

        calls: list[dict] = []

        class FakeResponse:
            def __init__(self, status_code: int, payload: dict, *, text: str = ""):
                self.status_code = int(status_code)
                self._payload = payload
                self.text = text

            def json(self):
                return self._payload

            def raise_for_status(self):
                if int(self.status_code) >= 400:
                    req = httpx.Request("POST", "http://example.com")
                    resp = httpx.Response(int(self.status_code), request=req)
                    raise httpx.HTTPStatusError("error", request=req, response=resp)

        class FakeAsyncClient:
            def __init__(self, *args, **kwargs):
                _ = args
                _ = kwargs

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                _ = exc_type
                _ = exc
                _ = tb
                return False

            async def post(self, url, headers=None, json=None):
                _ = url
                _ = headers
                calls.append(json or {})
                if len(calls) == 1:
                    return FakeResponse(400, {"error": {"message": "response_format unsupported"}})
                return FakeResponse(
                    200,
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"summary":"S","highlights":["H1"],"keywords":["K1"]}'
                                }
                            }
                        ]
                    },
                )

        monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient, raising=True)

        svc = NewsAIPipelineService()
        out = await svc._llm_summarize(
            api_key="k",
            base_url="http://example.com",
            model="m",
            title="t",
            content="c",
            timeout_seconds=1.0,
            summary_max_chars=120,
            highlights_max=3,
            keywords_max=5,
        )

        assert isinstance(out, str)
        assert out.strip().startswith("{")
        assert len(calls) == 2
        assert "response_format" in calls[0]
        assert "response_format" not in calls[1]

    @pytest.mark.asyncio
    async def test_run_once_persists_highlights_keywords(self, test_session, monkeypatch):
        from sqlalchemy import select

        from app.models.news import News
        from app.models.news_ai import NewsAIAnnotation
        from app.services.news_ai_pipeline_service import NewsAIPipelineService

        monkeypatch.setenv("NEWS_AI_SUMMARY_WRITEBACK_ENABLED", "0")

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

        async def fake_make_summary(self, _news: News, *, env_overrides=None):
            _ = self
            _ = env_overrides
            return "AI摘要", True, ["要点一", "要点二"], ["关键词A", "关键词B"]

        def fake_make_risk(self, _news: News):
            return "safe", None

        async def fake_find_duplicate_of(self, _db, _news: News):
            return None

        monkeypatch.setattr(NewsAIPipelineService, "_make_summary", fake_make_summary, raising=True)
        monkeypatch.setattr(NewsAIPipelineService, "_make_risk", fake_make_risk, raising=True)
        monkeypatch.setattr(NewsAIPipelineService, "_find_duplicate_of", fake_find_duplicate_of, raising=True)

        svc = NewsAIPipelineService()
        res = await svc.run_once(test_session)

        assert int(res.get("processed", 0)) == 1
        assert int(res.get("created", 0)) == 1
        assert int(res.get("errors", 0)) == 0

        ann_res = await test_session.execute(
            select(NewsAIAnnotation).where(NewsAIAnnotation.news_id == int(news.id))
        )
        ann = ann_res.scalar_one_or_none()
        assert ann is not None
        assert ann.summary == "AI摘要"
        assert ann.highlights is not None
        assert ann.keywords is not None
        assert json.loads(ann.highlights) == ["要点一", "要点二"]
        assert json.loads(ann.keywords) == ["关键词A", "关键词B"]
        assert ann.processed_at is not None

    @pytest.mark.asyncio
    async def test_run_once_review_policy_updates_pending(self, test_session, monkeypatch):
        from app.models.news import News
        from app.services.news_ai_pipeline_service import NewsAIPipelineService

        monkeypatch.setenv("NEWS_AI_SUMMARY_WRITEBACK_ENABLED", "0")
        monkeypatch.setenv("NEWS_REVIEW_POLICY_ENABLED", "1")

        news = News(
            title="审核策略单测",
            summary=None,
            content="正文内容",
            category="法律动态",
            is_top=False,
            is_published=False,
            review_status="pending",
        )
        test_session.add(news)
        await test_session.commit()
        await test_session.refresh(news)

        async def fake_make_summary(self, _news: News, *, env_overrides=None):
            _ = self
            _ = env_overrides
            return "AI摘要", True, ["要点一"], ["关键词A"]

        def fake_make_risk(self, _news: News):
            return "safe", None

        async def fake_find_duplicate_of(self, _db, _news: News):
            return None

        monkeypatch.setattr(NewsAIPipelineService, "_make_summary", fake_make_summary, raising=True)
        monkeypatch.setattr(NewsAIPipelineService, "_make_risk", fake_make_risk, raising=True)
        monkeypatch.setattr(NewsAIPipelineService, "_find_duplicate_of", fake_find_duplicate_of, raising=True)

        svc = NewsAIPipelineService()
        res = await svc.run_once(test_session)
        assert int(res.get("processed", 0)) == 1

        await test_session.refresh(news)
        assert str(news.review_status) == "approved"
        assert getattr(news, "reviewed_at", None) is not None
        assert getattr(news, "review_reason", None) in {None, ""}

    @pytest.mark.asyncio
    async def test_make_summary_provider_api_key_fallback(self, test_session, monkeypatch):
        import json

        from app.config import get_settings
        from app.models.news import News
        from app.services.news_ai_pipeline_service import NewsAIPipelineService

        monkeypatch.setenv("OPENAI_API_KEY", "k_fallback")
        monkeypatch.setenv("OPENAI_BASE_URL", "http://unused")
        monkeypatch.setenv("AI_MODEL", "m_fallback")
        get_settings.cache_clear()

        monkeypatch.setenv("NEWS_AI_SUMMARY_LLM_ENABLED", "1")
        monkeypatch.setenv(
            "NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON",
            json.dumps(
                [
                    {"name": "p1", "base_url": "http://good", "model": "m1"},
                ],
                ensure_ascii=False,
            ),
        )

        received: dict[str, str] = {}

        async def fake_llm_summarize(self, *, api_key: str, base_url: str, **kwargs):
            _ = self
            _ = kwargs
            received["api_key"] = str(api_key)
            received["base_url"] = str(base_url)
            return '{"summary":"S","highlights":["H1"],"keywords":["K1"]}'

        monkeypatch.setattr(NewsAIPipelineService, "_llm_summarize", fake_llm_summarize, raising=True)

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

        svc = NewsAIPipelineService()
        summary, is_llm, highlights, keywords = await svc._make_summary(news)

        assert is_llm is True
        assert summary == "S"
        assert highlights == ["H1"]
        assert keywords == ["K1"]
        assert received.get("api_key") == "k_fallback"
        assert received.get("base_url") == "http://good"

    @pytest.mark.asyncio
    async def test_make_summary_provider_failover(self, test_session, monkeypatch):
        from app.models.news import News
        from app.services.news_ai_pipeline_service import NewsAIPipelineService

        monkeypatch.setenv("NEWS_AI_SUMMARY_LLM_ENABLED", "1")
        monkeypatch.setenv(
            "NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON",
            json.dumps(
                [
                    {"name": "bad", "base_url": "http://bad", "api_key": "k1", "model": "m1"},
                    {"name": "good", "base_url": "http://good", "api_key": "k2", "model": "m2"},
                ],
                ensure_ascii=False,
            ),
        )

        calls: list[str] = []

        async def fake_llm_summarize(self, *, base_url: str, **kwargs):
            _ = self
            _ = kwargs
            calls.append(str(base_url))
            if str(base_url).startswith("http://bad"):
                raise RuntimeError("provider down")
            return '{"summary":"S","highlights":["H1"],"keywords":["K1"]}'

        monkeypatch.setattr(NewsAIPipelineService, "_llm_summarize", fake_llm_summarize, raising=True)

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

        svc = NewsAIPipelineService()
        summary, is_llm, highlights, keywords = await svc._make_summary(news)

        assert is_llm is True
        assert summary == "S"
        assert highlights == ["H1"]
        assert keywords == ["K1"]
        assert calls == ["http://bad", "http://good"]

    @pytest.mark.asyncio
    async def test_load_system_config_overrides_env_suffix_preferred(self, test_session, monkeypatch):
        from app.models.system import SystemConfig
        from app.services.news_ai_pipeline_service import NewsAIPipelineService

        monkeypatch.setenv("APP_ENV", "production")

        test_session.add_all(
            [
                SystemConfig(
                    key="NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY",
                    value="random",
                    category="news_ai",
                ),
                SystemConfig(
                    key="NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY_PROD",
                    value="priority",
                    category="news_ai",
                ),
            ]
        )
        await test_session.commit()

        cfg = await NewsAIPipelineService.load_system_config_overrides(test_session)
        assert cfg.get("NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY") == "priority"

    @pytest.mark.asyncio
    async def test_make_summary_respects_priority_order(self, test_session, monkeypatch):
        from app.models.news import News
        from app.services.news_ai_pipeline_service import NewsAIPipelineService

        monkeypatch.setenv("NEWS_AI_SUMMARY_LLM_ENABLED", "1")
        monkeypatch.setenv("NEWS_AI_SUMMARY_LLM_PROVIDER_STRATEGY", "priority")
        monkeypatch.setenv(
            "NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON",
            json.dumps(
                [
                    {"name": "p2", "base_url": "http://p2", "api_key": "k2", "model": "m2", "priority": 2},
                    {"name": "p1", "base_url": "http://p1", "api_key": "k1", "model": "m1", "priority": 1},
                ],
                ensure_ascii=False,
            ),
        )

        calls: list[str] = []

        async def fake_llm_summarize(self, *, base_url: str, **kwargs):
            _ = self
            _ = kwargs
            calls.append(str(base_url))
            return '{"summary":"S","highlights":["H1"],"keywords":["K1"]}'

        monkeypatch.setattr(NewsAIPipelineService, "_llm_summarize", fake_llm_summarize, raising=True)

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

        svc = NewsAIPipelineService()
        summary, is_llm, highlights, keywords = await svc._make_summary(news)

        assert is_llm is True
        assert summary == "S"
        assert highlights == ["H1"]
        assert keywords == ["K1"]
        assert calls == ["http://p1"]

    @pytest.mark.asyncio
    async def test_get_summary_llm_providers_name_only_from_env(self, monkeypatch):
        from app.config import get_settings
        from app.services.news_ai_pipeline_service import NewsAIPipelineService

        monkeypatch.setenv("OPENAI_API_KEY", "k_openai")
        monkeypatch.setenv("OPENAI_BASE_URL", "http://openai")
        monkeypatch.setenv("AI_MODEL", "m_openai")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "k_azure")
        monkeypatch.setenv("AZURE_OPENAI_BASE_URL", "http://azure")
        monkeypatch.setenv("AZURE_OPENAI_MODEL", "m_azure")
        get_settings.cache_clear()

        providers_json = json.dumps(
            [
                {"name": "openai", "priority": 1},
                {"name": "azure-openai", "priority": 2},
            ],
            ensure_ascii=False,
        )

        settings = get_settings()
        svc = NewsAIPipelineService()
        providers = svc.get_summary_llm_providers(
            settings,
            env_overrides={"NEWS_AI_SUMMARY_LLM_PROVIDERS_JSON": providers_json},
        )

        assert len(providers) == 2
        by_name = {str(p.get("name")): p for p in providers}

        p1 = by_name.get("openai")
        assert p1 is not None
        assert str(p1.get("base_url")) == "http://openai"
        assert str(p1.get("api_key")) == "k_openai"

        p2 = by_name.get("azure-openai")
        assert p2 is not None
        assert str(p2.get("base_url")) == "http://azure"
        assert str(p2.get("api_key")) == "k_azure"
        assert str(p2.get("model")) == "m_azure"
