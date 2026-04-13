from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import SyncStatus
from app.services.git_ops import git_pull, git_push, sync_status
from app.services.indexer import incremental_reindex
from app.services.settings import get_runtime_sync_settings


def _sync_disabled_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="Sync backend is disabled",
    )


def _webdav_not_implemented_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="WebDAV sync backend is not implemented yet",
    )


async def pull_active_backend(db: AsyncSession) -> tuple[str | None, list[str]]:
    runtime = await get_runtime_sync_settings(db)
    if runtime.sync_backend == "none":
        raise _sync_disabled_error()
    if runtime.sync_backend == "webdav":
        raise _webdav_not_implemented_error()

    new_sha, changed = git_pull(
        git_remote_url=runtime.git_remote_url,
        git_branch=runtime.git_branch,
    )
    if changed:
        await incremental_reindex(db, changed)
    return new_sha, changed


async def push_active_backend(db: AsyncSession) -> None:
    runtime = await get_runtime_sync_settings(db)
    if runtime.sync_backend == "none":
        raise _sync_disabled_error()
    if runtime.sync_backend == "webdav":
        raise _webdav_not_implemented_error()

    git_push(git_remote_url=runtime.git_remote_url, git_branch=runtime.git_branch)


async def get_active_sync_status(db: AsyncSession) -> SyncStatus:
    runtime = await get_runtime_sync_settings(db)
    if runtime.sync_backend == "none":
        return SyncStatus(backend="none", message="Sync is disabled")
    if runtime.sync_backend == "webdav":
        return SyncStatus(
            backend="webdav",
            message="WebDAV sync backend is not implemented yet",
        )

    data = sync_status(
        git_remote_url=runtime.git_remote_url,
        git_branch=runtime.git_branch,
    )
    if not runtime.sync_auto_enabled:
        data["message"] = "Automatic sync is disabled"
    return SyncStatus(**data)


async def run_scheduled_sync(db: AsyncSession) -> SyncStatus:
    runtime = await get_runtime_sync_settings(db, use_cache=False)
    if runtime.sync_backend != "git" or not runtime.sync_auto_enabled:
        if runtime.sync_backend == "none":
            return SyncStatus(backend="none", message="Sync is disabled")
        if runtime.sync_backend == "webdav":
            return SyncStatus(
                backend="webdav",
                message="WebDAV sync backend is not implemented yet",
            )
        return SyncStatus(backend="git", message="Automatic sync is disabled")

    await pull_active_backend(db)
    return await get_active_sync_status(db)
