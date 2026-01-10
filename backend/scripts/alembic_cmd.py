from __future__ import annotations

import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    backend_dir = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_dir))

    from alembic.config import CommandLine

    ini_path = backend_dir / "alembic.ini"

    cmd = CommandLine(prog="alembic")
    old_cwd = os.getcwd()
    try:
        os.chdir(str(backend_dir))
        cmd.main(["-c", str(ini_path), *args])
    finally:
        os.chdir(old_cwd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
