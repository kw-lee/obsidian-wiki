from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db.session import get_db
from app.schemas import SyncStatus
from app.services.git_ops import git_pull, git_push, sync_status
from app.services.indexer import incremental_reindex

router = APIRouter()


@router.post("/pull")
async def pull(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> dict:
    new_sha, changed = git_pull()
    if changed:
        await incremental_reindex(db, changed)
    return {"head": new_sha, "changed_files": len(changed)}


@router.post("/push")
async def push(_user: str = Depends(get_current_user)) -> dict:
    git_push()
    return {"status": "ok"}


@router.get("/status", response_model=SyncStatus)
async def get_sync_status(_user: str = Depends(get_current_user)) -> SyncStatus:
    data = sync_status()
    return SyncStatus(**data)
