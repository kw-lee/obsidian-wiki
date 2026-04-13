from __future__ import annotations

import mimetypes
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePosixPath

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Attachment, Document
from app.schemas import ResolvedWikiLink
from app.services import vault

NOTE_EXTENSIONS = (".md", ".mdx")
WIKILINK_RE = re.compile(r"(?P<embed>!)?\[\[(?P<body>[^\]]+)\]\]")


@dataclass(frozen=True)
class ParsedWikiLink:
    raw_target: str
    display_text: str
    embed: bool


@dataclass(frozen=True)
class _ResolverCatalog:
    document_paths: set[str]
    documents_by_stem: dict[str, list[str]]
    documents_by_name: dict[str, list[str]]
    attachment_paths: set[str]
    attachments_by_name: dict[str, list[str]]


def parse_wikilinks(content: str) -> list[ParsedWikiLink]:
    links: list[ParsedWikiLink] = []
    for match in WIKILINK_RE.finditer(content):
        body = match.group("body").strip()
        if not body:
            continue
        target, _, alias = body.partition("|")
        target = target.strip()
        if not target:
            continue
        display = alias.strip() if alias.strip() else target
        links.append(
            ParsedWikiLink(
                raw_target=target,
                display_text=display,
                embed=bool(match.group("embed")),
            )
        )
    return links


async def resolve_links_for_document(
    session: AsyncSession,
    source_path: str,
    content: str,
) -> list[ResolvedWikiLink]:
    catalog = await load_resolver_catalog(session)
    return [resolve_wikilink(link, source_path, catalog) for link in parse_wikilinks(content)]


async def load_resolver_catalog(session: AsyncSession) -> _ResolverCatalog:
    document_rows = await session.execute(select(Document.path))
    attachment_rows = await session.execute(select(Attachment.path))

    document_paths = {row[0] for row in document_rows.all()}
    attachment_paths = {row[0] for row in attachment_rows.all()}

    documents_by_stem: dict[str, list[str]] = defaultdict(list)
    documents_by_name: dict[str, list[str]] = defaultdict(list)
    for path in sorted(document_paths):
        pure_path = PurePosixPath(path)
        documents_by_stem[pure_path.stem.lower()].append(path)
        documents_by_name[pure_path.name.lower()].append(path)

    attachments_by_name: dict[str, list[str]] = defaultdict(list)
    for path in sorted(attachment_paths):
        attachments_by_name[PurePosixPath(path).name.lower()].append(path)

    return _ResolverCatalog(
        document_paths=document_paths,
        documents_by_stem=dict(documents_by_stem),
        documents_by_name=dict(documents_by_name),
        attachment_paths=attachment_paths,
        attachments_by_name=dict(attachments_by_name),
    )


def resolve_wikilink(
    parsed: ParsedWikiLink,
    source_path: str,
    catalog: _ResolverCatalog,
) -> ResolvedWikiLink:
    target_path, subpath, subpath_marker = _split_subpath(parsed.raw_target)
    explicit_suffix = PurePosixPath(target_path).suffix.lower() if target_path else ""
    is_note_target = not explicit_suffix or explicit_suffix in NOTE_EXTENSIONS

    if not target_path:
        return _build_resolved_link(
            parsed=parsed,
            kind="block" if subpath_marker == "^" else "heading",
            vault_path=source_path,
            subpath=subpath,
            exists=True,
        )

    if is_note_target:
        groups, predicted_path = _note_candidate_groups(target_path, source_path, catalog)
        return _finalize_candidates(
            parsed=parsed,
            groups=groups,
            predicted_path=predicted_path,
            subpath=subpath,
            subpath_marker=subpath_marker,
        )

    groups, predicted_path = _attachment_candidate_groups(target_path, source_path, catalog)
    return _finalize_candidates(
        parsed=parsed,
        groups=groups,
        predicted_path=predicted_path,
        subpath=subpath,
        subpath_marker=subpath_marker,
    )


def _finalize_candidates(
    *,
    parsed: ParsedWikiLink,
    groups: list[list[str]],
    predicted_path: str | None,
    subpath: str | None,
    subpath_marker: str | None,
) -> ResolvedWikiLink:
    selected = next((group for group in groups if group), [])
    if not selected:
        unresolved_kind = "attachment" if _is_attachment_target(parsed.raw_target) else "unresolved"
        return _build_resolved_link(
            parsed=parsed,
            kind=unresolved_kind if unresolved_kind == "attachment" else "unresolved",
            vault_path=predicted_path,
            subpath=subpath,
            exists=False,
        )

    if len(selected) > 1:
        return _build_resolved_link(
            parsed=parsed,
            kind="ambiguous",
            vault_path=None,
            subpath=subpath,
            exists=True,
            ambiguous_paths=selected,
        )

    resolved_path = selected[0]
    if _is_note_path(resolved_path):
        if subpath_marker == "^":
            kind = "block"
        elif subpath:
            kind = "heading"
        else:
            kind = "note"
    else:
        kind = "attachment"

    return _build_resolved_link(
        parsed=parsed,
        kind=kind,
        vault_path=resolved_path,
        subpath=subpath,
        exists=True,
    )


def _build_resolved_link(
    *,
    parsed: ParsedWikiLink,
    kind: str,
    vault_path: str | None,
    subpath: str | None,
    exists: bool,
    ambiguous_paths: list[str] | None = None,
) -> ResolvedWikiLink:
    mime_type = None
    if vault_path and not _is_note_path(vault_path):
        mime_type = mimetypes.guess_type(vault_path)[0] or "application/octet-stream"

    return ResolvedWikiLink(
        raw_target=parsed.raw_target,
        display_text=parsed.display_text,
        kind=kind,
        vault_path=vault_path,
        subpath=subpath,
        embed=parsed.embed,
        exists=exists,
        ambiguous_paths=ambiguous_paths or [],
        mime_type=mime_type,
    )


