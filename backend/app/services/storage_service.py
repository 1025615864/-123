import asyncio
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol

from ..config import get_settings


@dataclass(frozen=True)
class StoredObject:
    category: str
    filename: str
    key: str
    url: str


class StorageProvider(Protocol):
    name: str

    async def put_bytes(
        self,
        *,
        category: str,
        filename: str,
        content: bytes,
        content_type: str | None,
    ) -> StoredObject: ...

    async def get_download_url(self, *, category: str, filename: str) -> str: ...


def _norm_provider(value: str | None) -> str:
    s = str(value or "").strip().lower()
    if not s:
        return "local"
    if s in {"fs", "file", "filesystem"}:
        return "local"
    return s


def _join_url(base: str, *parts: str) -> str:
    b = str(base or "").strip().rstrip("/")
    cleaned = [str(p).strip().strip("/") for p in parts if str(p).strip().strip("/")]
    if not cleaned:
        return b
    return b + "/" + "/".join(cleaned)


class LocalStorageProvider:
    name = "local"

    def __init__(self, *, base_dir: str, api_prefix: str = "/api/upload"):
        self.base_dir = str(base_dir)
        self.api_prefix = str(api_prefix).rstrip("/")

    def _dir_for(self, category: str) -> str:
        safe_category = str(category).strip().strip("/")
        return os.path.join(self.base_dir, safe_category)

    def _path_for(self, category: str, filename: str) -> str:
        return os.path.join(self._dir_for(category), str(filename))

    async def put_bytes(
        self,
        *,
        category: str,
        filename: str,
        content: bytes,
        content_type: str | None,
    ) -> StoredObject:
        _ = content_type
        dst_dir = self._dir_for(category)
        dst_path = self._path_for(category, filename)

        def _write() -> None:
            os.makedirs(dst_dir, exist_ok=True)
            with open(dst_path, "wb") as f:
                _ = f.write(content)

        await asyncio.to_thread(_write)

        url = f"{self.api_prefix}/{str(category).strip().strip('/')}/{str(filename)}"
        return StoredObject(category=category, filename=filename, key=dst_path, url=url)

    async def get_download_url(self, *, category: str, filename: str) -> str:
        _ = category
        _ = filename
        raise RuntimeError("local provider does not support external download url")

    def get_local_path(self, *, category: str, filename: str) -> str:
        return self._path_for(category, filename)


class S3CompatibleStorageProvider:
    name = "s3"

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str | None,
        region_name: str | None,
        access_key_id: str | None,
        secret_access_key: str | None,
        public_base_url: str,
        prefix: str,
    ):
        self.bucket = str(bucket).strip()
        self.endpoint_url = str(endpoint_url or "").strip() or None
        self.region_name = str(region_name or "").strip() or None
        self.access_key_id = str(access_key_id or "").strip() or None
        self.secret_access_key = str(secret_access_key or "").strip() or None
        self.public_base_url = str(public_base_url).strip()
        self.prefix = str(prefix or "uploads").strip().strip("/") or "uploads"

    def _key_for(self, category: str, filename: str) -> str:
        return "/".join(
            p
            for p in (
                self.prefix,
                str(category).strip().strip("/"),
                str(filename).strip().strip("/"),
            )
            if p
        )

    def _make_client(self) -> Any:
        import boto3

        kwargs: dict[str, Any] = {}
        if self.endpoint_url:
            kwargs["endpoint_url"] = self.endpoint_url
        if self.region_name:
            kwargs["region_name"] = self.region_name
        if self.access_key_id and self.secret_access_key:
            kwargs["aws_access_key_id"] = self.access_key_id
            kwargs["aws_secret_access_key"] = self.secret_access_key
        return boto3.client("s3", **kwargs)

    async def put_bytes(
        self,
        *,
        category: str,
        filename: str,
        content: bytes,
        content_type: str | None,
    ) -> StoredObject:
        key = self._key_for(category, filename)

        def _upload() -> None:
            client = self._make_client()
            put_kwargs: dict[str, Any] = {
                "Bucket": self.bucket,
                "Key": key,
                "Body": content,
            }
            if content_type:
                put_kwargs["ContentType"] = str(content_type)
            client.put_object(**put_kwargs)

        await asyncio.to_thread(_upload)

        url = _join_url(self.public_base_url, key)
        return StoredObject(category=category, filename=filename, key=key, url=url)

    async def get_download_url(self, *, category: str, filename: str) -> str:
        key = self._key_for(category, filename)
        return _join_url(self.public_base_url, key)


@lru_cache()
def get_storage_provider() -> StorageProvider:
    settings = get_settings()
    provider = _norm_provider(getattr(settings, "storage_provider", None))

    if provider == "s3":
        return S3CompatibleStorageProvider(
            bucket=str(getattr(settings, "storage_s3_bucket", "") or "").strip(),
            endpoint_url=getattr(settings, "storage_s3_endpoint_url", None),
            region_name=getattr(settings, "storage_s3_region", None),
            access_key_id=getattr(settings, "storage_s3_access_key_id", None),
            secret_access_key=getattr(settings, "storage_s3_secret_access_key", None),
            public_base_url=str(getattr(settings, "storage_public_base_url", "") or "").strip(),
            prefix=str(getattr(settings, "storage_s3_prefix", "uploads") or "uploads"),
        )

    here = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    base_dir = os.path.join(here, "uploads")
    return LocalStorageProvider(base_dir=base_dir)
