import json
import posixpath
import re
from collections import defaultdict
from pathlib import PurePosixPath

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
    git_add_all_and_commit,
    git_add_and_commit,
    git_stage_move_and_commit,
    head_commit_sha,
    read_file_at_commit,
)
from app.services.indexer import full_reindex, index_file
from app.services.settings import ensure_app_settings
from app.services.templater import TemplaterRenderContext, render_template_markdown
from app.services.wiki_links import (
    ParsedWikiLink,
    load_resolver_catalog,
    parse_wikilinks,
    resolve_links_for_document,
    resolve_wikilink,
)

router = APIRouter()


def _invalid_path(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def _resolve_or_400(path: str, *, for_write: bool = False):
    try:
        return vault.resolve(path, for_write=for_write)
    except ValueError as exc:
        raise _invalid_path(str(exc)) from exc


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


def _extract_backlink_snippet(
    source_content: str, source_path: str, target_path: str, catalog
) -> str | None:
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


def _translate_moved_path(path: str, source_root: str, destination_root: str) -> str:
    if path == source_root:
        return destination_root
    source_prefix = f"{source_root}/"
    if path.startswith(source_prefix):
        return f"{destination_root}/{path.removeprefix(source_prefix)}"
    return path


def _reverse_translate_moved_path(path: str, source_root: str, destination_root: str) -> str:
    if path == destination_root:
        return source_root
    destination_prefix = f"{destination_root}/"
    if path.startswith(destination_prefix):
        return f"{source_root}/{path.removeprefix(destination_prefix)}"
    return path


def _split_subpath(raw_target: str) -> tuple[str, str | None, str | None]:
    if raw_target.startswith("#"):
        return "", raw_target[1:].strip() or None, "#"
    if raw_target.startswith("^"):
        return "", raw_target[1:].strip() or None, "^"

    heading_index = raw_target.find("#")
    block_index = raw_target.find("^")
    indexes = [
        (index, marker)
        for index, marker in ((heading_index, "#"), (block_index, "^"))
        if index >= 0
    ]
    if not indexes:
        return raw_target.strip(), None, None

    index, marker = min(indexes, key=lambda item: item[0])
    path = raw_target[:index].strip()
    subpath = raw_target[index + 1 :].strip() or None
    return path, subpath, marker


def _rewrite_wikilink_target(
    current_path: str,
    target_path: str,
    resolved_path: str,
    subpath: str | None,
    subpath_marker: str | None,
) -> str:
    relative_target = posixpath.relpath(
        resolved_path,
        start=PurePosixPath(current_path).parent.as_posix() or ".",
    )
    original_suffix = PurePosixPath(target_path).suffix.lower()
    if original_suffix not in (".md", ".mdx") and PurePosixPath(resolved_path).suffix.lower() in (
        ".md",
        ".mdx",
    ):
        note_suffix = PurePosixPath(relative_target).suffix
        if note_suffix.lower() in (".md", ".mdx"):
            relative_target = relative_target[: -len(note_suffix)]

    if subpath:
        relative_target = f"{relative_target}{subpath_marker or '#'}{subpath}"
    return relative_target


def _rewrite_wikilinks_for_move(
    content: str,
    *,
    current_path: str,
    previous_path: str,
    source_root: str,
    destination_root: str,
    catalog,
) -> tuple[str, int]:
    rewritten = 0
    parts: list[str] = []
    last_index = 0

    for match in re.finditer(r"(?P<embed>!)?\[\[(?P<body>[^\]]+)\]\]", content):
        parts.append(content[last_index : match.start()])
        body = match.group("body")
        target_part, separator, alias_part = body.partition("|")
        target_text = target_part.strip()
        if not target_text:
            parts.append(match.group(0))
            last_index = match.end()
            continue

        target_path, subpath, subpath_marker = _split_subpath(target_text)
        if not target_path:
            parts.append(match.group(0))
            last_index = match.end()
            continue

        parsed = ParsedWikiLink(
            raw_target=target_text,
            display_text=alias_part.strip() if alias_part.strip() else target_text,
            embed=bool(match.group("embed")),
        )
        resolved = resolve_wikilink(parsed, previous_path, catalog)
        if not resolved.exists or resolved.kind == "ambiguous" or not resolved.vault_path:
            parts.append(match.group(0))
            last_index = match.end()
            continue

        translated_path = _translate_moved_path(resolved.vault_path, source_root, destination_root)
        if current_path == previous_path and translated_path == resolved.vault_path:
            parts.append(match.group(0))
            last_index = match.end()
            continue

        rewritten_target = _rewrite_wikilink_target(
            current_path=current_path,
            target_path=target_path,
            resolved_path=translated_path,
            subpath=subpath,
            subpath_marker=subpath_marker,
        )
        if rewritten_target == target_text:
            parts.append(match.group(0))
            last_index = match.end()
            continue

        leading_ws = target_part[: len(target_part) - len(target_part.lstrip())]
        trailing_ws = target_part[len(target_part.rstrip()) :]
        rewritten_target_part = f"{leading_ws}{rewritten_target}{trailing_ws}"
        rewritten_body = (
            f"{rewritten_target_part}{separator}{alias_part}"
            if separator
            else rewritten_target_part
        )
        parts.append(f"{'!' if match.group('embed') else ''}[[{rewritten_body}]]")
        rewritten += 1
        last_index = match.end()

    parts.append(content[last_index:])
    return "".join(parts), rewritten


async def _rewrite_links_after_move(
    source_root: str,
    destination_root: str,
    catalog,
) -> tuple[list[str], int]:
    rewritten_paths: list[str] = []
    rewritten_links = 0
    vault_root = vault.vault_path()

    for md_file in vault_root.rglob("*.md"):
        if md_file.name.startswith(".") or ".obsidian" in md_file.parts:
            continue
        current_path = md_file.relative_to(vault_root).as_posix()
        previous_path = _reverse_translate_moved_path(current_path, source_root, destination_root)
        content = await vault.read_doc(current_path)
        rewritten_content, count = _rewrite_wikilinks_for_move(
            content,
            current_path=current_path,
            previous_path=previous_path,
            source_root=source_root,
            destination_root=destination_root,
            catalog=catalog,
        )
        if count:
            await vault.write_doc(current_path, rewritten_content)
            rewritten_paths.append(current_path)
            rewritten_links += count

    return rewritten_paths, rewritten_links


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
    except ValueError as exc:
        raise _invalid_path(str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
        ) from exc
    row = await db.execute(select(Document).where(Document.path == path))
    doc = row.scalar_one_or_none()
    outgoing_links = await resolve_links_for_document(db, path, content)
    runtime_settings = await ensure_app_settings(db)
    title = doc.title if doc else path.rsplit("/", 1)[-1].removesuffix(".md")
    tags = _normalize_tags(doc.tags) if doc else []
    frontmatter = _normalize_frontmatter(doc.frontmatter) if doc else {}
    rendered_content = None
    if runtime_settings.templater_enabled:
        rendered_content = await render_template_markdown(
            db,
            content,
            TemplaterRenderContext(
                note_path=path,
                resolve_path=path,
                title=title,
                content=content,
                frontmatter=frontmatter,
                tags=tags,
                created_at=doc.created_at if doc else None,
                updated_at=doc.updated_at if doc else None,
                timezone=runtime_settings.timezone,
            ),
        )
    return DocDetail(
        path=path,
        title=title,
        tags=tags,
        frontmatter=frontmatter,
        created_at=doc.created_at if doc else None,
        updated_at=doc.updated_at if doc else None,
        content=content,
        rendered_content=rendered_content,
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
    _resolve_or_400(path, for_write=True)
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
        try:
            current_content = await vault.read_doc(path)
        except ValueError as exc:
            raise _invalid_path(str(exc)) from exc
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
    full = _resolve_or_400(path, for_write=True)
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Folder path is required"
        )

    full = _resolve_or_400(path, for_write=True)
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
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Source and destination are required"
        )
    if source_path == destination_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Source and destination must differ"
        )
    if any(part.startswith(".") for part in source_path.split("/")) or any(
        part.startswith(".") for part in destination_path.split("/")
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Hidden paths cannot be moved"
        )
    if destination_path.startswith(f"{source_path}/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot move a folder into itself"
        )

    source_full = _resolve_or_400(source_path)
    destination_full = _resolve_or_400(destination_path, for_write=True)
    if not source_full.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Source path does not exist"
        )
    if destination_full.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Destination already exists"
        )

    catalog = await load_resolver_catalog(db)
    moved_path = await vault.move_path(source_path, destination_path)
    rewritten_paths: list[str] = []
    rewritten_links = 0
    if body.rewrite_links:
        rewritten_paths, rewritten_links = await _rewrite_links_after_move(
            source_path, moved_path, catalog
        )
        git_add_all_and_commit(f"web: move {source_path} -> {moved_path}")
    else:
        git_stage_move_and_commit(
            source_path, moved_path, f"web: move {source_path} -> {moved_path}"
        )
    await full_reindex(db)
    return MovePathResponse(
        path=moved_path,
        rewrite_links=body.rewrite_links,
        rewritten_paths=rewritten_paths,
        rewritten_links=rewritten_links,
    )


@router.delete("/doc/{path:path}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_doc(
    path: str,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> None:
    _resolve_or_400(path, for_write=True)
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
        select(Link.source_path, Link.target_path, Link.alias, Document.title).join(
            Document, Document.path == Link.source_path
        )
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
