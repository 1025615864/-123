import argparse
import asyncio
import os
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from sqlalchemy.engine import make_url

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def _default_database_url() -> str:
    try:
        from app.config import get_settings

        return str(get_settings().database_url)
    except Exception:
        return "sqlite+aiosqlite:///./data/app.db"


def _effective_database_url(override: str | None) -> str:
    if override and str(override).strip():
        return str(override).strip()
    env = os.getenv("DATABASE_URL")
    if env and env.strip():
        return env.strip()
    return _default_database_url()


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _resolve_sqlite_path(url_str: str) -> Path:
    url = make_url(url_str)
    db = url.database or ""
    if db in {":memory:", ""}:
        raise SystemExit("sqlite in-memory database cannot be backed up via file path")
    p = Path(db)
    if not p.is_absolute():
        p = (_backend_root() / p).resolve()
    return p


def _to_sync_db_url(url_str: str) -> str:
    url = make_url(url_str)
    driver = str(url.drivername or "")
    if "+" in driver:
        url = url.set(drivername=driver.split("+", 1)[0])
    return str(url)


def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def backup_sqlite(database_url: str, output_path: Path) -> None:
    src = _resolve_sqlite_path(database_url)
    if not src.exists():
        raise SystemExit(f"sqlite db file not found: {src}")

    _ensure_parent(output_path)

    src_conn = sqlite3.connect(str(src))
    try:
        dst_conn = sqlite3.connect(str(output_path))
        try:
            src_conn.backup(dst_conn)
            dst_conn.execute("PRAGMA integrity_check")
            dst_conn.commit()
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def _require_exe(name: str) -> str:
    exe = shutil.which(name)
    if not exe:
        raise SystemExit(f"required executable not found in PATH: {name}")
    return exe


async def _async_verify_postgres_connection(database_url: str) -> None:
    try:
        import asyncpg
    except Exception as e:
        raise SystemExit(f"asyncpg is required to verify postgres connection: {e}")

    url = make_url(database_url)
    if str(url.get_backend_name()) != "postgresql":
        raise SystemExit("postgres connection verify requires a postgresql database url")

    conn = await asyncpg.connect(
        user=url.username,
        password=url.password,
        host=url.host,
        port=url.port or 5432,
        database=url.database,
    )
    try:
        _ = await conn.fetchval("SELECT 1")
    finally:
        await conn.close()


def verify_postgres_connection(database_url: str) -> None:
    asyncio.run(_async_verify_postgres_connection(database_url))


def _prune_backups(
    backups_dir: Path,
    *,
    prefix: str,
    retention_count: int | None,
    retention_days: int | None,
) -> None:
    if retention_count is None and retention_days is None:
        return

    backups_dir = backups_dir.resolve()
    if not backups_dir.exists():
        return

    candidates = [p for p in backups_dir.glob(f"{prefix}_*") if p.is_file()]
    if not candidates:
        return

    if retention_days is not None and retention_days > 0:
        cutoff = datetime.now().timestamp() - (retention_days * 86400)
        for p in list(candidates):
            try:
                if p.stat().st_mtime < cutoff:
                    p.unlink()
                    candidates.remove(p)
            except Exception:
                pass

    if retention_count is not None and retention_count >= 0:
        candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        for p in candidates[retention_count:]:
            try:
                p.unlink()
            except Exception:
                pass


def backup_postgres(database_url: str, output_path: Path) -> None:
    pg_dump = _require_exe("pg_dump")
    _ensure_parent(output_path)

    sync_url = _to_sync_db_url(database_url)

    cmd = [
        pg_dump,
        "--no-owner",
        "--no-privileges",
        "-Fc",
        "-f",
        str(output_path),
        "--dbname",
        sync_url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"pg_dump failed: {err}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--verify", action="store_true", help="verify postgres connectivity before backup")
    parser.add_argument("--retention-count", type=int, default=None)
    parser.add_argument("--retention-days", type=int, default=None)
    args = parser.parse_args()

    database_url = _effective_database_url(args.database_url)
    url = make_url(database_url)
    backend = _backend_root()

    if args.output and str(args.output).strip():
        output = Path(str(args.output)).expanduser()
        if not output.is_absolute():
            output = (backend / output).resolve()
    else:
        backups_dir = backend / "backups"
        if str(url.get_backend_name()) == "sqlite":
            output = backups_dir / f"sqlite_{_timestamp()}.db"
        else:
            output = backups_dir / f"postgres_{_timestamp()}.dump"

    if str(url.get_backend_name()) == "sqlite":
        backup_sqlite(database_url, output)
    else:
        if bool(args.verify):
            verify_postgres_connection(database_url)
        backup_postgres(database_url, output)

    if (
        str(url.get_backend_name()) in {"sqlite", "postgresql"}
        and output.resolve().parent == (backend / "backups").resolve()
    ):
        prefix = "sqlite" if str(url.get_backend_name()) == "sqlite" else "postgres"
        _prune_backups(
            backend / "backups",
            prefix=prefix,
            retention_count=args.retention_count,
            retention_days=args.retention_days,
        )

    print(str(output))


if __name__ == "__main__":
    main()
