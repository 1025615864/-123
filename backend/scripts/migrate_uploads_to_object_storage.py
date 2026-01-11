from __future__ import annotations

import argparse
import mimetypes
import sys
from pathlib import Path
import asyncio


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_import_path() -> None:
    backend_dir = _backend_dir()
    sys.path.insert(0, str(backend_dir))


def _iter_files(root: Path) -> list[Path]:
    if not root.exists() or not root.is_dir():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


def _guess_content_type(path: Path) -> str | None:
    ctype, _ = mimetypes.guess_type(str(path))
    return ctype


async def _run_migration(*, src_dir: Path, categories: list[str], dry_run: bool, delete_after: bool) -> int:
    from app.services.storage_service import get_storage_provider, LocalStorageProvider

    storage = get_storage_provider()
    if isinstance(storage, LocalStorageProvider):
        raise RuntimeError(
            "Storage provider is 'local'. Set STORAGE_PROVIDER=s3 and configure STORAGE_* env vars before running."
        )

    total_files = 0
    uploaded = 0
    skipped = 0

    for category in categories:
        cat_dir = src_dir / category
        files = _iter_files(cat_dir)
        if not files:
            continue

        for path in files:
            rel = path.relative_to(cat_dir)

            # IMPORTANT: API routes use `/files/{filename}` (not `{filename:path}`),
            # so filename must NOT contain `/` or `\`.
            if len(rel.parts) != 1:
                print(f"[SKIP] nested path not supported for API filename: {category}/{rel} <- {path}")
                skipped += 1
                continue

            filename = rel.name
            total_files += 1

            if dry_run:
                print(f"[DRY] {category}/{filename} <- {path}")
                skipped += 1
                continue

            content = path.read_bytes()
            content_type = _guess_content_type(path)

            _ = await storage.put_bytes(
                category=str(category),
                filename=filename,
                content=content,
                content_type=content_type,
            )

            uploaded += 1
            print(f"[OK] {category}/{filename}")

            if delete_after:
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    print(f"[WARN] failed to delete {path}")

    print(f"Done. total={total_files} uploaded={uploaded} dry_run_skipped={skipped if dry_run else 0}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Migrate local uploads to object storage (S3-compatible). "
            "Run with STORAGE_PROVIDER=s3 and required STORAGE_* env vars. "
            "This script uploads files under backend/uploads/<category> to the configured storage provider."
        )
    )
    _ = parser.add_argument(
        "--src",
        default=None,
        help=(
            "Source uploads directory. Default: <backend>/uploads (i.e. backend/uploads)."
        ),
    )
    _ = parser.add_argument(
        "--category",
        action="append",
        default=[],
        help=(
            "Only migrate a specific category subfolder (e.g. avatars/images/files). "
            "Can be repeated. Default: migrate all categories under src."
        ),
    )
    _ = parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only list files to be uploaded, do not upload.",
    )
    _ = parser.add_argument(
        "--delete-after",
        action="store_true",
        help="Delete local files after successful upload (dangerous).",
    )

    args: argparse.Namespace = parser.parse_args(sys.argv[1:] if argv is None else argv)

    _ensure_import_path()

    backend_dir = _backend_dir()
    src_dir = Path(args.src).resolve() if args.src else (backend_dir / "uploads")

    if not src_dir.exists() or not src_dir.is_dir():
        raise RuntimeError(f"Source uploads directory does not exist: {src_dir}")

    categories: list[str]
    if args.category:
        categories = [str(c).strip().strip("/").strip("\\") for c in args.category if str(c).strip()]
    else:
        categories = [p.name for p in src_dir.iterdir() if p.is_dir()]

    return asyncio.run(
        _run_migration(
            src_dir=src_dir,
            categories=categories,
            dry_run=bool(args.dry_run),
            delete_after=bool(args.delete_after),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