def _note_candidate_groups(
    target_path: str,
    source_path: str,
    catalog: _ResolverCatalog,
) -> tuple[list[list[str]], str | None]:
    explicit_suffix = PurePosixPath(target_path).suffix.lower()
    relative_base = _normalize_relative_path(target_path, source_path)
    root_base = _normalize_relative_path(target_path, None)
    predicted = None

    if explicit_suffix in NOTE_EXTENSIONS:
        predicted = relative_base or root_base
        groups = [
            _existing_document_candidates([relative_base], catalog.document_paths),
            _existing_document_candidates([root_base], catalog.document_paths),
            _existing_document_candidates(
                catalog.documents_by_name.get(PurePosixPath(target_path).name.lower(), []),
                catalog.document_paths,
            ),
        ]
        return groups, predicted

    relative_candidates = _with_note_extensions(relative_base)
    root_candidates = _with_note_extensions(root_base)
    predicted = next((candidate for candidate in relative_candidates if candidate), None)
    groups = [
        _existing_document_candidates(relative_candidates, catalog.document_paths),
        _existing_document_candidates(root_candidates, catalog.document_paths),
        _existing_document_candidates(
            catalog.documents_by_stem.get(PurePosixPath(target_path).name.lower(), []),
            catalog.document_paths,
        ),
    ]
    return groups, predicted


def _attachment_candidate_groups(
    target_path: str,
    source_path: str,
    catalog: _ResolverCatalog,
) -> tuple[list[list[str]], str | None]:
    relative_candidate = _normalize_relative_path(target_path, source_path)
    root_candidate = _normalize_relative_path(target_path, None)
    predicted = relative_candidate or root_candidate
    basename = PurePosixPath(target_path).name.lower()

    groups = [
        _existing_attachment_candidates([relative_candidate], catalog.attachment_paths),
        _existing_attachment_candidates([root_candidate], catalog.attachment_paths),
        _existing_attachment_candidates(catalog.attachments_by_name.get(basename, []), catalog.attachment_paths),
    ]
    if not any(groups):
        groups = [
            _existing_attachment_candidates([relative_candidate], set()),
            _existing_attachment_candidates([root_candidate], set()),
            _filesystem_attachment_matches(basename),
        ]
    return groups, predicted


def _existing_document_candidates(
    candidates: list[str | None],
    known_paths: set[str],
) -> list[str]:
    ordered = [candidate for candidate in candidates if candidate and candidate in known_paths]
    return _dedupe_paths(ordered)


def _existing_attachment_candidates(
    candidates: list[str | None] | list[str],
    known_paths: set[str],
) -> list[str]:
    ordered: list[str] = []
    for candidate in candidates:
        if not candidate:
            continue
        if candidate in known_paths or _file_exists(candidate):
            ordered.append(candidate)
    return _dedupe_paths(ordered)


def _filesystem_attachment_matches(basename: str) -> list[str]:
    root = vault.vault_path()
    matches: list[str] = []
    for path in root.rglob("*"):
        if (
            path.is_file()
            and path.name.lower() == basename
            and not path.name.startswith(".")
            and ".obsidian" not in path.parts
        ):
            matches.append(path.relative_to(root).as_posix())
    return _dedupe_paths(sorted(matches))


def _with_note_extensions(path: str | None) -> list[str | None]:
    if not path:
        return []
    return [f"{path}{extension}" for extension in NOTE_EXTENSIONS]


def _normalize_relative_path(target_path: str, source_path: str | None) -> str | None:
    clean_target = target_path.strip().lstrip("/")
    if not clean_target:
        return None

    base = PurePosixPath(source_path).parent if source_path else PurePosixPath()
    combined = base / PurePosixPath(clean_target)
    parts: list[str] = []
    for part in combined.parts:
        if part in ("", "."):
            continue
        if part == "..":
            if not parts:
                return None
            parts.pop()
            continue
        parts.append(part)
    return "/".join(parts) if parts else None


def _split_subpath(raw_target: str) -> tuple[str, str | None, str | None]:
    if raw_target.startswith("#"):
        return "", raw_target[1:].strip() or None, "#"
    if raw_target.startswith("^"):
        return "", raw_target[1:].strip() or None, "^"

    heading_index = raw_target.find("#")
    block_index = raw_target.find("^")
    indexes = [(index, marker) for index, marker in ((heading_index, "#"), (block_index, "^")) if index >= 0]
    if not indexes:
        return raw_target.strip(), None, None

    index, marker = min(indexes, key=lambda item: item[0])
    path = raw_target[:index].strip()
    subpath = raw_target[index + 1 :].strip() or None
    return path, subpath, marker


def _file_exists(relative_path: str) -> bool:
    try:
        full = vault.resolve(relative_path)
    except ValueError:
        return False
    return full.exists() and full.is_file()


def _is_note_path(path: str) -> bool:
    return PurePosixPath(path).suffix.lower() in NOTE_EXTENSIONS


def _is_attachment_target(raw_target: str) -> bool:
    target_path, _, _ = _split_subpath(raw_target)
    suffix = PurePosixPath(target_path).suffix.lower()
    return bool(suffix and suffix not in NOTE_EXTENSIONS)


def _dedupe_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for path in paths:
        if path not in seen:
            seen.add(path)
            ordered.append(path)
    return ordered
