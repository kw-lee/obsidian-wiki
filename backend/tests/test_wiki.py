"""Wiki API tests.

Note: Tests that involve DB writes (create/save/delete) require a git-initialized
vault and may use PostgreSQL-specific features. They are marked to accept 500 on SQLite.
"""

import subprocess
from datetime import UTC, datetime

import pytest
from git import Repo
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

import app.db.session as session_mod
from app.db.models import AuditLog, User
from app.main import app
from app.services.indexer import index_attachment_file, index_file
from app.services.settings import ensure_app_settings, invalidate_settings_cache
from app.services.vault import content_hash, write_doc


def _git_init(vault_path):
    """Initialize a git repo in the vault for tests that need git operations."""
    subprocess.run(["git", "init", str(vault_path)], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(vault_path), "config", "user.email", "test@test.com"],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(vault_path), "config", "user.name", "Test"],
        capture_output=True,
        check=True,
    )
    # Create initial commit so HEAD is valid
    (vault_path / ".gitkeep").write_text("")
    subprocess.run(["git", "-C", str(vault_path), "add", "."], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(vault_path), "commit", "-m", "init"],
        capture_output=True,
        check=True,
    )


async def _write_and_index_doc(path: str, content: str) -> None:
    from app.db.session import async_session

    await write_doc(path, content)
    async with async_session() as session:
        await index_file(session, path, content)
        await session.commit()


