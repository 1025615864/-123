import asyncio

import pytest

from app.utils.periodic_task_runner import PeriodicLockedRunner


class _DummyLockClient:
    def __init__(self) -> None:
        self.acquire_calls: list[tuple[str, str, int]] = []
        self.refresh_calls: list[tuple[str, str, int]] = []
        self.release_calls: list[tuple[str, str]] = []

        self.acquire_result = True
        self.refresh_results: list[bool] = []

    async def acquire_lock(self, key: str, value: str, expire: int) -> bool:
        self.acquire_calls.append((key, value, int(expire)))
        return bool(self.acquire_result)

    async def refresh_lock(self, key: str, value: str, expire: int) -> bool:
        self.refresh_calls.append((key, value, int(expire)))
        if self.refresh_results:
            return bool(self.refresh_results.pop(0))
        return True

    async def release_lock(self, key: str, value: str) -> bool:
        self.release_calls.append((key, value))
        return True


@pytest.mark.asyncio
async def test_periodic_locked_runner_runs_job_and_releases_lock() -> None:
    stop_event = asyncio.Event()
    lock_client = _DummyLockClient()
    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=lock_client, logger=__import__("logging").getLogger(__name__))

    ran: list[str] = []

    async def job() -> object:
        ran.append("ok")
        stop_event.set()
        return {"done": True}

    await runner.run(
        lock_key="k",
        lock_ttl_seconds=1,
        interval_seconds=0.01,
        refresh_interval_seconds=0.01,
        job=job,
        lock_value="lv",
    )

    assert ran == ["ok"]
    assert lock_client.acquire_calls
    assert lock_client.release_calls


@pytest.mark.asyncio
async def test_periodic_locked_runner_cancels_job_on_lock_lost() -> None:
    stop_event = asyncio.Event()

    class _LockClient(_DummyLockClient):
        async def release_lock(self, key: str, value: str) -> bool:
            ok = await super().release_lock(key, value)
            stop_event.set()
            return ok

    lock_client = _LockClient()
    lock_client.refresh_results = [False]

    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=lock_client, logger=__import__("logging").getLogger(__name__))

    cancelled = asyncio.Event()

    async def job() -> object:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return {"done": False}

    await runner.run(
        lock_key="k",
        lock_ttl_seconds=1,
        interval_seconds=0.01,
        refresh_interval_seconds=0.01,
        job=job,
        lock_value="lv",
        cancel_job_on_lock_lost=True,
    )

    assert cancelled.is_set()
    assert lock_client.refresh_calls
    assert lock_client.release_calls


@pytest.mark.asyncio
async def test_periodic_locked_runner_does_not_cancel_job_when_config_disabled() -> None:
    stop_event = asyncio.Event()

    class _LockClient(_DummyLockClient):
        async def release_lock(self, key: str, value: str) -> bool:
            ok = await super().release_lock(key, value)
            stop_event.set()
            return ok

    lock_client = _LockClient()
    lock_client.refresh_results = [False]

    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=lock_client, logger=__import__("logging").getLogger(__name__))

    cancelled = asyncio.Event()

    async def job() -> object:
        try:
            await asyncio.sleep(0.02)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return {"done": True}

    await runner.run(
        lock_key="k",
        lock_ttl_seconds=1,
        interval_seconds=0.01,
        refresh_interval_seconds=0.01,
        job=job,
        lock_value="lv",
        cancel_job_on_lock_lost=False,
    )

    assert cancelled.is_set() is False
    assert lock_client.refresh_calls
    assert lock_client.release_calls


@pytest.mark.asyncio
async def test_periodic_locked_runner_refresh_exception_cancels_job() -> None:
    stop_event = asyncio.Event()

    class _LockClient(_DummyLockClient):
        async def refresh_lock(self, key: str, value: str, expire: int) -> bool:
            _ = (key, value, expire)
            raise RuntimeError("boom")

        async def release_lock(self, key: str, value: str) -> bool:
            ok = await super().release_lock(key, value)
            stop_event.set()
            return ok

    lock_client = _LockClient()

    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=lock_client, logger=__import__("logging").getLogger(__name__))

    cancelled = asyncio.Event()

    async def job() -> object:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.set()
            raise
        return {"done": False}

    await runner.run(
        lock_key="k",
        lock_ttl_seconds=1,
        interval_seconds=0.01,
        refresh_interval_seconds=0.01,
        job=job,
        lock_value="lv",
        cancel_job_on_lock_lost=True,
    )

    assert cancelled.is_set()
    assert lock_client.release_calls


