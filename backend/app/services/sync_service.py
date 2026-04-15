from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import SyncStatus
from app.services.settings import get_runtime_sync_settings
from app.services.sync.base import ProgressCallback, emit_progress
from app.services.sync.git_backend import GitSyncBackend
from app.services.sync.webdav_backend import WebDAVSyncBackend


def _sync_disabled_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Sync backend is disabled",
    )


def build_sync_backend(runtime):
    if runtime.sync_backend == "git":
        return GitSyncBackend(runtime)
    if runtime.sync_backend == "webdav":
        return WebDAVSyncBackend(runtime)
    return None


def _mode_allows_pull(mode: str) -> bool:
    return mode in {"bidirectional", "pull-only"}


def _mode_allows_push(mode: str) -> bool:
    return mode in {"bidirectional", "push-only"}


async def run_backend_sync_cycle(
    db: AsyncSession,
    *,
    runtime,
    backend,
    progress: ProgressCallback | None = None,
) -> tuple[SyncStatus, int]:
    await emit_progress(progress, phase="checking", message="Checking sync status")

    mode = getattr(runtime, "sync_mode", "bidirectional")
    status_before = await backend.status(db)
    changed_files = 0
    pulled = False

    if status_before.behind > 0 and _mode_allows_pull(mode):
        _head, changed = await backend.pull(db, progress=progress)
        changed_files = len(changed)
        pulled = True

    status_after_pull = await backend.status(db) if pulled else status_before
    if status_after_pull.ahead > 0 and _mode_allows_push(mode):
        await backend.push(db, progress=progress)

    status = await backend.status(db)
    return status.model_copy(update={"timezone": runtime.timezone}), changed_files


async def pull_active_backend(db: AsyncSession) -> tuple[str | None, list[str]]:
    runtime = await get_runtime_sync_settings(db)
    backend = build_sync_backend(runtime)
    if backend is None:
        raise _sync_disabled_error()
    return await backend.pull(db)


async def push_active_backend(db: AsyncSession) -> None:
    runtime = await get_runtime_sync_settings(db)
    backend = build_sync_backend(runtime)
    if backend is None:
        raise _sync_disabled_error()
    await backend.push(db)


async def get_active_sync_status(db: AsyncSession) -> SyncStatus:
    runtime = await get_runtime_sync_settings(db)
    backend = build_sync_backend(runtime)
    if backend is None:
        return SyncStatus(backend="none", message="Sync is disabled", timezone=runtime.timezone)
    status = await backend.status(db)
    return status.model_copy(update={"timezone": runtime.timezone})


async def run_scheduled_sync(db: AsyncSession) -> SyncStatus:
    runtime = await get_runtime_sync_settings(db, use_cache=False)
    backend = build_sync_backend(runtime)
    if backend is None:
        return SyncStatus(backend="none", message="Sync is disabled", timezone=runtime.timezone)
    if not runtime.sync_auto_enabled:
        return SyncStatus(
            backend=runtime.sync_backend,
            message="Automatic sync is disabled",
            timezone=runtime.timezone,
        )

    status, _changed_files = await run_backend_sync_cycle(
        db,
        runtime=runtime,
        backend=backend,
    )
    return status


async def test_sync_backend(db: AsyncSession, runtime_override=None):
    runtime = runtime_override or await get_runtime_sync_settings(db)
    backend = build_sync_backend(runtime)
    if backend is None:
        raise _sync_disabled_error()
    return await backend.test()
