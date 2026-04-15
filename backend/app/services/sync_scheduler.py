from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from contextlib import suppress

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.settings import get_runtime_sync_settings
from app.services.sync_service import run_scheduled_sync

logger = logging.getLogger(__name__)


class SyncScheduler:
    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        runner: Callable[[AsyncSession], Awaitable[object]] = run_scheduled_sync,
    ) -> None:
        self._session_factory = session_factory
        self._runner = runner
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(self._run_loop(), name="sync-scheduler")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def reload(self) -> None:
        await self.stop()
        await self.start()

    async def _run_loop(self) -> None:
        while True:
            try:
                async with self._session_factory() as db:
                    runtime = await get_runtime_sync_settings(db, use_cache=False)
                    interval = max(runtime.sync_interval_seconds, 60)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Scheduled sync iteration failed")
                interval = 60

            await asyncio.sleep(interval)

            try:
                async with self._session_factory() as db:
                    await self._runner(db)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Scheduled sync iteration failed")
