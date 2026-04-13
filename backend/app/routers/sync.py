from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db.session import get_db
from app.schemas import SyncJobResponse, SyncJobStartRequest, SyncStatus
from app.services.sync_job_manager import SyncJobManager
from app.services.sync_service import (
    get_active_sync_status,
    pull_active_backend,
    push_active_backend,
)

router = APIRouter()


def _get_job_manager(request: Request) -> SyncJobManager:
    manager = getattr(request.app.state, "sync_job_manager", None)
    if not isinstance(manager, SyncJobManager):
        raise RuntimeError("Sync job manager is not configured")
    return manager


async def _with_last_sync_from_jobs(request: Request, status_data: SyncStatus) -> SyncStatus:
    if status_data.last_sync is not None:
        return status_data

    manager = _get_job_manager(request)
    last_sync = await manager.get_last_successful_finished_at(backend=status_data.backend)
    if last_sync is None:
        return status_data
    return status_data.model_copy(update={"last_sync": last_sync})


@router.post("/pull")
async def pull(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> dict:
    new_sha, changed = await pull_active_backend(db)
    return {"head": new_sha, "changed_files": len(changed)}


@router.post("/push")
async def push(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> dict:
    await push_active_backend(db)
    return {"status": "ok"}


@router.get("/status", response_model=SyncStatus)
async def get_sync_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> SyncStatus:
    status_data = await get_active_sync_status(db)
    return await _with_last_sync_from_jobs(request, status_data)


@router.post("/job", response_model=SyncJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_sync_job(
    body: SyncJobStartRequest,
    request: Request,
    _user: str = Depends(get_current_user),
) -> SyncJobResponse:
    manager = _get_job_manager(request)
    return await manager.start_job(
        action=body.action,
        source="manual",
        bootstrap_strategy=body.bootstrap_strategy,
    )


@router.get("/job", response_model=SyncJobResponse | None)
async def get_current_sync_job(
    request: Request,
    _user: str = Depends(get_current_user),
) -> SyncJobResponse | None:
    manager = _get_job_manager(request)
    return await manager.get_current_job()
