from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db.session import get_db
from app.schemas import SyncStatus
from app.services.sync_service import get_active_sync_status, pull_active_backend, push_active_backend

router = APIRouter()


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
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> SyncStatus:
    return await get_active_sync_status(db)
