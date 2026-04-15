from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.schemas import SyncJobResponse
from app.services.settings import get_runtime_sync_settings
from app.services.sync_service import build_sync_backend, run_backend_sync_cycle

logger = logging.getLogger(__name__)

SyncAction = Literal["pull", "push", "bootstrap", "sync"]
SyncSource = Literal["manual", "automatic"]
SyncJobStatus = Literal["queued", "running", "succeeded", "failed", "conflict"]

_FINAL_STATUSES: set[SyncJobStatus] = {"succeeded", "failed", "conflict"}


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _progress_percent(current: int, total: int) -> int | None:
    if total <= 0:
        return None
    return max(0, min(100, int((current / total) * 100)))


def _error_message(detail: object) -> str:
    if isinstance(detail, dict):
        message = detail.get("message")
        if isinstance(message, str) and message:
            return message
        diff = detail.get("diff")
        if isinstance(diff, str) and diff:
            return diff
    if isinstance(detail, str):
        return detail
    return "Sync job failed"


@dataclass
class SyncJobRecord:
    id: str
    action: SyncAction
    source: SyncSource
    backend: str | None
    status: SyncJobStatus
    phase: str | None = None
    message: str | None = None
    current: int = 0
    total: int = 0
    bootstrap_strategy: Literal["remote", "local"] | None = None
    head: str | None = None
    changed_files: int = 0
    started_at: datetime | None = None
    updated_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    task: asyncio.Task[None] | None = field(default=None, repr=False)


class SyncJobManager:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._lock = asyncio.Lock()
        self._jobs: dict[str, SyncJobRecord] = {}
        self._recent_job_ids: deque[str] = deque(maxlen=20)
        self._active_job_id: str | None = None

    async def start_job(
        self,
        *,
        action: SyncAction,
        source: SyncSource = "manual",
        bootstrap_strategy: Literal["remote", "local"] | None = None,
    ) -> SyncJobResponse:
        async with self._lock:
            active = self._get_active_record()
            if active is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "message": "Another sync job is already running",
                        "job": self._to_response(active).model_dump(mode="json"),
                    },
                )

            job = SyncJobRecord(
                id=uuid4().hex,
                action=action,
                source=source,
                backend=None,
                status="queued",
                message="Sync job queued",
                bootstrap_strategy=bootstrap_strategy,
                updated_at=_utcnow(),
            )
            self._jobs[job.id] = job
            self._recent_job_ids.appendleft(job.id)
            self._active_job_id = job.id
            job.task = asyncio.create_task(self._run_job(job.id), name=f"sync-job-{job.id}")
            return self._to_response(job)

    async def get_current_job(self) -> SyncJobResponse | None:
        async with self._lock:
            active = self._get_active_record()
            if active is not None:
                return self._to_response(active)
            if not self._recent_job_ids:
                return None
            return self._to_response(self._jobs[self._recent_job_ids[0]])

    async def get_job(self, job_id: str) -> SyncJobResponse | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return self._to_response(job)

    async def get_last_successful_finished_at(
        self,
        *,
        backend: str | None = None,
    ) -> datetime | None:
        async with self._lock:
            for job_id in self._recent_job_ids:
                job = self._jobs.get(job_id)
                if job is None:
                    continue
                if job.status != "succeeded" or job.finished_at is None:
                    continue
                if backend is not None and job.backend != backend:
                    continue
                return job.finished_at
            return None

    async def _run_job(self, job_id: str) -> None:
        try:
            async with self._session_factory() as db:
                runtime = await get_runtime_sync_settings(db, use_cache=False)
                backend = build_sync_backend(runtime)
                if backend is None:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Sync backend is disabled",
                    )

                await self._update_job(
                    job_id,
                    backend=runtime.sync_backend,
                    status="running",
                    phase="starting",
                    message="Preparing sync job",
                    started_at=_utcnow(),
                )

                reporter = self._build_reporter(job_id)
                if self._jobs[job_id].action == "pull":
                    head, changed = await backend.pull(db, progress=reporter)
                    await self._update_job(
                        job_id,
                        head=head,
                        changed_files=len(changed),
                        status="succeeded",
                        phase="complete",
                        message="Pull finished",
                        finished_at=_utcnow(),
                    )
                elif self._jobs[job_id].action == "push":
                    await backend.push(db, progress=reporter)
                    await self._update_job(
                        job_id,
                        status="succeeded",
                        phase="complete",
                        message="Push finished",
                        finished_at=_utcnow(),
                    )
                elif self._jobs[job_id].action == "bootstrap":
                    strategy = self._jobs[job_id].bootstrap_strategy
                    if strategy is None:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Bootstrap strategy is required",
                        )
                    head, changed = await backend.bootstrap(
                        db,
                        strategy=strategy,
                        progress=reporter,
                    )
                    await self._update_job(
                        job_id,
                        head=head,
                        changed_files=len(changed),
                        status="succeeded",
                        phase="complete",
                        message=f"Bootstrap finished ({strategy})",
                        finished_at=_utcnow(),
                    )
                elif self._jobs[job_id].action == "sync":
                    sync_status, changed_files = await run_backend_sync_cycle(
                        db,
                        runtime=runtime,
                        backend=backend,
                        progress=reporter,
                    )
                    await self._update_job(
                        job_id,
                        head=sync_status.head,
                        changed_files=changed_files,
                        status="succeeded",
                        phase="complete",
                        message="Sync finished",
                        finished_at=_utcnow(),
                    )
        except asyncio.CancelledError:
            raise
        except HTTPException as exc:
            final_status: SyncJobStatus = (
                "conflict" if exc.status_code == status.HTTP_409_CONFLICT else "failed"
            )
            await self._update_job(
                job_id,
                status=final_status,
                phase="error",
                message=_error_message(exc.detail),
                error=_error_message(exc.detail),
                finished_at=_utcnow(),
            )
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.exception("Background sync job failed")
            await self._update_job(
                job_id,
                status="failed",
                phase="error",
                message=str(exc),
                error=str(exc),
                finished_at=_utcnow(),
            )
        finally:
            async with self._lock:
                if self._active_job_id == job_id:
                    self._active_job_id = None

    def _build_reporter(self, job_id: str):
        async def report(
            *,
            phase: str,
            message: str | None = None,
            current: int | None = None,
            total: int | None = None,
        ) -> None:
            updates: dict[str, object] = {"phase": phase}
            if message is not None:
                updates["message"] = message
            if current is not None:
                updates["current"] = current
            if total is not None:
                updates["total"] = total
            await self._update_job(job_id, **updates)

        return report

    async def _update_job(self, job_id: str, **updates: object) -> None:
        async with self._lock:
            job = self._jobs[job_id]
            for key, value in updates.items():
                setattr(job, key, value)
            job.updated_at = _utcnow()

    def _get_active_record(self) -> SyncJobRecord | None:
        if self._active_job_id is None:
            return None
        job = self._jobs.get(self._active_job_id)
        if job is None or job.status in _FINAL_STATUSES:
            return None
        return job

    def _to_response(self, job: SyncJobRecord) -> SyncJobResponse:
        return SyncJobResponse(
            id=job.id,
            action=job.action,
            source=job.source,
            backend=job.backend,
            status=job.status,
            phase=job.phase,
            message=job.message,
            current=job.current,
            total=job.total,
            progress_percent=_progress_percent(job.current, job.total),
            bootstrap_strategy=job.bootstrap_strategy,
            head=job.head,
            changed_files=job.changed_files,
            started_at=job.started_at,
            updated_at=job.updated_at,
            finished_at=job.finished_at,
            error=job.error,
        )
