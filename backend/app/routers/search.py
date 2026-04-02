from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db.session import get_db
from app.schemas import SearchResponse, SearchResult

router = APIRouter()


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, max_length=200),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> SearchResponse:
    """Hybrid search: tsvector FTS + pg_trgm similarity."""
    sql = text("""
        SELECT
            path,
            title,
            ts_headline('korean', coalesce(title, '') || ' ', websearch_to_tsquery('korean', :q),
                'MaxWords=30, MinWords=10, StartSel=**, StopSel=**') AS snippet,
            (
                similarity(title, :q) * 3 +
                ts_rank(search_vector, websearch_to_tsquery('korean', :q)) * 2 +
                similarity(path, :q) * 1
            ) AS score
        FROM documents
        WHERE
            search_vector @@ websearch_to_tsquery('korean', :q)
            OR similarity(title, :q) > 0.1
            OR similarity(path, :q) > 0.1
        ORDER BY score DESC
        LIMIT :limit
    """)
    result = await db.execute(sql, {"q": q, "limit": limit})
    rows = result.all()
    results = [SearchResult(path=r[0], title=r[1], snippet=r[2], score=float(r[3])) for r in rows]
    return SearchResponse(query=q, results=results, total=len(results))
