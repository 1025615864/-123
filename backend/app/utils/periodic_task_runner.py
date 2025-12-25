import asyncio
import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from typing import Protocol


class LockClient(Protocol):
    async def acquire_lock(self, key: str, value: str, expire: int) -> bool: ...

    async def refresh_lock(self, key: str, value: str, expire: int) -> bool: ...

    async def release_lock(self, key: str, value: str) -> bool: ...


class PeriodicLockedRunner:
    def __init__(self, *, stop_event: asyncio.Event, lock_client: LockClient, logger: logging.Logger):
        self._stop_event = stop_event
        self._lock_client = lock_client
        self._logger = logger

    async def run(
        self,
        *,
        lock_key: str,
        lock_ttl_seconds: int,
        interval_seconds: float,
        job: Callable[[], Awaitable[object]],
        lock_value: str | None = None,
        refresh_interval_seconds: float | None = None,
        cancel_job_on_lock_lost: bool = True,
        job_cancel_grace_seconds: float = 2.0,
    ) -> None:
        lv = lock_value or f"{os.getpid()}-{uuid.uuid4().hex}"
        refresh_interval = (
            float(refresh_interval_seconds)
            if refresh_interval_seconds is not None
            else max(5.0, float(lock_ttl_seconds) / 3.0)
        )

        while not self._stop_event.is_set():
            try:
                acquired = await self._lock_client.acquire_lock(
                    lock_key,
                    value=lv,
                    expire=int(lock_ttl_seconds),
                )

                if acquired:
                    job_task: asyncio.Task[object] | None = None
                    refresh_task: asyncio.Task[None] | None = None
                    try:
                        async def _job_wrapper() -> object:
                            return await job()

                        job_task = asyncio.create_task(_job_wrapper())

                        async def _refresh_loop() -> None:
                            while (not self._stop_event.is_set()) and (job_task is not None) and (not job_task.done()):
                                try:
                                    await asyncio.wait_for(self._stop_event.wait(), timeout=refresh_interval)
                                    return
                                except asyncio.TimeoutError:
                                    try:
                                        ok = await self._lock_client.refresh_lock(
                                            lock_key,
                                            value=lv,
                                            expire=int(lock_ttl_seconds),
                                        )
                                        if not ok:
                                            if cancel_job_on_lock_lost and job_task is not None and not job_task.done():
                                                job_task.cancel()
                                            return
                                    except Exception:
                                        self._logger.exception("定时任务锁续租失败")
                                        if cancel_job_on_lock_lost and job_task is not None and not job_task.done():
                                            job_task.cancel()
                                        return

                        refresh_task = asyncio.create_task(_refresh_loop())
                        try:
                            _ = await job_task
                        except asyncio.CancelledError:
                            if self._stop_event.is_set():
                                raise
                    finally:
                        if refresh_task is not None:
                            refresh_task.cancel()
                            try:
                                await refresh_task
                            except asyncio.CancelledError:
                                if self._stop_event.is_set():
                                    raise
                            except Exception:
                                pass

                        if job_task is not None and (not job_task.done()):
                            job_task.cancel()
                            try:
                                await asyncio.wait_for(job_task, timeout=float(job_cancel_grace_seconds))
                            except asyncio.CancelledError:
                                if self._stop_event.is_set():
                                    raise
                            except Exception:
                                pass

                        _ = await self._lock_client.release_lock(lock_key, value=lv)
            except asyncio.CancelledError:
                raise
            except Exception:
                self._logger.exception("处理定时任务失败")

            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=float(interval_seconds))
            except asyncio.TimeoutError:
                pass
