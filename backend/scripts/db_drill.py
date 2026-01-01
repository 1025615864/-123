import argparse
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

_BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


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


def _resolve_sqlite_path(url_str: str) -> Path:
    url = make_url(url_str)
    db = url.database or ""
    if db in {":memory:", ""}:
        raise SystemExit("sqlite in-memory database cannot be drilled via file path")
    p = Path(db)
    if not p.is_absolute():
        p = (_backend_root() / p).resolve()
    return p


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--drill-database-url",
        default=None,
        help="for postgres: required; for sqlite: optional (if omitted, uses a temp sqlite file)",
    )
    parser.add_argument("--backup", default=None, help="optional: use an existing backup file")
    parser.add_argument("--verify", action="store_true", help="for postgres: verify source/drill db connectivity")
    parser.add_argument("--keep", action="store_true", help="keep drill restore db file")
    args = parser.parse_args()

    database_url = _effective_database_url(args.database_url)
    url = make_url(database_url)

    backend = _backend_root()
    backups_dir = backend / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    backend_name = str(url.get_backend_name())

    # 1) create backup
    if args.backup and str(args.backup).strip():
        backup_path = Path(str(args.backup)).expanduser()
        if not backup_path.is_absolute():
            backup_path = (backend / backup_path).resolve()
    else:
        from datetime import datetime

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if backend_name == "sqlite":
            backup_path = (backups_dir / f"drill_sqlite_{ts}.db").resolve()
            from scripts.db_backup import backup_sqlite

            backup_sqlite(database_url, backup_path)
        elif backend_name == "postgresql":
            backup_path = (backups_dir / f"drill_postgres_{ts}.dump").resolve()
            from scripts.db_backup import backup_postgres

            backup_postgres(database_url, backup_path)
        else:
            raise SystemExit(f"db_drill unsupported database backend: {backend_name}")

    # 2) restore into a separate drill db (do NOT overwrite the primary DB)
    if backend_name == "sqlite":
        from datetime import datetime

        ts2 = datetime.now().strftime("%Y%m%d_%H%M%S")
        drill_db_rel = f"./backups/drill_restore_{ts2}.db"
        drill_db_url = f"sqlite+aiosqlite:///{drill_db_rel}"

        if args.drill_database_url and str(args.drill_database_url).strip():
            drill_db_url = str(args.drill_database_url).strip()

        from scripts.db_restore import restore_sqlite

        restore_sqlite(drill_db_url, backup_path, force=True)

        drill_db_path = _resolve_sqlite_path(drill_db_url)
    else:
        if not (args.drill_database_url and str(args.drill_database_url).strip()):
            raise SystemExit("postgres drill requires --drill-database-url (must be a dedicated drill db)")

        drill_db_url = str(args.drill_database_url).strip()
        src = make_url(database_url)
        dst = make_url(drill_db_url)

        if str(dst.get_backend_name()) != "postgresql":
            raise SystemExit("--drill-database-url must be a postgres database url")

        def _id(u):
            return (u.host, u.port or 5432, u.database, u.username)

        if _id(src) == _id(dst):
            raise SystemExit("refusing to drill-restore into the same postgres database")

        if bool(args.verify):
            from scripts.db_backup import verify_postgres_connection

            verify_postgres_connection(database_url)
            verify_postgres_connection(drill_db_url)

        from scripts.db_restore import restore_postgres

        restore_postgres(drill_db_url, backup_path)
        drill_db_path = None

    # 3) run init_db against the drill db to validate schema/bootstrap
    env = os.environ.copy()
    env["DATABASE_URL"] = drill_db_url

    cmd = [
        sys.executable,
        "-c",
        "import asyncio; from app.database import init_db; asyncio.run(init_db())",
    ]

    proc = subprocess.run(
        cmd,
        cwd=str(backend),
        env=env,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()
        raise SystemExit(f"drill init_db failed: {err}")

    if backend_name == "sqlite":
        if drill_db_path is not None and drill_db_path.exists() and not args.keep:
            drill_db_path.unlink()

    print(str(backup_path))


if __name__ == "__main__":
    main()
