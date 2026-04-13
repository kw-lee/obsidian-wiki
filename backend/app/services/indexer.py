"""Full and incremental indexing of vault markdown files into the database."""

import hashlib
import logging
import re
from pathlib import Path

import frontmatter
from sqlalchemy import delete, func, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import Document, Link, Tag

logger = logging.getLogger(__name__)

WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
TAG_RE = re.compile(r"(?:^|\s)#([a-zA-Z0-9가-힣_/-]+)", re.MULTILINE)


def _extract_links(content: str) -> list[tuple[str, str | None]]:
    """Extract (target, alias) tuples from wikilinks."""
    return [(m.group(1).strip(), m.group(2)) for m in WIKILINK_RE.finditer(content)]


def _extract_tags(content: str, fm_tags: list[str]) -> list[str]:
    """Extract tags from both frontmatter and inline #tags."""
    inline = {m.group(1) for m in TAG_RE.finditer(content)}
    return sorted(set(fm_tags) | inline)


async def index_file(session: AsyncSession, relative_path: str, content: str) -> None:
    """Index a single markdown file."""
    fm = frontmatter.loads(content)
    title = fm.metadata.get("title", Path(relative_path).stem)
    fm_tags = fm.metadata.get("tags", [])
    if isinstance(fm_tags, str):
        fm_tags = [t.strip() for t in fm_tags.split(",")]
    tags = _extract_tags(fm.content, fm_tags)
    chash = hashlib.sha256(content.encode()).hexdigest()

    # Upsert document
    stmt = insert(Document).values(
        path=relative_path,
        title=title,
        content_hash=chash,
        frontmatter=dict(fm.metadata),
        tags=tags,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["path"],
        set_={
            "title": stmt.excluded.title,
            "content_hash": stmt.excluded.content_hash,
            "frontmatter": stmt.excluded.frontmatter,
            "tags": stmt.excluded.tags,
            "updated_at": func.now(),
        },
    )
    await session.execute(stmt)

    # Update search vector
    await session.execute(
        text("""
            UPDATE documents
            SET search_vector = to_tsvector('korean', coalesce(title, '') || ' ' || :content)
            WHERE path = :path
        """),
        {"path": relative_path, "content": fm.content},
    )

    # Re-create links for this doc
    await session.execute(delete(Link).where(Link.source_path == relative_path))
    links = _extract_links(fm.content)
    for target, alias in links:
        await session.execute(
            insert(Link)
            .values(source_path=relative_path, target_path=target, alias=alias)
            .on_conflict_do_nothing()
        )

    await session.flush()


async def full_reindex(session: AsyncSession) -> int:
    """Reindex all markdown files in the vault. Returns count."""
    vault = Path(settings.vault_local_path)
    await session.execute(delete(Link))
    await session.execute(delete(Document))

    count = 0
    for md_file in vault.rglob("*.md"):
        if md_file.name.startswith(".") or ".obsidian" in md_file.parts:
            continue
        relative = str(md_file.relative_to(vault))
        content = md_file.read_text(encoding="utf-8", errors="replace")
        await index_file(session, relative, content)
        count += 1

    # Refresh tag counts
    await _refresh_tag_counts(session)
    await session.commit()
    logger.info("Full reindex complete: %d documents", count)
    return count


async def incremental_reindex(session: AsyncSession, changed_paths: list[str]) -> None:
    """Reindex only changed files."""
    vault = Path(settings.vault_local_path)
    for rel in changed_paths:
        full_path = vault / rel
        if full_path.exists() and full_path.suffix.lower() == ".md":
            content = full_path.read_text(encoding="utf-8", errors="replace")
            await index_file(session, rel, content)
        else:
            # Deleted file
            await session.execute(delete(Link).where(Link.source_path == rel))
            await session.execute(delete(Document).where(Document.path == rel))

    await _refresh_tag_counts(session)
    await session.commit()


async def _refresh_tag_counts(session: AsyncSession) -> None:
    """Rebuild the tags table from documents.tags arrays."""
    await session.execute(delete(Tag))
    await session.execute(
        text("""
            INSERT INTO tags (name, doc_count)
            SELECT unnest(tags), count(*)
            FROM documents
            WHERE tags != '{}'
            GROUP BY unnest(tags)
            ON CONFLICT (name) DO UPDATE SET doc_count = EXCLUDED.doc_count
        """)
    )
