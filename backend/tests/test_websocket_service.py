import pytest

from app.services.websocket_service import ConnectionManager, create_message, MessageType


class _DummyWebSocket:
    def __init__(self, *, fail_send_text: bool = False) -> None:
        self.accepted = False
        self.sent_text: list[str] = []
        self.fail_send_text = bool(fail_send_text)

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        if self.fail_send_text:
            raise RuntimeError("send_text_failed")
        self.sent_text.append(data)


@pytest.mark.asyncio
async def test_connection_manager_connect_disconnect_user_and_anonymous() -> None:
    mgr = ConnectionManager()

    ws1 = _DummyWebSocket()
    await mgr.connect(ws1, user_id=1)
    assert ws1.accepted is True
    assert mgr.get_online_users() == [1]
    assert mgr.get_user_connection_count(1) == 1

    ws2 = _DummyWebSocket()
    await mgr.connect(ws2, user_id=None)
    assert ws2.accepted is True
    assert mgr.get_total_connections() == 2

    mgr.disconnect(ws1, user_id=1)
    assert mgr.get_total_connections() == 1
    assert mgr.get_online_users() == []

    mgr.disconnect(ws2, user_id=None)
    assert mgr.get_total_connections() == 0


@pytest.mark.asyncio
async def test_send_personal_message_handles_missing_and_send_errors() -> None:
    mgr = ConnectionManager()

    assert await mgr.send_personal_message(1, {"x": 1}) is False

    ok_ws = _DummyWebSocket()
    bad_ws = _DummyWebSocket(fail_send_text=True)

    await mgr.connect(ok_ws, user_id=1)
    await mgr.connect(bad_ws, user_id=1)

    sent = await mgr.send_personal_message(1, {"type": "t", "title": "a", "content": "b"})
    assert sent is True
    assert len(ok_ws.sent_text) == 1


@pytest.mark.asyncio
async def test_broadcast_counts_successes_and_swallows_anonymous_errors() -> None:
    mgr = ConnectionManager()

    ok1 = _DummyWebSocket()
    ok2 = _DummyWebSocket()
    bad1 = _DummyWebSocket(fail_send_text=True)
    bad_anon = _DummyWebSocket(fail_send_text=True)

    await mgr.connect(ok1, user_id=1)
    await mgr.connect(bad1, user_id=2)
    await mgr.connect(ok2, user_id=None)
    await mgr.connect(bad_anon, user_id=None)

    n = await mgr.broadcast({"type": "t", "title": "a", "content": "b"})
    assert n == 2


def test_create_message_shape() -> None:
    msg = create_message(MessageType.SYSTEM, "t", "c", {"x": 1})
    assert msg["type"] == MessageType.SYSTEM
    assert msg["title"] == "t"
    assert msg["content"] == "c"
    assert msg["data"] == {"x": 1}
    assert isinstance(msg["timestamp"], str)
