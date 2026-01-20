import pytest

from app.models.user import User
from app.routers import websocket as ws_router
from app.services.websocket_service import ConnectionManager


class _DummyWebSocket:
    def __init__(self, headers: dict[str, str] | None = None) -> None:
        self.headers = headers or {}


class _SessionCtx:
    def __init__(self, session) -> None:
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


def test_get_token_from_websocket_prefers_authorization_header() -> None:
    ws = _DummyWebSocket({"authorization": "Bearer abc"})
    assert ws_router._get_token_from_websocket(ws, "q") == "abc"

    ws2 = _DummyWebSocket({})
    assert ws_router._get_token_from_websocket(ws2, "q") == "q"


@pytest.mark.asyncio
async def test_get_active_user_id_happy_path_and_inactive_user(test_session, monkeypatch):
    user = User(username="ws1", email="ws1@example.com", nickname="ws1", hashed_password="x")
    test_session.add(user)
    await test_session.commit()
    await test_session.refresh(user)

    monkeypatch.setattr(ws_router, "AsyncSessionLocal", lambda: _SessionCtx(test_session), raising=True)
    monkeypatch.setattr(ws_router, "decode_token", lambda _t: {"sub": str(user.id)}, raising=True)

    assert await ws_router._get_active_user_id("t") == user.id

    user2 = User(username="ws2", email="ws2@example.com", nickname="ws2", hashed_password="x", is_active=False)
    test_session.add(user2)
    await test_session.commit()
    await test_session.refresh(user2)

    monkeypatch.setattr(ws_router, "decode_token", lambda _t: {"sub": user2.id}, raising=True)
    assert await ws_router._get_active_user_id("t") is None


@pytest.mark.asyncio
async def test_get_active_user_id_invalid_payloads_return_none(test_session, monkeypatch):
    monkeypatch.setattr(ws_router, "AsyncSessionLocal", lambda: _SessionCtx(test_session), raising=True)

    assert await ws_router._get_active_user_id(None) is None

    monkeypatch.setattr(ws_router, "decode_token", lambda _t: None, raising=True)
    assert await ws_router._get_active_user_id("t") is None

    monkeypatch.setattr(ws_router, "decode_token", lambda _t: {"sub": "abc"}, raising=True)
    assert await ws_router._get_active_user_id("t") is None

    monkeypatch.setattr(ws_router, "decode_token", lambda _t: {"sub": "999"}, raising=True)
    assert await ws_router._get_active_user_id("t") is None


@pytest.mark.asyncio
async def test_ws_status_endpoint_returns_counts(client, monkeypatch):
    mgr = ConnectionManager()
    monkeypatch.setattr(ws_router, "manager", mgr, raising=True)

    resp = await client.get("/ws/status")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total_connections"] == 0
    assert data["online_users"] == []
    assert data["anonymous_count"] == 0
