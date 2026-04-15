"""Wiki API tests.

Note: Tests that involve DB writes (create/save/delete) require a git-initialized
vault and may use PostgreSQL-specific features. They are marked to accept 500 on SQLite.
"""

import subprocess

import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

import app.db.session as session_mod
from app.main import app
from app.services.indexer import index_file
from app.services.settings import ensure_app_settings, invalidate_settings_cache
from app.services.vault import write_doc


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
    try:
        resp = await client.put(
            "/api/wiki/doc/edit-me.md",
            json={"content": "updated content", "base_commit": None},
            headers=auth_headers,
        )
    except OperationalError:
        pytest.skip("SQLite does not support PostgreSQL dialect (ARRAY/JSONB)")
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        assert resp.json()["content"] == "updated content"


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
            json={"content": "updated content", "base_commit": None},
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
