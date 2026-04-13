from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import SyncStatus
from app.services.settings import get_runtime_sync_settings
from app.services.sync.git_backend import GitSyncBackend
from app.services.sync.webdav_backend import WebDAVSyncBackend


def _sync_disabled_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Sync backend is disabled",
    )


def _get_backend(runtime):
    if runtime.sync_backend == "git":
        return GitSyncBackend(runtime)
    if runtime.sync_backend == "webdav":
        return WebDAVSyncBackend(runtime)
    return None


async def pull_active_backend(db: AsyncSession) -> tuple[str | None, list[str]]:
    runtime = await get_runtime_sync_settings(db)
    backend = _get_backend(runtime)
    if backend is None:
        raise _sync_disabled_error()
    return await backend.pull(db)


async def push_active_backend(db: AsyncSession) -> None:
    runtime = await get_runtime_sync_settings(db)
    backend = _get_backend(runtime)
    if backend is None:
        raise _sync_disabled_error()
    await backend.push(db)


async def get_active_sync_status(db: AsyncSession) -> SyncStatus:
    runtime = await get_runtime_sync_settings(db)
    backend = _get_backend(runtime)
    if backend is None:
        return SyncStatus(backend="none", message="Sync is disabled")
    return await backend.status(db)


async def run_scheduled_sync(db: AsyncSession) -> SyncStatus:
    runtime = await get_runtime_sync_settings(db, use_cache=False)
    backend = _get_backend(runtime)
    if backend is None:
        return SyncStatus(backend="none", message="Sync is disabled")
    if not runtime.sync_auto_enabled:
        return SyncStatus(backend=runtime.sync_backend, message="Automatic sync is disabled")

    status_before = await backend.status(db)
    if status_before.behind > 0:
        await backend.pull(db)

    status_after_pull = await backend.status(db)
    if status_after_pull.ahead > 0:
        await backend.push(db)

    return await backend.status(db)


async def test_sync_backend(db: AsyncSession, runtime_override=None):
    runtime = runtime_override or await get_runtime_sync_settings(db)
    backend = _get_backend(runtime)
    if backend is None:
        raise _sync_disabled_error()
    return await backend.test()
