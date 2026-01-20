import inspect
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from httpx import ASGITransport, AsyncClient
from starlette.responses import StreamingResponse
from starlette.requests import Request

from app.middleware.envelope_middleware import EnvelopeMiddleware


def _make_transport(app: FastAPI) -> ASGITransport:
    transport_kwargs: dict[str, Any] = {"app": app}
    if "lifespan" in inspect.signature(ASGITransport.__init__).parameters:
        transport_kwargs["lifespan"] = "off"
    return ASGITransport(**transport_kwargs)


def _make_request(*, envelope: str = "1") -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(b"x-api-envelope", envelope.encode("utf-8"))],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


@pytest.mark.asyncio
async def test_envelope_middleware_dispatch_jsonresponse_already_wrapped_returns_same_obj() -> None:
    middleware = EnvelopeMiddleware(FastAPI())
    request = _make_request(envelope="1")

    response = JSONResponse({"ok": True, "data": {"x": 1}})

    async def call_next(_req: Request):
        return response

    out = await middleware.dispatch(request, call_next)
    assert out is response


@pytest.mark.asyncio
async def test_envelope_middleware_dispatch_raw_bytes_wraps() -> None:
    middleware = EnvelopeMiddleware(FastAPI())
    request = _make_request(envelope="true")

    resp = Response(content=b"", media_type="application/json")
    setattr(resp, "body", b'{"x":1}')

    async def call_next(_req: Request):
        return resp

    out = await middleware.dispatch(request, call_next)
    assert out is not resp
    data = out.body
    assert b"\"ok\"" in data


@pytest.mark.asyncio
async def test_envelope_middleware_dispatch_raw_bytearray_wraps() -> None:
    middleware = EnvelopeMiddleware(FastAPI())
    request = _make_request(envelope="yes")

    resp = Response(content=b"", media_type="application/json")
    setattr(resp, "body", bytearray(b'{"x":1}'))

    async def call_next(_req: Request):
        return resp

    out = await middleware.dispatch(request, call_next)
    assert out is not resp
    assert b"\"ok\"" in out.body


@pytest.mark.asyncio
async def test_envelope_middleware_dispatch_raw_memoryview_wraps() -> None:
    middleware = EnvelopeMiddleware(FastAPI())
    request = _make_request(envelope="on")

    resp = Response(content=b"", media_type="application/json")
    setattr(resp, "body", memoryview(b'{"m":2}'))

    async def call_next(_req: Request):
        return resp

    out = await middleware.dispatch(request, call_next)
    assert out is not resp
    assert b"\"ok\"" in out.body


@pytest.mark.asyncio
async def test_envelope_middleware_dispatch_body_none_no_iterator_returns_same_obj() -> None:
    middleware = EnvelopeMiddleware(FastAPI())
    request = _make_request(envelope="1")

    resp = Response(content=b"", media_type="application/json")
    setattr(resp, "body", None)

    async def call_next(_req: Request):
        return resp

    out = await middleware.dispatch(request, call_next)
    assert out is resp


@pytest.mark.asyncio
async def test_envelope_middleware_dispatch_raw_other_type_no_iterator_returns_same_obj() -> None:
    middleware = EnvelopeMiddleware(FastAPI())
    request = _make_request(envelope="1")

    resp = Response(content=b"", media_type="application/json")
    resp.__dict__["body"] = object()

    async def call_next(_req: Request):
        return resp

    out = await middleware.dispatch(request, call_next)
    assert out is resp


@pytest.mark.asyncio
async def test_envelope_middleware_dispatch_iterator_none_and_bytes_conversion_paths() -> None:
    middleware = EnvelopeMiddleware(FastAPI())
    request = _make_request(envelope="1")

    class _Good:
        def __bytes__(self) -> bytes:
            return b""

    class _Bad:
        def __bytes__(self) -> bytes:
            raise TypeError("no")

    async def gen():
        yield None
        yield memoryview(b'{"a":1}')
        yield _Good()
        yield _Bad()

    resp = Response(content=b"", media_type="application/json")
    setattr(resp, "body", None)
    setattr(resp, "body_iterator", gen())

    async def call_next(_req: Request):
        return resp

    out = await middleware.dispatch(request, call_next)
    assert b"\"ok\"" in out.body


@pytest.mark.asyncio
async def test_envelope_middleware_wraps_json_when_header_present() -> None:
    app = FastAPI()
    app.add_middleware(EnvelopeMiddleware)

    @app.get("/json")
    async def json_endpoint():
        return {"hello": "world"}

    transport = _make_transport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/json", headers={"X-Api-Envelope": "1"})
        assert res.status_code == 200
        payload = res.json()
        assert payload["ok"] is True
        assert payload["data"] == {"hello": "world"}
        assert int(payload["ts"]) > 0


