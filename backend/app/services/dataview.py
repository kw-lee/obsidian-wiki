from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Document, Link
from app.schemas import (
    DataviewCell,
    DataviewContextResponse,
    DataviewLinkSnapshot,
    DataviewPageFileSnapshot,
    DataviewPageSnapshot,
    DataviewQueryResponse,
    DataviewRow,
    TaskItem,
)
from app.services.tasks import list_vault_tasks
from app.services.wiki_links import ParsedWikiLink, load_resolver_catalog, resolve_wikilink

_QUERY_RE = re.compile(
    r"^(?P<kind>LIST|TABLE)(?:\s+WITHOUT\s+ID)?(?:\s+(?P<fields>.+?))?\s+FROM\s+(?P<source>\"[^\"]+\"|#[\w/-]+)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedDataviewQuery:
    kind: str
    fields: list[str]
    source_kind: str
    source_value: str


def _normalize_query(query: str) -> str:
    lines = [line.strip() for line in query.splitlines() if line.strip()]
    return " ".join(lines)


def parse_dataview_query(query: str) -> ParsedDataviewQuery:
    normalized = _normalize_query(query)
    match = _QUERY_RE.match(normalized)
    if not match:
        raise ValueError('Only LIST/TABLE FROM "folder" or FROM #tag queries are supported')

    kind = match.group("kind").lower()
    fields_text = (match.group("fields") or "").strip()
    source = match.group("source")

    if kind == "table":
        if not fields_text:
            raise ValueError("TABLE queries require at least one field")
        fields = [field.strip() for field in fields_text.split(",") if field.strip()]
    else:
        fields = ["file.link"]

    if source.startswith("#"):
        return ParsedDataviewQuery(
            kind=kind,
            fields=fields,
            source_kind="tag",
            source_value=source[1:],
        )

    source_value = source.strip('"').strip()
    return ParsedDataviewQuery(
        kind=kind,
        fields=fields,
        source_kind="folder",
        source_value=source_value,
    )


def _normalize_tags(value) -> list[str]:
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


def _serialize_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _normalize_frontmatter(value) -> dict:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    try:
        return dict(value)
    except (TypeError, ValueError):
        return {}


def _frontmatter_lookup(frontmatter: dict, field: str):
    if field in frontmatter:
        return frontmatter[field]
    lower_map = {str(key).lower(): value for key, value in frontmatter.items()}
    return lower_map.get(field.lower())


def _build_cell(doc: Document, field: str) -> DataviewCell:
    normalized = field.strip()
    lowered = normalized.lower()
    frontmatter = _normalize_frontmatter(doc.frontmatter)
    tags = _normalize_tags(doc.tags)

    if lowered == "file.link":
        return DataviewCell(value=doc.title, link_path=doc.path)
    if lowered == "file.name":
        return DataviewCell(value=doc.title)
    if lowered == "file.path":
        return DataviewCell(value=doc.path)
    if lowered == "tags":
        return DataviewCell(value=_serialize_value(tags))

    return DataviewCell(value=_serialize_value(_frontmatter_lookup(frontmatter, normalized)))


def _link_display(path: str) -> str:
    return PurePosixPath(path).stem


def _link_snapshot(path: str) -> DataviewLinkSnapshot:
    return DataviewLinkSnapshot(path=path, display=_link_display(path))


async def run_dataview_query(db: AsyncSession, query: str) -> DataviewQueryResponse:
    parsed = parse_dataview_query(query)
    result = await db.execute(select(Document).order_by(Document.path))
    docs = list(result.scalars().all())

    if parsed.source_kind == "folder":
        folder = parsed.source_value.strip().strip("/")
        if folder and folder != ".":
            docs = [
                doc
                for doc in docs
                if doc.path == folder
                or doc.path.startswith(f"{folder}/")
                or doc.path.startswith(f"{folder}.")
            ]
    else:
        docs = [doc for doc in docs if parsed.source_value in _normalize_tags(doc.tags)]

    rows = [DataviewRow(cells=[_build_cell(doc, field) for field in parsed.fields]) for doc in docs]
    return DataviewQueryResponse(kind=parsed.kind, columns=parsed.fields, rows=rows)


async def build_dataview_context(db: AsyncSession) -> DataviewContextResponse:
    document_result = await db.execute(select(Document).order_by(Document.path))
    documents = list(document_result.scalars().all())

    link_result = await db.execute(select(Link.source_path, Link.target_path))
    catalog = await load_resolver_catalog(db)
    outlinks_by_source: dict[str, set[str]] = defaultdict(set)
    inlinks_by_target: dict[str, set[str]] = defaultdict(set)
    for source_path, target_path in link_result.all():
        resolved = resolve_wikilink(
            ParsedWikiLink(raw_target=target_path, display_text=target_path, embed=False),
            source_path,
            catalog,
        )
        normalized_target = resolved.vault_path or target_path
        outlinks_by_source[source_path].add(normalized_target)
        inlinks_by_target[normalized_target].add(source_path)

    tasks_by_path: dict[str, list[TaskItem]] = defaultdict(list)
    for task in list_vault_tasks(include_done=True):
        tasks_by_path[task.path].append(
            TaskItem(
                path=task.path,
                line_number=task.line_number,
                text=task.text,
                completed=task.completed,
                due_date=task.due_date,
                priority=task.priority,
            )
        )

    pages: list[DataviewPageSnapshot] = []
    for document in documents:
        pure_path = PurePosixPath(document.path)
        folder = "" if str(pure_path.parent) == "." else str(pure_path.parent)
        tags = _normalize_tags(document.tags)
        frontmatter = _normalize_frontmatter(document.frontmatter)
        file_snapshot = DataviewPageFileSnapshot(
            name=pure_path.stem,
            path=document.path,
            folder=folder,
            ext=pure_path.suffix,
            link=_link_snapshot(document.path),
            ctime=document.created_at,
            mtime=document.updated_at,
            tags=tags,
            inlinks=[
                _link_snapshot(path) for path in sorted(inlinks_by_target.get(document.path, set()))
            ],
            outlinks=[
                _link_snapshot(path)
                for path in sorted(outlinks_by_source.get(document.path, set()))
            ],
            tasks=tasks_by_path.get(document.path, []),
        )
        pages.append(
            DataviewPageSnapshot(
                path=document.path,
                title=document.title,
                tags=tags,
                frontmatter=frontmatter,
                file=file_snapshot,
            )
        )

    return DataviewContextResponse(pages=pages)
