import json
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete as sql_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.db.models import Document, Link
from app.db.session import get_db
from app.schemas import (
    BacklinkItem,
    DocCreateRequest,
    DocDetail,
    DocSaveRequest,
    FolderCreateRequest,
    FolderCreateResponse,
    MovePathRequest,
    MovePathResponse,
    TreeNode,
)
from app.services import vault
from app.services.conflict import three_way_merge
from app.services.git_ops import (
    file_changed_between,
    git_add_and_commit,
    git_stage_move_and_commit,
    head_commit_sha,
    read_file_at_commit,
)
from app.services.indexer import full_reindex, index_file
from app.services.wiki_links import (
    ParsedWikiLink,
    load_resolver_catalog,
    parse_wikilinks,
    resolve_links_for_document,
    resolve_wikilink,
)

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


def _normalize_frontmatter(value: object) -> dict:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            decoded = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _normalize_snippet(text: str, max_length: int = 160) -> str:
    compact = " ".join(text.split())
    if len(compact) <= max_length:
        return compact
    return f"{compact[: max_length - 1].rstrip()}…"


def _extract_backlink_snippet(source_content: str, source_path: str, target_path: str, catalog) -> str | None:
    for raw_line in source_content.splitlines():
        line = raw_line.strip()
        if not line or "[[" not in line:
            continue
        for parsed in parse_wikilinks(line):
            resolved = resolve_wikilink(parsed, source_path, catalog)
            if resolved.vault_path == target_path:
                return _normalize_snippet(line)
    for raw_line in source_content.splitlines():
        line = raw_line.strip()
        if line:
            return _normalize_snippet(line)
    return None


@router.get("/tree", response_model=list[TreeNode])
async def get_tree(_user: str = Depends(get_current_user)) -> list[TreeNode]:
    nodes = vault.build_tree()
    return [TreeNode(**n) for n in nodes]


@router.get("/doc/{path:path}", response_model=DocDetail)
async def get_doc(
    path: str,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> DocDetail:
    try:
        content = await vault.read_doc(path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found") from exc
    row = await db.execute(select(Document).where(Document.path == path))
    doc = row.scalar_one_or_none()
    outgoing_links = await resolve_links_for_document(db, path, content)
    return DocDetail(
        path=path,
        title=doc.title if doc else path.rsplit("/", 1)[-1].removesuffix(".md"),
        tags=_normalize_tags(doc.tags) if doc else [],
        frontmatter=_normalize_frontmatter(doc.frontmatter) if doc else {},
        created_at=doc.created_at if doc else None,
        updated_at=doc.updated_at if doc else None,
        content=content,
        base_commit=head_commit_sha(),
        outgoing_links=outgoing_links,
    )


@router.put("/doc/{path:path}", response_model=DocDetail)
async def save_doc(
    path: str,
    body: DocSaveRequest,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> DocDetail:
    current_head = head_commit_sha()

    # Conflict check
    if (
        body.base_commit
        and current_head
        and body.base_commit != current_head
        and file_changed_between(path, body.base_commit, current_head)
    ):
        # Attempt 3-way merge
        try:
            base_content = read_file_at_commit(path, body.base_commit)
        except Exception:
            base_content = ""
        current_content = await vault.read_doc(path)
        merged, diff = three_way_merge(base_content, body.content, current_content)
        if merged is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"message": "Merge conflict", "diff": diff},
            )
        body.content = merged

    await vault.write_doc(path, body.content)
    git_add_and_commit([path], f"web: update {path}")

    await index_file(db, path, body.content)
    await db.commit()

    return await get_doc(path, db)


@router.post("/doc", response_model=DocDetail, status_code=status.HTTP_201_CREATED)
async def create_doc(
    body: DocCreateRequest,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> DocDetail:
    path = body.path
    if not path.endswith(".md"):
        path += ".md"
    full = vault.resolve(path)
    if full.exists():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Document already exists")

    await vault.write_doc(path, body.content)
    git_add_and_commit([path], f"web: create {path}")

    await index_file(db, path, body.content)
    await db.commit()

    return await get_doc(path, db)


@router.post("/folder", response_model=FolderCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_folder(
    body: FolderCreateRequest,
    _user: str = Depends(get_current_user),
) -> FolderCreateResponse:
    path = body.path.strip().strip("/")
    if not path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Folder path is required")

    full = vault.resolve(path)
    if full.exists():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Folder already exists")

    placeholder_path = await vault.create_folder(path)
    git_add_and_commit([placeholder_path], f"web: create folder {path}")
    return FolderCreateResponse(path=path)


@router.post("/move", response_model=MovePathResponse)
async def move_path(
    body: MovePathRequest,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> MovePathResponse:
    source_path = body.source_path.strip().strip("/")
    destination_path = body.destination_path.strip().strip("/")

    if not source_path or not destination_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source and destination are required")
    if source_path == destination_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source and destination must differ")
    if any(part.startswith(".") for part in source_path.split("/")) or any(
        part.startswith(".") for part in destination_path.split("/")
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Hidden paths cannot be moved")
    if destination_path.startswith(f"{source_path}/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot move a folder into itself")

    source_full = vault.resolve(source_path)
    destination_full = vault.resolve(destination_path)
    if not source_full.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source path does not exist")
    if destination_full.exists():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Destination already exists")

    moved_path = await vault.move_path(source_path, destination_path)
    git_stage_move_and_commit(source_path, moved_path, f"web: move {source_path} -> {moved_path}")
    await full_reindex(db)
    return MovePathResponse(path=moved_path)


@router.delete("/doc/{path:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_doc(
    path: str,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> None:
    await vault.delete_doc(path)
    git_add_and_commit([path], f"web: delete {path}")

    await db.execute(sql_delete(Link).where(Link.source_path == path))
    await db.execute(sql_delete(Document).where(Document.path == path))
    await db.commit()


@router.get("/backlinks/{path:path}", response_model=list[BacklinkItem])
async def get_backlinks(
    path: str,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> list[BacklinkItem]:
    catalog = await load_resolver_catalog(db)
    result = await db.execute(
        select(Link.source_path, Link.target_path, Link.alias, Document.title)
        .join(Document, Document.path == Link.source_path)
    )

    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {"title": "", "mention_count": 0, "snippet": None}
    )

    for source_path, raw_target, alias, title in result.all():
        resolved = resolve_wikilink(
            ParsedWikiLink(
                raw_target=raw_target,
                display_text=alias or raw_target,
                embed=False,
            ),
            source_path,
            catalog,
        )
        if resolved.vault_path != path:
            continue

        item = grouped[source_path]
        item["title"] = title
        item["mention_count"] = int(item["mention_count"]) + 1
        if item["snippet"] is None:
            try:
                content = await vault.read_doc(source_path)
            except FileNotFoundError:
                content = ""
            item["snippet"] = _extract_backlink_snippet(content, source_path, path, catalog)

    items = [
        BacklinkItem(
            source_path=source_path,
            title=str(payload["title"]),
            snippet=payload["snippet"] if isinstance(payload["snippet"], str) else None,
            mention_count=int(payload["mention_count"]),
        )
        for source_path, payload in grouped.items()
    ]
    return sorted(items, key=lambda item: (item.title.lower(), item.source_path.lower()))