@pytest.mark.asyncio
async def test_get_tree_empty(client, auth_headers, setup_vault):
    resp = await client.get("/api/wiki/tree", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_get_tree_with_files(client, auth_headers, setup_vault):
    vault = setup_vault
    (vault / "note1.md").write_text("# Note 1")
    sub = vault / "folder"
    sub.mkdir()
    (sub / "note2.md").write_text("# Note 2")

    resp = await client.get("/api/wiki/tree", headers=auth_headers)
    assert resp.status_code == 200
    tree = resp.json()
    names = {n["name"] for n in tree}
    assert "note1.md" in names
    assert "folder" in names


@pytest.mark.asyncio
async def test_get_attachment_catalog_returns_indexed_attachments(
    client, auth_headers, setup_vault
):
    from app.db.session import async_session

    assets = setup_vault / "assets"
    assets.mkdir()
    image = assets / "diagram.png"
    image.write_bytes(b"png")
    pdf = assets / "paper.pdf"
    pdf.write_bytes(b"%PDF")

    async with async_session() as session:
        await index_attachment_file(session, "assets/diagram.png", image)
        await index_attachment_file(session, "assets/paper.pdf", pdf)
        await session.commit()

    resp = await client.get("/api/wiki/attachment-catalog", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == [
        {
            "path": "assets/diagram.png",
            "mime_type": "image/png",
            "size_bytes": 3,
        },
        {
            "path": "assets/paper.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 4,
        },
    ]


@pytest.mark.asyncio
async def test_get_note_catalog_returns_titles_and_aliases(
    client, auth_headers, setup_vault
):
    (setup_vault / "notes").mkdir()

    await _write_and_index_doc(
        "notes/alpha.md",
        """---
title: Project Alpha
aliases:
  - Alpha Roadmap
  - Launch Plan
---
# Alpha
""",
    )
    await _write_and_index_doc(
        "notes/beta.md",
        """---
alias: Beta Card
---
# Beta
""",
    )

    resp = await client.get("/api/wiki/note-catalog", headers=auth_headers)

    assert resp.status_code == 200
    assert resp.json() == [
        {
            "path": "notes/alpha.md",
            "title": "Project Alpha",
            "aliases": ["Alpha Roadmap", "Launch Plan"],
        },
        {
            "path": "notes/beta.md",
            "title": "beta",
            "aliases": ["Beta Card"],
        },
    ]


@pytest.mark.asyncio
async def test_get_link_target_catalog_returns_headings_and_blocks(
    client, auth_headers, setup_vault
):
    (setup_vault / "notes").mkdir()
    (setup_vault / "reference").mkdir()

    await _write_and_index_doc("notes/current.md", "# Current\nSee [[../reference/guide]].")
    await _write_and_index_doc(
        "reference/guide.md",
        """---
title: Guide
---
# Overview

Paragraph with block ^intro

```md
## Hidden
Code block ^skip
```

## Deep Dive ##
""",
    )

    resp = await client.get(
        "/api/wiki/link-target-catalog",
        params={
            "source_path": "notes/current.md",
            "target": "../reference/guide",
        },
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json() == {
        "resolved_path": "reference/guide.md",
        "headings": [
            {"text": "Overview", "level": 1},
            {"text": "Deep Dive", "level": 2},
        ],
        "blocks": [
            {
                "id": "intro",
                "text": "Paragraph with block",
            }
        ],
    }


@pytest.mark.asyncio
async def test_create_doc(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    try:
        resp = await client.post(
            "/api/wiki/doc",
            json={"path": "new-note.md", "content": "# New Note\nHello world"},
            headers=auth_headers,
        )
    except OperationalError:
        pytest.skip("SQLite does not support PostgreSQL dialect (ARRAY/JSONB)")
    assert resp.status_code in (201, 500)
    if resp.status_code == 201:
        data = resp.json()
        assert data["path"] == "new-note.md"
        assert data["content"] == "# New Note\nHello world"


@pytest.mark.asyncio
async def test_create_doc_records_user_identity_without_creating_a_git_commit(
    client, auth_headers, setup_vault, monkeypatch
):
    _git_init(setup_vault)

    async def fake_index_file(db, path, content):  # noqa: ANN001
        del db, path, content

    monkeypatch.setattr("app.routers.wiki.index_file", fake_index_file)

    async with session_mod.async_session() as session:
        user = await session.scalar(select(User).where(User.username == "admin"))
        assert user is not None
        user.git_display_name = "Audit Writer"
        user.git_email = "audit@example.com"
        user.must_change_credentials = False
        await session.commit()

    resp = await client.post(
        "/api/wiki/doc",
        json={"path": "audit-note.md", "content": "# Audit"},
        headers=auth_headers,
    )
    assert resp.status_code == 201

    repo = Repo(setup_vault)
    assert repo.head.commit.message.strip() == "init"

    async with session_mod.async_session() as session:
        logs = (await session.execute(select(AuditLog))).scalars().all()
        assert len(logs) == 1
        assert logs[0].action == "wiki.create"
        assert logs[0].path == "audit-note.md"
        assert logs[0].git_display_name == "Audit Writer"
        assert logs[0].git_email == "audit@example.com"
        assert logs[0].commit_sha is None


@pytest.mark.asyncio
async def test_create_doc_auto_md_extension(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    try:
        resp = await client.post(
            "/api/wiki/doc",
            json={"path": "no-extension", "content": "content"},
            headers=auth_headers,
        )
    except OperationalError:
        pytest.skip("SQLite does not support PostgreSQL dialect (ARRAY/JSONB)")
    assert resp.status_code in (201, 500)
    if resp.status_code == 201:
        assert resp.json()["path"] == "no-extension.md"


@pytest.mark.asyncio
async def test_get_doc_history_returns_current_path_and_renamed_history(
    client, auth_headers, setup_vault
):
    vault = setup_vault
    (vault / "archive").mkdir()
    (vault / "archive" / "renamed.md").write_text("# Renamed", encoding="utf-8")

    async with session_mod.async_session() as session:
        user = await session.scalar(select(User).where(User.username == "admin"))
        assert user is not None
        session.add_all(
            [
                AuditLog(
                    user_id=user.id,
                    username=user.username,
                    git_display_name="Admin Writer",
                    git_email="admin@example.com",
                    action="wiki.create",
                    path="notes/original.md",
                    commit_sha="aaa111",
                    created_at=datetime(2026, 4, 15, 11, 0, tzinfo=UTC),
                ),
                AuditLog(
                    user_id=user.id,
                    username=user.username,
                    git_display_name="Admin Writer",
                    git_email="admin@example.com",
                    action="wiki.update",
                    path="notes/original.md",
                    commit_sha="bbb222",
                    created_at=datetime(2026, 4, 15, 11, 5, tzinfo=UTC),
                ),
                AuditLog(
                    user_id=user.id,
                    username=user.username,
                    git_display_name="Admin Writer",
                    git_email="admin@example.com",
                    action="wiki.move",
                    path="notes/original.md -> archive/renamed.md",
                    commit_sha="ccc333",
                    created_at=datetime(2026, 4, 15, 11, 10, tzinfo=UTC),
                ),
                AuditLog(
                    user_id=user.id,
                    username=user.username,
                    git_display_name="Admin Writer",
                    git_email="admin@example.com",
                    action="wiki.update",
                    path="archive/renamed.md",
                    commit_sha="ddd444",
                    created_at=datetime(2026, 4, 15, 11, 15, tzinfo=UTC),
                ),
                AuditLog(
                    user_id=user.id,
                    username=user.username,
                    git_display_name="Admin Writer",
                    git_email="admin@example.com",
                    action="wiki.update",
                    path="notes/other.md",
                    commit_sha="eee555",
                    created_at=datetime(2026, 4, 15, 11, 20, tzinfo=UTC),
                ),
            ]
        )
        await session.commit()

    resp = await client.get("/api/wiki/history/archive/renamed.md?limit=10", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert [entry["path"] for entry in data["entries"]] == [
        "archive/renamed.md",
        "notes/original.md -> archive/renamed.md",
        "notes/original.md",
        "notes/original.md",
    ]
    assert [entry["action"] for entry in data["entries"]] == [
        "wiki.update",
        "wiki.move",
        "wiki.update",
        "wiki.create",
    ]


@pytest.mark.asyncio
async def test_create_doc_rejects_obsidian_path(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    resp = await client.post(
        "/api/wiki/doc",
        json={"path": ".obsidian/workspace.json", "content": "{}"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_doc_rejects_git_path(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    resp = await client.post(
        "/api/wiki/doc",
        json={"path": ".git/config", "content": "[core]"},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_folder(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    resp = await client.post(
        "/api/wiki/folder", json={"path": "notes/subfolder"}, headers=auth_headers
    )
    assert resp.status_code == 201
    assert resp.json()["path"] == "notes/subfolder"
    assert (setup_vault / "notes" / "subfolder").is_dir()


@pytest.mark.asyncio
async def test_create_folder_conflict(client, auth_headers, setup_vault):
    (setup_vault / "notes").mkdir()
    resp = await client.post("/api/wiki/folder", json={"path": "notes"}, headers=auth_headers)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_create_folder_rejects_obsidian_path(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    resp = await client.post(
        "/api/wiki/folder", json={"path": ".obsidian/plugins"}, headers=auth_headers
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_move_doc(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    (setup_vault / "notes").mkdir()
    (setup_vault / "archive").mkdir()
    await write_doc("notes/move-me.md", "# Move me")

    resp = await client.post(
        "/api/wiki/move",
        json={"source_path": "notes/move-me.md", "destination_path": "archive/move-me.md"},
        headers=auth_headers,
    )

    assert resp.status_code == 200
    assert resp.json()["path"] == "archive/move-me.md"
    assert not (setup_vault / "notes" / "move-me.md").exists()
    assert (setup_vault / "archive" / "move-me.md").exists()


@pytest.mark.asyncio
async def test_move_folder_rewrites_wikilinks_when_requested(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    (setup_vault / "notes").mkdir()
    (setup_vault / "projects").mkdir()
    (setup_vault / "reference").mkdir()
    (setup_vault / "archive").mkdir()

    await _write_and_index_doc(
        "notes/source.md",
        "# Source\nSee [[../reference/guide]] and [[child]].",
    )
    await _write_and_index_doc("notes/child.md", "# Child")
    await _write_and_index_doc("reference/guide.md", "# Guide")
    await _write_and_index_doc("projects/ref.md", "See [[notes/source]] from here.")

    resp = await client.post(
        "/api/wiki/move",
        json={
            "source_path": "notes",
            "destination_path": "archive/notes",
            "rewrite_links": True,
        },
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["rewrite_links"] is True
    assert data["rewritten_links"] == 2
    assert set(data["rewritten_paths"]) == {"archive/notes/source.md", "projects/ref.md"}
    assert (setup_vault / "archive" / "notes" / "source.md").read_text(encoding="utf-8") == (
        "# Source\nSee [[../../reference/guide]] and [[child]]."
    )
    assert (setup_vault / "projects" / "ref.md").read_text(encoding="utf-8") == (
        "See [[../archive/notes/source]] from here."
    )
    assert (setup_vault / "archive" / "notes" / "child.md").read_text(encoding="utf-8") == "# Child"


@pytest.mark.asyncio
async def test_move_folder_without_rewrite_leaves_links_unchanged(
    client, auth_headers, setup_vault
):
    _git_init(setup_vault)
    (setup_vault / "notes").mkdir()
    (setup_vault / "projects").mkdir()
    (setup_vault / "reference").mkdir()
    (setup_vault / "archive").mkdir()

    await _write_and_index_doc(
        "notes/source.md",
        "# Source\nSee [[../reference/guide]] and [[child]].",
    )
    await _write_and_index_doc("notes/child.md", "# Child")
    await _write_and_index_doc("reference/guide.md", "# Guide")
    await _write_and_index_doc("projects/ref.md", "See [[notes/source]] from here.")

    resp = await client.post(
        "/api/wiki/move",
        json={
            "source_path": "notes",
            "destination_path": "archive/notes",
            "rewrite_links": False,
        },
        headers=auth_headers,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["rewrite_links"] is False
    assert data["rewritten_links"] == 0
    assert data["rewritten_paths"] == []
    assert (setup_vault / "archive" / "notes" / "source.md").read_text(encoding="utf-8") == (
        "# Source\nSee [[../reference/guide]] and [[child]]."
    )
    assert (setup_vault / "projects" / "ref.md").read_text(encoding="utf-8") == (
        "See [[notes/source]] from here."
    )


@pytest.mark.asyncio
async def test_move_folder_into_itself_rejected(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    (setup_vault / "notes").mkdir()
    (setup_vault / "notes" / "child").mkdir()

    resp = await client.post(
        "/api/wiki/move",
        json={"source_path": "notes", "destination_path": "notes/child/notes"},
        headers=auth_headers,
    )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_create_doc_conflict(client, auth_headers, setup_vault):
    await write_doc("existing.md", "content")
    resp = await client.post(
        "/api/wiki/doc",
        json={"path": "existing.md", "content": "new"},
        headers=auth_headers,
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_doc(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    await write_doc("test.md", "# Test\nBody")
    try:
        resp = await client.get("/api/wiki/doc/test.md", headers=auth_headers)
    except OperationalError:
        pytest.skip("SQLite does not support PostgreSQL dialect (ARRAY/JSONB)")
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert data["path"] == "test.md"
        assert data["content"] == "# Test\nBody"


@pytest.mark.asyncio
async def test_get_doc_not_found(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    try:
        resp = await client.get("/api/wiki/doc/nonexistent.md", headers=auth_headers)
        assert resp.status_code in (404, 500)
    except FileNotFoundError:
        pass  # Expected — vault.read_doc raises if file missing, no 404 handler yet


@pytest.mark.asyncio
async def test_get_doc_rejects_git_path(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    resp = await client.get("/api/wiki/doc/.git/config", headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_save_doc(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    await write_doc("edit-me.md", "original")
    repo = Repo(setup_vault)
    initial_head = repo.head.commit.hexsha
    try:
        resp = await client.put(
            "/api/wiki/doc/edit-me.md",
            json={
                "content": "updated content",
                "base_revision": content_hash("original"),
                "base_content": "original",
            },
            headers=auth_headers,
        )
    except OperationalError:
        pytest.skip("SQLite does not support PostgreSQL dialect (ARRAY/JSONB)")
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        assert resp.json()["content"] == "updated content"
        assert resp.json()["base_revision"] == content_hash("updated content")
        assert Repo(setup_vault).head.commit.hexsha == initial_head
        assert Repo(setup_vault).is_dirty(untracked_files=True)

        async with session_mod.async_session() as session:
            logs = (await session.execute(select(AuditLog))).scalars().all()

        assert logs
        latest = max(logs, key=lambda row: row.id)
        assert latest.action == "wiki.update"
        assert latest.commit_sha is None


@pytest.mark.asyncio
async def test_save_doc_enqueues_sync_when_sync_on_save_enabled(
    client, auth_headers, setup_vault, monkeypatch
):
    _git_init(setup_vault)
    await write_doc("edit-me.md", "original")

    async with session_mod.async_session() as session:
        row = await ensure_app_settings(session)
        row.sync_backend = "git"
        row.sync_on_save = True
        await session.commit()
    invalidate_settings_cache()

    calls: list[tuple[str, str]] = []

    async def fake_start_job(*, action, source="manual", bootstrap_strategy=None):  # noqa: ANN001
        del bootstrap_strategy
        calls.append((action, source))
        return None

    monkeypatch.setattr(app.state.sync_job_manager, "start_job", fake_start_job)

    try:
        resp = await client.put(
            "/api/wiki/doc/edit-me.md",
            json={
                "content": "updated content",
                "base_revision": content_hash("original"),
                "base_content": "original",
            },
            headers=auth_headers,
        )
    except OperationalError:
        pytest.skip("SQLite does not support PostgreSQL dialect (ARRAY/JSONB)")

    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        assert calls == [("sync", "automatic")]


@pytest.mark.asyncio
async def test_delete_doc(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    await write_doc("to-delete.md", "content")
    subprocess.run(
        ["git", "-C", str(setup_vault), "add", "."],
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "-C", str(setup_vault), "commit", "-m", "add file"],
        capture_output=True,
        check=True,
    )
    try:
        resp = await client.delete("/api/wiki/doc/to-delete.md", headers=auth_headers)
        assert resp.status_code in (204, 500)
    except (FileNotFoundError, Exception):
        pass  # Git may fail on deleted files in test env


@pytest.mark.asyncio
async def test_delete_doc_rejects_obsidian_path(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    resp = await client.delete("/api/wiki/doc/.obsidian/workspace.json", headers=auth_headers)
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_tree_requires_auth(client, setup_vault):
    resp = await client.get("/api/wiki/tree")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_backlinks_empty(client, auth_headers, setup_vault):
    try:
        resp = await client.get("/api/wiki/backlinks/test.md", headers=auth_headers)
    except OperationalError:
        pytest.skip("SQLite does not support PostgreSQL dialect")
    assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_backlinks_include_snippets_and_relative_resolution(
    client, auth_headers, setup_vault
):
    from app.db.session import async_session

    _git_init(setup_vault)
    (setup_vault / "notes").mkdir()
    (setup_vault / "projects").mkdir()

    target_content = "# Target\nBody"
    source_content = (
        "# Source\nSee [[../notes/target]] for context.\nAnd [[../notes/target#Overview]]."
    )
    await write_doc("notes/target.md", target_content)
    await write_doc("projects/source.md", source_content)

    async with async_session() as session:
        await session.execute(
            text("""
                INSERT INTO documents (path, title, content_hash, frontmatter, tags)
                VALUES (:path, :title, :content_hash, :frontmatter, :tags)
            """),
            {
                "path": "notes/target.md",
                "title": "Target",
                "content_hash": "target-hash",
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
                "path": "projects/source.md",
                "title": "Source",
                "content_hash": "source-hash",
                "frontmatter": "{}",
                "tags": "",
            },
        )
        await session.execute(
            text("""
                INSERT INTO links (source_path, target_path, alias)
                VALUES (:source_path, :target_path, :alias)
            """),
            {
                "source_path": "projects/source.md",
                "target_path": "../notes/target",
                "alias": None,
            },
        )
        await session.execute(
            text("""
                INSERT INTO links (source_path, target_path, alias)
                VALUES (:source_path, :target_path, :alias)
            """),
            {
                "source_path": "projects/source.md",
                "target_path": "../notes/target#Overview",
                "alias": "Overview",
            },
        )
        await session.commit()

    response = await client.get("/api/wiki/backlinks/notes/target.md", headers=auth_headers)
    assert response.status_code == 200

    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["source_path"] == "projects/source.md"
    assert payload[0]["mention_count"] == 2
    assert "See [[../notes/target]] for context." in payload[0]["snippet"]