@pytest.mark.asyncio
async def test_envelope_middleware_does_not_wrap_without_header() -> None:
    app = FastAPI()
    app.add_middleware(EnvelopeMiddleware)

    @app.get("/json")
    async def json_endpoint():
        return {"hello": "world"}

    transport = _make_transport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/json")
        assert res.status_code == 200
        assert res.json() == {"hello": "world"}


@pytest.mark.asyncio
async def test_envelope_middleware_skips_when_already_wrapped() -> None:
    app = FastAPI()
    app.add_middleware(EnvelopeMiddleware)

    @app.get("/wrapped")
    async def wrapped():
        return {"ok": True, "data": {"x": 1}}

    transport = _make_transport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/wrapped", headers={"X-Api-Envelope": "true"})
        assert res.status_code == 200
        assert res.json() == {"ok": True, "data": {"x": 1}}


@pytest.mark.asyncio
async def test_envelope_middleware_skips_non_json() -> None:
    app = FastAPI()
    app.add_middleware(EnvelopeMiddleware)

    @app.get("/text")
    async def text():
        return PlainTextResponse("hi")

    transport = _make_transport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/text", headers={"X-Api-Envelope": "1"})
        assert res.status_code == 200
        assert res.text == "hi"


@pytest.mark.asyncio
async def test_envelope_middleware_skips_204() -> None:
    app = FastAPI()
    app.add_middleware(EnvelopeMiddleware)

    @app.get("/empty")
    async def empty():
        return Response(status_code=204)

    transport = _make_transport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/empty", headers={"X-Api-Envelope": "1"})
        assert res.status_code == 204


@pytest.mark.asyncio
async def test_envelope_middleware_does_not_wrap_non_2xx() -> None:
    app = FastAPI()
    app.add_middleware(EnvelopeMiddleware)

    @app.get("/bad")
    async def bad():
        raise HTTPException(status_code=400, detail="bad")

    transport = _make_transport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/bad", headers={"X-Api-Envelope": "1"})
        assert res.status_code == 400
        assert "detail" in res.json()


@pytest.mark.asyncio
async def test_envelope_middleware_reconstructs_streaming_json() -> None:
    app = FastAPI()
    app.add_middleware(EnvelopeMiddleware)

    @app.get("/stream")
    async def stream():
        async def gen():
            yield b'{"a":1}'

        return StreamingResponse(gen(), media_type="application/json")

    transport = _make_transport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/stream", headers={"X-Api-Envelope": "1"})
        assert res.status_code == 200
        payload = res.json()
        assert payload["ok"] is True
        assert payload["data"] == {"a": 1}
        assert int(payload["ts"]) > 0


@pytest.mark.asyncio
async def test_envelope_middleware_memoryview_body_is_wrapped() -> None:
    app = FastAPI()
    app.add_middleware(EnvelopeMiddleware)

    @app.get("/mv")
    async def mv():
        resp = Response(content=b"", media_type="application/json")
        setattr(resp, "body", memoryview(b'{"m":2}'))
        return resp

    transport = _make_transport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/mv", headers={"X-Api-Envelope": "1"})
        assert res.status_code == 200
        payload = res.json()
        assert payload["ok"] is True
        assert payload["data"] == {"m": 2}


@pytest.mark.asyncio
async def test_envelope_middleware_reconstructed_empty_body_returns_unmodified() -> None:
    app = FastAPI()
    app.add_middleware(EnvelopeMiddleware)

    @app.get("/empty-stream")
    async def empty_stream():
        async def gen():
            if False:
                yield b""

        resp = Response(content=b"", media_type="application/json")
        setattr(resp, "body", None)
        setattr(resp, "body_iterator", gen())
        return resp

    transport = _make_transport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/empty-stream", headers={"X-Api-Envelope": "1"})
        assert res.status_code == 200
        assert res.content == b""


@pytest.mark.asyncio
async def test_envelope_middleware_reconstructed_invalid_json_returns_unmodified() -> None:
    app = FastAPI()
    app.add_middleware(EnvelopeMiddleware)

    @app.get("/bad-json")
    async def bad_json():
        async def gen():
            yield b"{bad"

        return StreamingResponse(gen(), media_type="application/json")

    transport = _make_transport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/bad-json", headers={"X-Api-Envelope": "1"})
        assert res.status_code == 200
        assert res.content == b"{bad"


@pytest.mark.asyncio
async def test_envelope_middleware_reconstructed_unbytesable_chunk_is_ignored() -> None:
    app = FastAPI()
    app.add_middleware(EnvelopeMiddleware)

    @app.get("/unbytes")
    async def unbytesable():
        async def gen():
            yield "x"

        resp = Response(content=b"", media_type="application/json")
        setattr(resp, "body", None)
        setattr(resp, "body_iterator", gen())
        return resp

    transport = _make_transport(app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/unbytes", headers={"X-Api-Envelope": "1"})
        assert res.status_code == 200
        assert res.content == b""