@pytest.mark.asyncio
async def test_periodic_locked_runner_refresh_loop_returns_on_stop_event() -> None:
    stop_event = asyncio.Event()
    lock_client = _DummyLockClient()
    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=lock_client, logger=__import__("logging").getLogger(__name__))

    started = asyncio.Event()

    async def job() -> object:
        started.set()
        await asyncio.sleep(0.05)
        return {"done": True}

    async def stopper() -> None:
        await started.wait()
        stop_event.set()

    asyncio.create_task(stopper())

    await runner.run(
        lock_key="k",
        lock_ttl_seconds=1,
        interval_seconds=0.01,
        refresh_interval_seconds=0.5,
        job=job,
        lock_value="lv",
    )

    assert lock_client.acquire_calls
    assert lock_client.release_calls


@pytest.mark.asyncio
async def test_periodic_locked_runner_acquire_lock_exception_is_swallowed() -> None:
    stop_event = asyncio.Event()

    class _LockClient(_DummyLockClient):
        async def acquire_lock(self, key: str, value: str, expire: int) -> bool:
            _ = (key, value, expire)
            stop_event.set()
            raise RuntimeError("boom")

    lock_client = _LockClient()
    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=lock_client, logger=__import__("logging").getLogger(__name__))

    async def job() -> object:
        return {"done": True}

    await runner.run(
        lock_key="k",
        lock_ttl_seconds=1,
        interval_seconds=0.01,
        refresh_interval_seconds=0.01,
        job=job,
        lock_value="lv",
    )


@pytest.mark.asyncio
async def test_periodic_locked_runner_interval_timeout_branch() -> None:
    stop_event = asyncio.Event()
    lock_client = _DummyLockClient()
    lock_client.acquire_result = False

    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=lock_client, logger=__import__("logging").getLogger(__name__))

    async def job() -> object:
        return {"done": True}

    async def stopper() -> None:
        await asyncio.sleep(0.03)
        stop_event.set()

    asyncio.create_task(stopper())

    await runner.run(
        lock_key="k",
        lock_ttl_seconds=1,
        interval_seconds=0.01,
        refresh_interval_seconds=0.01,
        job=job,
        lock_value="lv",
    )

    assert lock_client.acquire_calls


@pytest.mark.asyncio
async def test_periodic_locked_runner_cancelled_error_is_reraised_when_stopping() -> None:
    stop_event = asyncio.Event()
    lock_client = _DummyLockClient()
    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=lock_client, logger=__import__("logging").getLogger(__name__))

    started = asyncio.Event()

    async def job() -> object:
        started.set()
        await asyncio.sleep(10)
        return {"done": True}

    task = asyncio.create_task(
        runner.run(
            lock_key="k",
            lock_ttl_seconds=1,
            interval_seconds=0.01,
            refresh_interval_seconds=0.5,
            job=job,
            lock_value="lv",
        )
    )

    await started.wait()
    stop_event.set()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_periodic_locked_runner_refresh_task_cancelled_reraises_when_stop_is_set() -> None:
    class _Stop:
        def __init__(self) -> None:
            self.flag = False
            self.wait_called = asyncio.Event()

        def is_set(self) -> bool:
            return bool(self.flag)

        async def wait(self) -> None:
            self.wait_called.set()
            await asyncio.sleep(10)

    stop_event = _Stop()
    lock_client = _DummyLockClient()
    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=lock_client, logger=__import__("logging").getLogger(__name__))

    async def job() -> object:
        await stop_event.wait_called.wait()
        stop_event.flag = True
        return {"done": True}

    with pytest.raises(asyncio.CancelledError):
        await runner.run(
            lock_key="k",
            lock_ttl_seconds=30,
            interval_seconds=0.01,
            refresh_interval_seconds=30.0,
            job=job,
            lock_value="lv",
        )


@pytest.mark.asyncio
async def test_periodic_locked_runner_cancel_suppressed_to_cleanup_job_task_cancel_path() -> None:
    stop_event = asyncio.Event()

    class _LockClient(_DummyLockClient):
        async def release_lock(self, key: str, value: str) -> bool:
            ok = await super().release_lock(key, value)
            stop_event.set()
            return ok

    lock_client = _LockClient()
    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=lock_client, logger=__import__("logging").getLogger(__name__))

    started = asyncio.Event()

    async def job() -> object:
        started.set()
        await asyncio.sleep(10)
        return {"done": True}

    task = asyncio.create_task(
        runner.run(
            lock_key="k",
            lock_ttl_seconds=30,
            interval_seconds=0.01,
            refresh_interval_seconds=30.0,
            job=job,
            lock_value="lv",
        )
    )

    await started.wait()
    task.cancel()
    await task


