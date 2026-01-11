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
