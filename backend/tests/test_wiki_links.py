import hashlib

import pytest
from sqlalchemy import text

from app.services.wiki_links import parse_wikilinks, resolve_links_for_document


async def _seed_docs(session):
    documents = [
        ("notes/source.md", "source"),
        ("notes/target.md", "target"),
        ("archive/target.md", "target"),
        ("reference/topic.mdx", "topic"),
    ]
    for path, title in documents:
        await session.execute(
            text("""
                INSERT INTO documents (path, title, content_hash, frontmatter, tags)
                VALUES (:path, :title, :content_hash, :frontmatter, :tags)
            """),
            {
                "path": path,
                "title": title,
                "content_hash": hashlib.sha256(path.encode()).hexdigest(),
                "frontmatter": "{}",
                "tags": "",
            },
        )
    await session.commit()


async def test_resolve_links_for_document_prefers_same_folder(client, auth_headers, setup_vault):
    from app.db.session import async_session

    (setup_vault / "notes").mkdir()
    (setup_vault / "archive").mkdir()
    (setup_vault / "reference").mkdir()
    (setup_vault / "attachments").mkdir()
    (setup_vault / "attachments" / "diagram.png").write_bytes(b"png")

    async with async_session() as session:
        await _seed_docs(session)
        links = await resolve_links_for_document(
            session,
            "notes/source.md",
            "[[target]] [[../reference/topic]] [[diagram.png]] [[missing-note]]",
        )

    assert [link.kind for link in links] == ["note", "note", "attachment", "unresolved"]
    assert links[0].vault_path == "notes/target.md"
    assert links[1].vault_path == "reference/topic.mdx"
    assert links[2].vault_path == "attachments/diagram.png"
    assert links[3].vault_path == "notes/missing-note.md"


async def test_resolve_links_for_document_marks_ambiguous_matches(client, auth_headers, setup_vault):
    from app.db.session import async_session

    (setup_vault / "notes").mkdir()
    (setup_vault / "archive").mkdir()

    async with async_session() as session:
        await _seed_docs(session)
        links = await resolve_links_for_document(session, "root.md", "[[target]]")

    assert links[0].kind == "ambiguous"
    assert sorted(links[0].ambiguous_paths) == ["archive/target.md", "notes/target.md"]


def test_parse_wikilinks_preserves_alias_embed_and_heading():
    parsed = parse_wikilinks("![[folder/note#Heading|Alias]] and [[file.pdf]]")

    assert parsed[0].raw_target == "folder/note#Heading"
    assert parsed[0].display_text == "Alias"
    assert parsed[0].embed is True
    assert parsed[1].raw_target == "file.pdf"
    assert parsed[1].display_text == "file.pdf"
    assert parsed[1].embed is False


async def test_get_doc_returns_resolved_outgoing_links(client, auth_headers, setup_vault):
    from app.db.session import async_session

    (setup_vault / "notes").mkdir()
    (setup_vault / "notes" / "source.md").write_text("[[target#Overview]] ![[image.png]]", encoding="utf-8")
    (setup_vault / "notes" / "target.md").write_text("# Target", encoding="utf-8")
    (setup_vault / "notes" / "image.png").write_bytes(b"png")

    async with async_session() as session:
        await session.execute(
            text("""
                INSERT INTO documents (path, title, content_hash, frontmatter, tags)
                VALUES (:path, :title, :content_hash, :frontmatter, :tags)
            """),
            {
                "path": "notes/source.md",
                "title": "source",
                "content_hash": hashlib.sha256(b"source").hexdigest(),
                "frontmatter": "{}",
                "tags": "",
            },
        )
        await session.execute(
            text("""
                INSERT INTO documents (path, title, content_hash, frontmatter, tags)
                VALUES (:path, :title, :content_hash, :frontmatter, :tags)
            """),
            {
                "path": "notes/target.md",
                "title": "target",
                "content_hash": hashlib.sha256(b"target").hexdigest(),
                "frontmatter": "{}",
                "tags": "",
            },
        )
        await session.commit()

    response = await client.get("/api/wiki/doc/notes/source.md", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    assert payload["outgoing_links"][0]["kind"] == "heading"
    assert payload["outgoing_links"][0]["vault_path"] == "notes/target.md"
    assert payload["outgoing_links"][0]["subpath"] == "Overview"
    assert payload["outgoing_links"][1]["kind"] == "attachment"
    assert payload["outgoing_links"][1]["embed"] is True
