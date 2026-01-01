import argparse
import asyncio
import os
import shutil
import sqlite3
import subprocess
import sys
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
        raise SystemExit("sqlite in-memory database cannot be restored via file path")
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


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


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


def restore_sqlite(database_url: str, backup_path: Path, *, force: bool) -> None:
    target = _resolve_sqlite_path(database_url)
    backup_path = backup_path.resolve()
    if not backup_path.exists():
        raise SystemExit(f"backup file not found: {backup_path}")

    _ensure_parent(target)

    if target.exists() and not force:
        raise SystemExit(f"target db already exists: {target} (use --force to overwrite)")

    tmp = target.with_suffix(target.suffix + ".restore_tmp")
    if tmp.exists():
        tmp.unlink()

    src_conn = sqlite3.connect(str(backup_path))
    try:
        dst_conn = sqlite3.connect(str(tmp))
        try:
            src_conn.backup(dst_conn)
            dst_conn.execute("PRAGMA integrity_check")
            dst_conn.commit()
        finally:
            dst_conn.close()
    finally:
        src_conn.close()

    os.replace(str(tmp), str(target))


def restore_postgres(database_url: str, backup_path: Path) -> None:
    pg_restore = _require_exe("pg_restore")

    backup_path = backup_path.resolve()
    if not backup_path.exists():
        raise SystemExit(f"backup file not found: {backup_path}")

    sync_url = _to_sync_db_url(database_url)

    cmd = [
        pg_restore,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--dbname",
        sync_url,
        str(backup_path),
    ]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"pg_restore failed: {err}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("backup", help="backup file path to restore from")
    parser.add_argument("--database-url", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--verify", action="store_true", help="verify postgres connectivity before restore")
    args = parser.parse_args()

    database_url = _effective_database_url(args.database_url)
    url = make_url(database_url)
    backup_path = Path(str(args.backup)).expanduser()
    if not backup_path.is_absolute():
        backup_path = (_backend_root() / backup_path).resolve()

    if str(url.get_backend_name()) == "sqlite":
        restore_sqlite(database_url, backup_path, force=bool(args.force))
    else:
        if bool(args.verify):
            verify_postgres_connection(database_url)
        restore_postgres(database_url, backup_path)

    print("ok")


if __name__ == "__main__":
    main()
