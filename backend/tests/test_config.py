import app.config as config


def test_parse_cors_allow_origins_from_string() -> None:
    out = config.Settings._parse_cors_allow_origins("http://a.com， http://b.com, ,http://a.com")
    assert out == ["http://a.com", "http://b.com", "http://a.com"]


def test_parse_ai_fallback_models() -> None:
    assert config.Settings._parse_ai_fallback_models(None) == []
    assert config.Settings._parse_ai_fallback_models("a，b, a") == ["a", "b"]
    assert config.Settings._parse_ai_fallback_models(["a", " ", "b", "a"]) == ["a", "b"]
    assert config.Settings._parse_ai_fallback_models(123) == ["123"]


def test_parse_debug_variants(monkeypatch) -> None:
    monkeypatch.setattr(config, "_running_tests", lambda: False, raising=True)
    assert config.Settings._parse_debug(None) is False
    assert config.Settings._parse_debug(True) is True
    assert config.Settings._parse_debug(0) is False
    assert config.Settings._parse_debug(1) is True
    assert config.Settings._parse_debug("0") is False
    assert config.Settings._parse_debug("false") is False
    assert config.Settings._parse_debug("") is False
    assert config.Settings._parse_debug("maybe") is True


def test_resolve_env_files_explicit(monkeypatch) -> None:
    monkeypatch.setattr(config, "_running_tests", lambda: False, raising=True)
    monkeypatch.setenv("ENV_FILE", "D:/tmp/.env")
    assert config._resolve_env_files() == ["D:/tmp/.env"]


def test_validate_security_raises_when_debug_false_insecure_secret(monkeypatch) -> None:
    monkeypatch.setattr(config, "_running_tests", lambda: False, raising=True)
    monkeypatch.setenv("SECRET_KEY", "your-super-secret-key-change-in-production")
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET", "1234567890abcdef")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")

    try:
        config.Settings(debug=False)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "SECRET_KEY" in str(e)


def test_validate_security_raises_when_debug_false_webhook_missing(monkeypatch) -> None:
    monkeypatch.setattr(config, "_running_tests", lambda: False, raising=True)
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.delenv("PAYMENT_WEBHOOK_SECRET", raising=False)
    try:
        config.Settings(debug=False)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "PAYMENT_WEBHOOK_SECRET" in str(e)


def test_validate_security_raises_when_debug_false_redis_missing(monkeypatch) -> None:
    monkeypatch.setattr(config, "_running_tests", lambda: False, raising=True)
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET", "1234567890abcdef")
    try:
        config.Settings(debug=False)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "REDIS_URL" in str(e)


def test_validate_security_raises_s3_bucket_missing(monkeypatch) -> None:
    monkeypatch.setattr(config, "_running_tests", lambda: False, raising=True)
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET", "1234567890abcdef")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("STORAGE_PROVIDER", "s3")
    monkeypatch.setenv("STORAGE_PUBLIC_BASE_URL", "http://cdn")
    try:
        config.Settings(debug=False)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "STORAGE_S3_BUCKET" in str(e)


def test_validate_security_raises_s3_keys_pair(monkeypatch) -> None:
    monkeypatch.setattr(config, "_running_tests", lambda: False, raising=True)
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setenv("PAYMENT_WEBHOOK_SECRET", "1234567890abcdef")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("STORAGE_PROVIDER", "local")
    monkeypatch.setenv("STORAGE_S3_ACCESS_KEY_ID", "ak")
    try:
        config.Settings(debug=False)
        assert False, "expected ValueError"
    except ValueError as e:
        assert "STORAGE_S3_ACCESS_KEY_ID" in str(e)


def test_get_settings_is_cached(monkeypatch) -> None:
    try:
        config.get_settings.cache_clear()
    except Exception:
        pass
    s1 = config.get_settings()
    s2 = config.get_settings()
    assert s1 is s2
