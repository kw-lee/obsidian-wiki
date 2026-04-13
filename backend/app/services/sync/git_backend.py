from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import SyncStatus, SyncTestResult
from app.services.git_ops import git_pull, git_push, sync_status
from app.services.indexer import incremental_reindex
from app.services.settings import SyncRuntimeSettings
from app.services.sync.base import SyncBackend


class GitSyncBackend(SyncBackend):
    def __init__(self, runtime: SyncRuntimeSettings) -> None:
        self.runtime = runtime

    async def pull(self, db: AsyncSession) -> tuple[str | None, list[str]]:
        new_sha, changed = git_pull(
            git_remote_url=self.runtime.git_remote_url,
            git_branch=self.runtime.git_branch,
        )
        if changed:
            await incremental_reindex(db, changed)
        return new_sha, changed

    async def push(self, db: AsyncSession) -> None:
        del db
        git_push(
            git_remote_url=self.runtime.git_remote_url,
            git_branch=self.runtime.git_branch,
        )

    async def status(self, db: AsyncSession) -> SyncStatus:
        del db
        data = sync_status(
            git_remote_url=self.runtime.git_remote_url,
            git_branch=self.runtime.git_branch,
        )
        if not self.runtime.sync_auto_enabled:
            data["message"] = "Automatic sync is disabled"
        return SyncStatus(**data)

    async def test(self) -> SyncTestResult:
        if not self.runtime.git_remote_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Git remote URL is required",
            )
        return SyncTestResult(ok=True, backend="git", detail="Git configuration looks valid")
