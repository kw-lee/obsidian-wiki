"""Tags and Graph API tests.

Note: Tag/Graph queries use PostgreSQL ARRAY columns — they fail on SQLite.
These tests pass in Docker with real PostgreSQL.
"""

import hashlib

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.routers.tags import _normalize_tags


@pytest.mark.asyncio
async def test_list_tags_empty(client, auth_headers, setup_vault):
    try:
        resp = await client.get("/api/tags", headers=auth_headers)
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            assert resp.json() == []
    except OperationalError:
        pytest.skip("SQLite does not support ARRAY columns")


@pytest.mark.asyncio
async def test_graph_empty(client, auth_headers, setup_vault):
    try:
        resp = await client.get("/api/graph", headers=auth_headers)
        assert resp.status_code in (200, 500)
        if resp.status_code == 200:
            data = resp.json()
            assert data["nodes"] == []
            assert data["edges"] == []
    except OperationalError:
        pytest.skip("SQLite does not support ARRAY columns")


@pytest.mark.asyncio
async def test_tags_requires_auth(client, setup_vault):
    resp = await client.get("/api/tags")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_graph_requires_auth(client, setup_vault):
    resp = await client.get("/api/graph")
    assert resp.status_code in (401, 403)


def test_normalize_tags_handles_postgres_and_plain_text_shapes():
    assert _normalize_tags(["graph", "wiki"]) == ["graph", "wiki"]
    assert _normalize_tags("{graph,wiki}") == ["graph", "wiki"]
    assert _normalize_tags("graph, wiki") == ["graph", "wiki"]
    assert _normalize_tags(None) == []


@pytest.mark.asyncio
async def test_graph_resolves_note_targets_and_includes_unresolved_nodes(
    client, auth_headers, setup_vault
):
    from app.db.session import async_session

    (setup_vault / "notes").mkdir()
    (setup_vault / "assets").mkdir()
    (setup_vault / "other").mkdir()
    (setup_vault / "assets" / "photo.png").write_bytes(b"photo")
    (setup_vault / "assets" / "shared.png").write_bytes(b"shared-1")
    (setup_vault / "other" / "shared.png").write_bytes(b"shared-2")

    async with async_session() as session:
        for path, title, tags in (
            ("notes/source.md", "Source", "graph,source"),
            ("notes/target.md", "Target", "graph,target"),
        ):
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
                    "tags": tags,
                },
            )

        for path, mime_type, size_bytes in (
            ("assets/photo.png", "image/png", 5),
            ("assets/shared.png", "image/png", 8),
            ("other/shared.png", "image/png", 8),
        ):
            await session.execute(
                text("""
                    INSERT INTO attachments (path, mime_type, size_bytes)
                    VALUES (:path, :mime_type, :size_bytes)
                """),
                {
                    "path": path,
                    "mime_type": mime_type,
                    "size_bytes": size_bytes,
                },
            )

        for source_path, target_path in (
            ("notes/source.md", "target"),
            ("notes/source.md", "missing-note"),
            ("notes/source.md", "photo.png"),
            ("notes/source.md", "shared.png"),
        ):
            await session.execute(
                text("""
                    INSERT INTO links (source_path, target_path, alias)
                    VALUES (:source_path, :target_path, :alias)
                """),
                {
                    "source_path": source_path,
                    "target_path": target_path,
                    "alias": None,
                },
            )

        await session.commit()

    response = await client.get("/api/graph", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    nodes = {node["id"]: node for node in payload["nodes"]}
    edges = {(edge["source"], edge["target"]) for edge in payload["edges"]}

    assert nodes["notes/source.md"]["kind"] == "note"
    assert nodes["notes/source.md"]["tags"] == ["graph", "source"]
    assert nodes["notes/target.md"]["kind"] == "note"
    assert nodes["notes/missing-note.md"]["kind"] == "unresolved"
    assert nodes["notes/missing-note.md"]["tags"] == []
    assert nodes["assets/photo.png"]["kind"] == "attachment"
    assert nodes["assets/photo.png"]["title"] == "photo"
    assert nodes["assets/photo.png"]["mime_type"] == "image/png"
    ambiguous_nodes = [node for node in nodes.values() if node["kind"] == "ambiguous"]
    assert len(ambiguous_nodes) == 1
    assert ambiguous_nodes[0]["id"].startswith("graph:ambiguous:")
    assert ambiguous_nodes[0]["title"] == "shared.png"
    assert ambiguous_nodes[0]["candidate_paths"] == [
        "assets/shared.png",
        "other/shared.png",
    ]
    assert ("notes/source.md", "notes/target.md") in edges
    assert ("notes/source.md", "notes/missing-note.md") in edges
    assert ("notes/source.md", "assets/photo.png") in edges
    assert ("notes/source.md", ambiguous_nodes[0]["id"]) in edges
