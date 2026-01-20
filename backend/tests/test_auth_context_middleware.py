from fastapi import FastAPI, Request
from httpx import AsyncClient, ASGITransport
import pytest

from app.middleware.auth_context_middleware import AuthContextMiddleware


@pytest.mark.asyncio
async def test_auth_context_middleware_sub_not_int_sets_none(monkeypatch):
    import app.middleware.auth_context_middleware as m

    def fake_decode_token(token: str):
        return {"sub": "abc"}

    monkeypatch.setattr(m, "decode_token", fake_decode_token, raising=True)

    app = FastAPI()
    app.add_middleware(AuthContextMiddleware)

    @app.get("/x")
    async def x(request: Request):
        return {"user_id": request.state.user_id}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/x", headers={"Authorization": "Bearer token"})
        assert res.status_code == 200
        assert res.json()["user_id"] is None


@pytest.mark.asyncio
async def test_auth_context_middleware_decode_token_raises_sets_none(monkeypatch):
    import app.middleware.auth_context_middleware as m

    def fake_decode_token(token: str):
        raise RuntimeError("boom")

    monkeypatch.setattr(m, "decode_token", fake_decode_token, raising=True)

    app = FastAPI()
    app.add_middleware(AuthContextMiddleware)

    @app.get("/x")
    async def x(request: Request):
        return {"user_id": request.state.user_id}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/x", headers={"Authorization": "Bearer token"})
        assert res.status_code == 200
        assert res.json()["user_id"] is None
