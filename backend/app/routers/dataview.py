from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db.session import get_db
from app.schemas import DataviewQueryRequest, DataviewQueryResponse
from app.services.dataview import run_dataview_query

router = APIRouter()


@router.post("/dataview/query", response_model=DataviewQueryResponse)
async def query_dataview(
    body: DataviewQueryRequest,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> DataviewQueryResponse:
    try:
        return await run_dataview_query(db, body.query)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
