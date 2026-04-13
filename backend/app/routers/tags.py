import hashlib
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


def _graph_pseudo_id(kind: str, source_path: str, raw_target: str, *parts: str) -> str:
    digest_input = "\0".join((kind, source_path, raw_target, *parts))
    digest = hashlib.sha256(digest_input.encode("utf-8")).hexdigest()[:16]
    return f"graph:{kind}:{digest}"


def _graph_node_for_resolved_link(
    resolved_kind: str,
    source_path: str,
    raw_target: str,
    display_text: str,
    vault_path: str | None,
    ambiguous_paths: list[str] | None = None,
    mime_type: str | None = None,
) -> GraphNode:
    if resolved_kind == "attachment":
        node_id = vault_path or _graph_pseudo_id(
            "attachment",
            source_path,
            raw_target,
            display_text,
        )
        return GraphNode(
            id=node_id,
            title=_graph_title_for_path(vault_path or display_text or raw_target),
            tags=[],
            kind="attachment",
            mime_type=mime_type,
        )

    if resolved_kind == "ambiguous":
        node_id = _graph_pseudo_id(
            "ambiguous",
            source_path,
            raw_target,
            *(ambiguous_paths or []),
        )
        return GraphNode(
            id=node_id,
            title=display_text or raw_target,
            tags=[],
            kind="ambiguous",
            candidate_paths=ambiguous_paths or [],
        )

    raise ValueError(f"Unsupported graph node kind: {resolved_kind}")


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
        if resolved.kind == "unresolved":
            if not resolved.vault_path:
                continue
            nodes_by_id.setdefault(
                resolved.vault_path,
                GraphNode(
                    id=resolved.vault_path,
                    title=_graph_title_for_path(resolved.vault_path),
                    tags=[],
                    kind="unresolved",
                ),
            )
            edge_pairs.add((source_path, resolved.vault_path))
            continue

        if resolved.kind == "note":
            if not resolved.vault_path or resolved.vault_path not in nodes_by_id:
                continue
            edge_pairs.add((source_path, resolved.vault_path))
            continue

        if resolved.kind in {"attachment", "ambiguous"}:
            if resolved.kind == "attachment":
                target_node = _graph_node_for_resolved_link(
                    resolved_kind="attachment",
                    source_path=source_path,
                    raw_target=resolved.raw_target,
                    display_text=resolved.display_text,
                    vault_path=resolved.vault_path,
                    mime_type=resolved.mime_type,
                )
            else:
                target_node = _graph_node_for_resolved_link(
                    resolved_kind="ambiguous",
                    source_path=source_path,
                    raw_target=resolved.raw_target,
                    display_text=resolved.display_text,
                    vault_path=resolved.vault_path,
                    ambiguous_paths=resolved.ambiguous_paths,
                )

            nodes_by_id.setdefault(target_node.id, target_node)
            edge_pairs.add((source_path, target_node.id))

    nodes = list(nodes_by_id.values())
    edges = [GraphEdge(source=source, target=target) for source, target in sorted(edge_pairs)]

    return GraphData(nodes=nodes, edges=edges)
