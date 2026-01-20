import os
import sys
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_storage_service_helpers_and_local_provider(tmp_path):
    from app.services import storage_service

    assert storage_service._norm_provider(None) == "local"
    assert storage_service._norm_provider("") == "local"
    assert storage_service._norm_provider("filesystem") == "local"
    assert storage_service._norm_provider("S3") == "s3"

    assert storage_service._join_url("http://a/", "/b/", "c") == "http://a/b/c"
    assert storage_service._join_url("http://a", "", "  ") == "http://a"

    provider = storage_service.LocalStorageProvider(base_dir=str(tmp_path), api_prefix="/api/upload")

    obj = await provider.put_bytes(
        category="images",
        filename="a.txt",
        content=b"hello",
        content_type="text/plain",
    )

    assert obj.category == "images"
    assert obj.filename == "a.txt"
    assert obj.url == "/api/upload/images/a.txt"
    assert os.path.exists(obj.key)
    with open(obj.key, "rb") as f:
        assert f.read() == b"hello"

    assert provider.get_local_path(category="images", filename="a.txt") == obj.key

    with pytest.raises(RuntimeError):
        await provider.get_download_url(category="images", filename="a.txt")


@pytest.mark.asyncio
async def test_storage_service_s3_provider_put_and_urls(monkeypatch):
    from app.services import storage_service

    called: list[dict[str, object]] = []
    client_kwargs: list[dict[str, object]] = []

    class _FakeClient:
        def put_object(self, **kwargs):
            called.append(dict(kwargs))

    class _FakeBoto3:
        @staticmethod
        def client(_name, **_kwargs):
            client_kwargs.append(dict(_kwargs))
            return _FakeClient()

    monkeypatch.setitem(sys.modules, "boto3", _FakeBoto3)

    provider = storage_service.S3CompatibleStorageProvider(
        bucket="b",
        endpoint_url="",
        region_name=None,
        access_key_id=None,
        secret_access_key=None,
        public_base_url="https://cdn.example.com/",
        prefix="uploads",
    )

    obj = await provider.put_bytes(
        category="docs",
        filename="x.pdf",
        content=b"data",
        content_type="application/pdf",
    )

    assert obj.key == "uploads/docs/x.pdf"
    assert obj.url == "https://cdn.example.com/uploads/docs/x.pdf"
    assert len(called) == 1
    assert called[0]["Bucket"] == "b"
    assert called[0]["Key"] == "uploads/docs/x.pdf"
    assert called[0]["Body"] == b"data"
    assert called[0]["ContentType"] == "application/pdf"

    u = await provider.get_download_url(category="docs", filename="x.pdf")
    assert u == "https://cdn.example.com/uploads/docs/x.pdf"

    called.clear()
    client_kwargs.clear()
    provider2 = storage_service.S3CompatibleStorageProvider(
        bucket="b",
        endpoint_url="https://s3.example.com",
        region_name="ap-southeast-1",
        access_key_id="ak",
        secret_access_key="sk",
        public_base_url="https://cdn.example.com/",
        prefix="uploads",
    )
    _ = await provider2.put_bytes(
        category="docs",
        filename="y.pdf",
        content=b"data2",
        content_type=None,
    )
    assert len(client_kwargs) == 1
    assert client_kwargs[0]["endpoint_url"] == "https://s3.example.com"
    assert client_kwargs[0]["region_name"] == "ap-southeast-1"
    assert client_kwargs[0]["aws_access_key_id"] == "ak"
    assert client_kwargs[0]["aws_secret_access_key"] == "sk"


@pytest.mark.asyncio
async def test_get_storage_provider_selects_s3_and_local(monkeypatch):
    from app.services import storage_service

    storage_service.get_storage_provider.cache_clear()

    monkeypatch.setattr(
        storage_service,
        "get_settings",
        lambda: SimpleNamespace(
            storage_provider="s3",
            storage_s3_bucket="bucket",
            storage_s3_endpoint_url="",
            storage_s3_region="",
            storage_s3_access_key_id="",
            storage_s3_secret_access_key="",
            storage_public_base_url="https://cdn.example.com",
            storage_s3_prefix="uploads",
        ),
        raising=True,
    )

    p1 = storage_service.get_storage_provider()
    assert getattr(p1, "name", None) == "s3"

    storage_service.get_storage_provider.cache_clear()

    monkeypatch.setattr(
        storage_service,
        "get_settings",
        lambda: SimpleNamespace(storage_provider="filesystem"),
        raising=True,
    )

    p2 = storage_service.get_storage_provider()
    assert getattr(p2, "name", None) == "local"
