from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.settings import get_runtime_sync_settings
from app.services.sync_job_manager import SyncJobManager

logger = logging.getLogger(__name__)


async def _queue_sync_job(manager: SyncJobManager, *, source: str) -> bool:
    try:
        await manager.start_job(action="sync", source=source)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_409_CONFLICT:
            return False
        logger.warning("Unable to queue %s sync job: %s", source, exc.detail)
        return False
    except Exception:  # pragma: no cover - defensive logging path
        logger.exception("Unable to queue %s sync job", source)
        return False
    return True


async def maybe_enqueue_sync_on_write(request: Request, db: AsyncSession) -> bool:
    try:
        manager = getattr(request.app.state, "sync_job_manager", None)
        if not isinstance(manager, SyncJobManager):
            return False

        runtime = await get_runtime_sync_settings(db, use_cache=False)
        if runtime.sync_backend == "none" or not runtime.sync_on_save:
            return False

        return await _queue_sync_job(manager, source="automatic")
    except Exception:  # pragma: no cover - defensive logging path
        logger.exception("Unable to queue sync-on-save job")
        return False


async def enqueue_startup_sync_if_enabled(
    session_factory: async_sessionmaker[AsyncSession],
    manager: SyncJobManager,
    *,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> bool:
    try:
        async with session_factory() as db:
            runtime = await get_runtime_sync_settings(db, use_cache=False)
            if runtime.sync_backend == "none" or not runtime.sync_run_on_startup:
                return False
            delay_seconds = max(runtime.sync_startup_delay_seconds, 0)

        if delay_seconds > 0:
            await sleep(delay_seconds)

        return await _queue_sync_job(manager, source="automatic")
    except asyncio.CancelledError:
        raise
    except Exception:  # pragma: no cover - defensive logging path
        logger.exception("Unable to queue startup sync job")
        return False
