import logging
from datetime import datetime, timezone

import pytest

import app.utils.logging_config as mod


class _FixedDateTime:
    @classmethod
    def now(cls):  # noqa: N805
        return datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def test_setup_logging_creates_handlers_and_files(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Save current root logger state to avoid leaking changes to other tests.
    root = logging.getLogger()
    old_level = root.level
    old_handlers = list(root.handlers)

    monkeypatch.setattr(mod, "datetime", _FixedDateTime)

    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    try:
        mod.setup_logging(log_level="DEBUG", log_dir=str(log_dir), app_name="app")

        assert root.level == logging.DEBUG
        assert len(root.handlers) == 3

        paths = []
        for h in root.handlers:
            if isinstance(h, logging.FileHandler):
                paths.append(h.baseFilename)

        assert any(p.endswith("app_2026-01-01.log") for p in paths)
        assert any(p.endswith("app_error_2026-01-01.log") for p in paths)

        assert (log_dir / "app_2026-01-01.log").exists()
        assert (log_dir / "app_error_2026-01-01.log").exists()

        assert logging.getLogger("uvicorn").level == logging.WARNING
        assert logging.getLogger("uvicorn.access").level == logging.WARNING
        assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("httpcore").level == logging.WARNING
    finally:
        root.handlers = old_handlers
        root.setLevel(old_level)


def test_request_logger_logs(caplog: pytest.LogCaptureFixture) -> None:
    rl = mod.RequestLogger("t")

    with caplog.at_level(logging.INFO, logger="t"):
        rl.log_request("GET", "/x", user_id=1, ip="1.2.3.4", extra={"k": "v"})
        assert "REQUEST GET /x" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.INFO, logger="t"):
        rl.log_response("GET", "/x", status_code=200, duration_ms=1.0, user_id=1)
        assert "RESPONSE GET /x" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="t"):
        rl.log_response("GET", "/x", status_code=400, duration_ms=1.0, user_id=1)
        assert "status=400" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.ERROR, logger="t"):
        rl.log_response("GET", "/x", status_code=500, duration_ms=1.0, user_id=1)
        assert "status=500" in caplog.text

    caplog.clear()
    with caplog.at_level(logging.ERROR, logger="t"):
        rl.log_error("GET", "/x", error="e", user_id=1, traceback="tb")
        assert "ERROR GET /x" in caplog.text
        assert "tb" in caplog.text