@pytest.mark.asyncio
async def test_periodic_locked_runner_job_task_cancelled_error_branch_is_swallowed(monkeypatch) -> None:
    import app.utils.periodic_task_runner as ptr

    stop_event = asyncio.Event()

    class _LockClient(_DummyLockClient):
        async def release_lock(self, key: str, value: str) -> bool:
            ok = await super().release_lock(key, value)
            stop_event.set()
            return ok

    lock_client = _LockClient()
    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=lock_client, logger=__import__("logging").getLogger(__name__))

    class _FakeTask:
        def __init__(self) -> None:
            self._cancelled = False

        def done(self) -> bool:
            return False

        def cancel(self) -> None:
            self._cancelled = True

        def __await__(self):
            async def _coro():
                if self._cancelled:
                    raise asyncio.CancelledError
                return {"ok": True}

            return _coro().__await__()

    real_create_task = ptr.asyncio.create_task
    calls = {"n": 0}

    def fake_create_task(coro):
        calls["n"] += 1
        if calls["n"] == 1:
            coro.close()
            return _FakeTask()
        return real_create_task(coro)

    monkeypatch.setattr(ptr.asyncio, "create_task", fake_create_task, raising=True)

    async def job() -> object:
        return {"done": True}

    await runner.run(
        lock_key="k",
        lock_ttl_seconds=1,
        interval_seconds=0.01,
        refresh_interval_seconds=0.01,
        job=job,
        lock_value="lv",
    )


@pytest.mark.asyncio
async def test_periodic_locked_runner_job_task_exception_branch_is_swallowed(monkeypatch) -> None:
    import app.utils.periodic_task_runner as ptr

    stop_event = asyncio.Event()

    class _LockClient(_DummyLockClient):
        async def release_lock(self, key: str, value: str) -> bool:
            ok = await super().release_lock(key, value)
            stop_event.set()
            return ok

    lock_client = _LockClient()
    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=lock_client, logger=__import__("logging").getLogger(__name__))

    class _FakeTask:
        def __init__(self) -> None:
            self._cancelled = False

        def done(self) -> bool:
            return False

        def cancel(self) -> None:
            self._cancelled = True

        def __await__(self):
            async def _coro():
                if self._cancelled:
                    raise RuntimeError("boom")
                return {"ok": True}

            return _coro().__await__()

    real_create_task = ptr.asyncio.create_task
    calls = {"n": 0}

    def fake_create_task(coro):
        calls["n"] += 1
        if calls["n"] == 1:
            coro.close()
            return _FakeTask()
        return real_create_task(coro)

    monkeypatch.setattr(ptr.asyncio, "create_task", fake_create_task, raising=True)

    async def job() -> object:
        return {"done": True}

    await runner.run(
        lock_key="k",
        lock_ttl_seconds=1,
        interval_seconds=0.01,
        refresh_interval_seconds=0.01,
        job=job,
        lock_value="lv",
    )


@pytest.mark.asyncio
async def test_periodic_locked_runner_refresh_task_exception_is_swallowed() -> None:
    class _Stop:
        def __init__(self) -> None:
            self.flag = False
            self.wait_called = asyncio.Event()

        def is_set(self) -> bool:
            return bool(self.flag)

        async def wait(self) -> None:
            if self.flag:
                return
            self.wait_called.set()
            raise RuntimeError("boom")

    stop_event = _Stop()
    lock_client = _DummyLockClient()
    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=lock_client, logger=__import__("logging").getLogger(__name__))

    async def job() -> object:
        await stop_event.wait_called.wait()
        stop_event.flag = True
        return {"done": True}

    await runner.run(
        lock_key="k",
        lock_ttl_seconds=30,
        interval_seconds=0.01,
        refresh_interval_seconds=0.01,
        job=job,
        lock_value="lv",
    )


@pytest.mark.asyncio
async def test_periodic_locked_runner_job_cancel_wait_timeout_is_swallowed() -> None:
    stop_event = asyncio.Event()

    class _LockClient(_DummyLockClient):
        async def release_lock(self, key: str, value: str) -> bool:
            ok = await super().release_lock(key, value)
            stop_event.set()
            return ok

    lock_client = _LockClient()
    runner = PeriodicLockedRunner(stop_event=stop_event, lock_client=lock_client, logger=__import__("logging").getLogger(__name__))

    started = asyncio.Event()

    async def job() -> object:
        started.set()
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            await asyncio.sleep(0.05)
            return {"done": True}
        return {"done": False}

    task = asyncio.create_task(
        runner.run(
            lock_key="k",
            lock_ttl_seconds=30,
            interval_seconds=0.01,
            refresh_interval_seconds=30.0,
            job=job,
            lock_value="lv",
            job_cancel_grace_seconds=0.001,
        )
    )

    await started.wait()
    task.cancel()
    await task
