from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import SyncStatus, SyncTestResult
from app.services.git_ops import (
    git_bootstrap_from_local,
    git_bootstrap_from_remote,
    git_pull,
    git_push,
    sync_status,
)
from app.services.indexer import full_reindex, incremental_reindex
from app.services.settings import SyncRuntimeSettings
from app.services.sync.base import ProgressCallback, SyncBackend, emit_progress


class GitSyncBackend(SyncBackend):
    def __init__(self, runtime: SyncRuntimeSettings) -> None:
        self.runtime = runtime

    async def pull(
        self,
        db: AsyncSession,
        *,
        progress: ProgressCallback | None = None,
    ) -> tuple[str | None, list[str]]:
        await emit_progress(
            progress, phase="pulling", message="Fetching from Git remote", current=1, total=3
        )
        new_sha, changed = git_pull(
            git_remote_url=self.runtime.git_remote_url,
            git_branch=self.runtime.git_branch,
        )
        if changed:
            await emit_progress(
                progress, phase="indexing", message="Refreshing index", current=2, total=3
            )
            await incremental_reindex(db, changed)
        await emit_progress(
            progress, phase="complete", message="Git pull finished", current=3, total=3
        )
        return new_sha, changed

    async def push(
        self,
        db: AsyncSession,
        *,
        progress: ProgressCallback | None = None,
    ) -> None:
        del db
        await emit_progress(
            progress, phase="pushing", message="Pushing to Git remote", current=1, total=2
        )
        git_push(
            git_remote_url=self.runtime.git_remote_url,
            git_branch=self.runtime.git_branch,
        )
        await emit_progress(
            progress, phase="complete", message="Git push finished", current=2, total=2
        )

    async def bootstrap(
        self,
        db: AsyncSession,
        *,
        strategy: str,
        progress: ProgressCallback | None = None,
    ) -> tuple[str | None, list[str]]:
        if not self.runtime.git_remote_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Git remote URL is required",
            )
        if strategy not in {"remote", "local"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bootstrap strategy is required",
            )

        try:
            if strategy == "remote":
                await emit_progress(
                    progress,
                    phase="bootstrap_remote",
                    message="Applying Git remote baseline",
                    current=1,
                    total=3,
                )
                head, changed = git_bootstrap_from_remote(
                    git_remote_url=self.runtime.git_remote_url,
                    git_branch=self.runtime.git_branch,
                )
            else:
                await emit_progress(
                    progress,
                    phase="bootstrap_local",
                    message="Applying Git local baseline",
                    current=1,
                    total=3,
                )
                head, changed = git_bootstrap_from_local(
                    git_remote_url=self.runtime.git_remote_url,
                    git_branch=self.runtime.git_branch,
                )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(exc),
            ) from exc

        await emit_progress(
            progress, phase="indexing", message="Refreshing full index", current=2, total=3
        )
        await full_reindex(db)
        await emit_progress(
            progress,
            phase="complete",
            message=f"Git bootstrap finished ({strategy})",
            current=3,
            total=3,
        )
        return head, changed

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
