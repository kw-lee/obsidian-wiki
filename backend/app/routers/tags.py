from pathlib import PurePosixPath

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db.models import Document, Link, Tag
from app.db.session import get_db
from app.schemas import GraphData, GraphEdge, GraphNode, TagInfo
from app.services.wiki_links import ParsedWikiLink, load_resolver_catalog, resolve_wikilink

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


def _graph_title_for_path(path: str) -> str:
    pure_path = PurePosixPath(path)
    return pure_path.stem or pure_path.name or path


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
    nodes_by_id = {
        row[0]: GraphNode(
            id=row[0],
            title=row[1],
            tags=_normalize_tags(row[2]),
            kind="note",
        )
        for row in docs.all()
    }

    links = await db.execute(select(Link.source_path, Link.target_path))
    catalog = await load_resolver_catalog(db)
    edge_pairs: set[tuple[str, str]] = set()

    for source_path, raw_target in links.all():
        if source_path not in nodes_by_id:
            continue

        resolved = resolve_wikilink(
            ParsedWikiLink(
                raw_target=raw_target,
                display_text=raw_target,
                embed=False,
            ),
            source_path,
            catalog,
        )

        if resolved.kind in {"attachment", "ambiguous"} or not resolved.vault_path:
            continue

        target_path = resolved.vault_path
        if resolved.kind == "unresolved":
            nodes_by_id.setdefault(
                target_path,
                GraphNode(
                    id=target_path,
                    title=_graph_title_for_path(target_path),
                    tags=[],
                    kind="unresolved",
                ),
            )
        elif target_path not in nodes_by_id:
            continue

        edge_pairs.add((source_path, target_path))

    nodes = list(nodes_by_id.values())
    edges = [GraphEdge(source=source, target=target) for source, target in sorted(edge_pairs)]

    return GraphData(nodes=nodes, edges=edges)
