from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    backend_dir = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_dir))

    from alembic.config import CommandLine

    ini_path = backend_dir / "alembic.ini"

    cmd = CommandLine(prog="alembic")
    cmd.main(["-c", str(ini_path), *args])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
