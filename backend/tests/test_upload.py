import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_upload_image_local_provider_serves_file(client: AsyncClient, test_session, monkeypatch, tmp_path):
    from app.models.user import User
    from app.utils.security import create_access_token, hash_password
    from app.routers import upload as upload_router
    from app.services.storage_service import LocalStorageProvider

    user = User(
        username="u_upload_local",
        email="u_upload_local@example.com",
        nickname="u_upload_local",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    provider = LocalStorageProvider(base_dir=str(tmp_path))
    monkeypatch.setattr(upload_router, "get_storage_provider", lambda: provider)

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    res = await client.post(
        "/api/upload/image",
        files={"file": ("a.png", png_bytes, "image/png")},
        headers=headers,
    )
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_upload_image_moderation_rejects(client: AsyncClient, test_session, monkeypatch, tmp_path):
    from app.models.user import User
    from app.utils.security import create_access_token, hash_password
    from app.routers import upload as upload_router
    from app.services.storage_service import LocalStorageProvider

    user = User(
        username="u_upload_mod_reject",
        email="u_upload_mod_reject@example.com",
        nickname="u_upload_mod_reject",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    provider = LocalStorageProvider(base_dir=str(tmp_path))
    monkeypatch.setattr(upload_router, "get_storage_provider", lambda: provider)
    monkeypatch.setenv("UPLOAD_IMAGE_MODERATION_ENABLED", "1")
    monkeypatch.setenv("UPLOAD_IMAGE_MODERATION_FAIL_OPEN", "0")

    async def _fake_moderate(*, content: bytes, content_type: str | None):
        _ = content
        _ = content_type
        return False, "nope"

    monkeypatch.setattr(upload_router, "_moderate_image_via_webhook", _fake_moderate, raising=True)

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    res = await client.post(
        "/api/upload/image",
        files={"file": ("a.png", png_bytes, "image/png")},
        headers=headers,
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_upload_image_moderation_error_fail_closed(client: AsyncClient, test_session, monkeypatch, tmp_path):
    from app.models.user import User
    from app.utils.security import create_access_token, hash_password
    from app.routers import upload as upload_router
    from app.services.storage_service import LocalStorageProvider

    user = User(
        username="u_upload_mod_err",
        email="u_upload_mod_err@example.com",
        nickname="u_upload_mod_err",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    provider = LocalStorageProvider(base_dir=str(tmp_path))
    monkeypatch.setattr(upload_router, "get_storage_provider", lambda: provider)
    monkeypatch.setenv("UPLOAD_IMAGE_MODERATION_ENABLED", "1")
    monkeypatch.setenv("UPLOAD_IMAGE_MODERATION_FAIL_OPEN", "0")

    async def _fake_moderate(*, content: bytes, content_type: str | None):
        _ = content
        _ = content_type
        raise RuntimeError("moderation down")

    monkeypatch.setattr(upload_router, "_moderate_image_via_webhook", _fake_moderate, raising=True)

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    res = await client.post(
        "/api/upload/image",
        files={"file": ("a.png", png_bytes, "image/png")},
        headers=headers,
    )
    assert res.status_code == 503


@pytest.mark.asyncio
async def test_upload_image_moderation_error_fail_open(client: AsyncClient, test_session, monkeypatch, tmp_path):
    from app.models.user import User
    from app.utils.security import create_access_token, hash_password
    from app.routers import upload as upload_router
    from app.services.storage_service import LocalStorageProvider

    user = User(
        username="u_upload_mod_open",
        email="u_upload_mod_open@example.com",
        nickname="u_upload_mod_open",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    provider = LocalStorageProvider(base_dir=str(tmp_path))
    monkeypatch.setattr(upload_router, "get_storage_provider", lambda: provider)
    monkeypatch.setenv("UPLOAD_IMAGE_MODERATION_ENABLED", "1")
    monkeypatch.setenv("UPLOAD_IMAGE_MODERATION_FAIL_OPEN", "1")

    async def _fake_moderate(*, content: bytes, content_type: str | None):
        _ = content
        _ = content_type
        raise RuntimeError("moderation down")

    monkeypatch.setattr(upload_router, "_moderate_image_via_webhook", _fake_moderate, raising=True)

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    res = await client.post(
        "/api/upload/image",
        files={"file": ("a.png", png_bytes, "image/png")},
        headers=headers,
    )
    assert res.status_code == 200
    payload = res.json()
    url = str(payload.get("url") or "")
    assert url.startswith("/api/upload/images/")

    res2 = await client.get(url)
    assert res2.status_code == 200
    assert res2.content == png_bytes


@pytest.mark.asyncio
async def test_get_image_s3_provider_redirects(client: AsyncClient, monkeypatch):
    from app.routers import upload as upload_router

    class FakeS3Provider:
        name = "s3"

        async def put_bytes(self, *, category: str, filename: str, content: bytes, content_type: str | None):
            _ = category
            _ = filename
            _ = content
            _ = content_type
            return None

        async def get_download_url(self, *, category: str, filename: str) -> str:
            return f"https://example-bucket.invalid/{category}/{filename}"

    monkeypatch.setattr(upload_router, "get_storage_provider", lambda: FakeS3Provider())

    filename = "a" * 32 + ".png"
    res = await client.get(f"/api/upload/images/{filename}")
    assert res.status_code == 307
    assert res.headers.get("location") == f"https://example-bucket.invalid/images/{filename}"


@pytest.mark.asyncio
async def test_upload_image_local_provider_blocked_when_require_object_storage(
    client: AsyncClient,
    test_session,
    monkeypatch,
    tmp_path,
):
    from app.models.user import User
    from app.utils.security import create_access_token, hash_password
    from app.routers import upload as upload_router
    from app.services.storage_service import LocalStorageProvider

    user = User(
        username="u_upload_blocked",
        email="u_upload_blocked@example.com",
        nickname="u_upload_blocked",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    provider = LocalStorageProvider(base_dir=str(tmp_path))
    monkeypatch.setattr(upload_router, "get_storage_provider", lambda: provider)
    monkeypatch.setenv("UPLOAD_REQUIRE_OBJECT_STORAGE", "1")
    monkeypatch.delenv("UPLOAD_ALLOW_LOCAL_STORAGE", raising=False)

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    res = await client.post(
        "/api/upload/image",
        files={"file": ("a.png", png_bytes, "image/png")},
        headers=headers,
    )
    assert res.status_code == 503


@pytest.mark.asyncio
async def test_upload_image_virus_scan_found_rejected(client: AsyncClient, test_session, monkeypatch, tmp_path):
    from app.models.user import User
    from app.utils.security import create_access_token, hash_password
    from app.routers import upload as upload_router
    from app.services.storage_service import LocalStorageProvider

    user = User(
        username="u_upload_virus",
        email="u_upload_virus@example.com",
        nickname="u_upload_virus",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    provider = LocalStorageProvider(base_dir=str(tmp_path))
    monkeypatch.setattr(upload_router, "get_storage_provider", lambda: provider)
    monkeypatch.setenv("UPLOAD_VIRUS_SCAN_ENABLED", "1")
    monkeypatch.setenv("UPLOAD_VIRUS_SCAN_FAIL_OPEN", "0")

    async def _fake_scan(_content: bytes):
        return "FOUND", "stream: Eicar-Test-Signature FOUND"

    monkeypatch.setattr(upload_router, "_scan_bytes_with_clamd", _fake_scan, raising=True)

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    res = await client.post(
        "/api/upload/image",
        files={"file": ("a.png", png_bytes, "image/png")},
        headers=headers,
    )
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_upload_image_virus_scan_error_fail_closed(client: AsyncClient, test_session, monkeypatch, tmp_path):
    from app.models.user import User
    from app.utils.security import create_access_token, hash_password
    from app.routers import upload as upload_router
    from app.services.storage_service import LocalStorageProvider

    user = User(
        username="u_upload_scan_err",
        email="u_upload_scan_err@example.com",
        nickname="u_upload_scan_err",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    provider = LocalStorageProvider(base_dir=str(tmp_path))
    monkeypatch.setattr(upload_router, "get_storage_provider", lambda: provider)
    monkeypatch.setenv("UPLOAD_VIRUS_SCAN_ENABLED", "1")
    monkeypatch.setenv("UPLOAD_VIRUS_SCAN_FAIL_OPEN", "0")

    async def _fake_scan(_content: bytes):
        return "ERROR", "stream: ERROR"

    monkeypatch.setattr(upload_router, "_scan_bytes_with_clamd", _fake_scan, raising=True)

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    res = await client.post(
        "/api/upload/image",
        files={"file": ("a.png", png_bytes, "image/png")},
        headers=headers,
    )
    assert res.status_code == 503


@pytest.mark.asyncio
async def test_upload_image_virus_scan_error_fail_open(client: AsyncClient, test_session, monkeypatch, tmp_path):
    from app.models.user import User
    from app.utils.security import create_access_token, hash_password
    from app.routers import upload as upload_router
    from app.services.storage_service import LocalStorageProvider

    user = User(
        username="u_upload_scan_open",
        email="u_upload_scan_open@example.com",
        nickname="u_upload_scan_open",
        hashed_password=hash_password("Test123456"),
        role="user",
        is_active=True,
    )
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    token = create_access_token({"sub": str(user.id)})
    headers = {"Authorization": f"Bearer {token}"}

    provider = LocalStorageProvider(base_dir=str(tmp_path))
    monkeypatch.setattr(upload_router, "get_storage_provider", lambda: provider)
    monkeypatch.setenv("UPLOAD_VIRUS_SCAN_ENABLED", "1")
    monkeypatch.setenv("UPLOAD_VIRUS_SCAN_FAIL_OPEN", "1")

    async def _fake_scan(_content: bytes):
        raise RuntimeError("clamd unavailable")

    monkeypatch.setattr(upload_router, "_scan_bytes_with_clamd", _fake_scan, raising=True)

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"0" * 16
    res = await client.post(
        "/api/upload/image",
        files={"file": ("a.png", png_bytes, "image/png")},
        headers=headers,
    )
    assert res.status_code == 200
