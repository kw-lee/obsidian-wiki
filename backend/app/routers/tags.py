from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db.models import Document, Link, Tag
from app.db.session import get_db
from app.schemas import GraphData, GraphEdge, GraphNode, TagInfo

router = APIRouter()


def _normalize_tags(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(tag) for tag in value]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("{") and text.endswith("}"):
            return [tag.strip().strip('"') for tag in text.strip("{}").split(",") if tag.strip()]
        return [tag.strip() for tag in text.split(",") if tag.strip()]
    return [str(value)]


@router.get("/tags", response_model=list[TagInfo])
async def list_tags(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> list[TagInfo]:
    result = await db.execute(select(Tag).order_by(Tag.doc_count.desc()))
    return [TagInfo(name=t.name, doc_count=t.doc_count) for t in result.scalars()]


@router.get("/graph", response_model=GraphData)
async def get_graph(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> GraphData:
    docs = await db.execute(select(Document.path, Document.title, Document.tags))
    nodes = [GraphNode(id=row[0], title=row[1], tags=_normalize_tags(row[2])) for row in docs.all()]

    links = await db.execute(select(Link.source_path, Link.target_path))
    edges = [GraphEdge(source=r[0], target=r[1]) for r in links.all()]

    return GraphData(nodes=nodes, edges=edges)
