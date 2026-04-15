import subprocess

import pytest
from sqlalchemy.exc import OperationalError

import app.db.session as session_mod
from app.services.settings import ensure_app_settings


def _git_init(vault_path):
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
    (vault_path / ".gitkeep").write_text("")
    subprocess.run(["git", "-C", str(vault_path), "add", "."], capture_output=True, check=True)
    subprocess.run(
        ["git", "-C", str(vault_path), "commit", "-m", "init"],
        capture_output=True,
        check=True,
    )


@pytest.mark.asyncio
async def test_dataview_list_from_folder(client, auth_headers, setup_vault):
    _git_init(setup_vault)

    try:
        first = await client.post(
            "/api/wiki/doc",
            json={"path": "projects/alpha.md", "content": "---\nstatus: active\n---\n# Alpha"},
            headers=auth_headers,
        )
        second = await client.post(
            "/api/wiki/doc",
            json={"path": "projects/beta.md", "content": "---\nstatus: done\n---\n# Beta"},
            headers=auth_headers,
        )
    except OperationalError:
        pytest.skip("SQLite does not support PostgreSQL dialect (ARRAY/JSONB)")
    assert first.status_code in (201, 500)
    assert second.status_code in (201, 500)
    if first.status_code != 201 or second.status_code != 201:
        pytest.skip("SQLite document upsert is not available")

    resp = await client.post(
        "/api/dataview/query",
        json={"query": 'LIST FROM "projects"'},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["kind"] == "list"
    assert len(data["rows"]) == 2
    assert data["rows"][0]["cells"][0]["link_path"] == "projects/alpha.md"


@pytest.mark.asyncio
async def test_dataview_table_from_folder(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    try:
        resp = await client.post(
            "/api/wiki/doc",
            json={
                "path": "notes/status.md",
                "content": "---\nstatus: active\ndue: 2026-04-30\n---\n# Status",
            },
            headers=auth_headers,
        )
    except OperationalError:
        pytest.skip("SQLite does not support PostgreSQL dialect (ARRAY/JSONB)")
    assert resp.status_code in (201, 500)
    if resp.status_code != 201:
        pytest.skip("SQLite document upsert is not available")

    query_resp = await client.post(
        "/api/dataview/query",
        json={"query": 'TABLE status, due, file.link FROM "notes"'},
        headers=auth_headers,
    )
    assert query_resp.status_code == 200
    data = query_resp.json()
    assert data["columns"] == ["status", "due", "file.link"]
    assert data["rows"][0]["cells"][0]["value"] == "active"
    assert data["rows"][0]["cells"][2]["link_path"] == "notes/status.md"


@pytest.mark.asyncio
async def test_dataview_rejects_unsupported_query(client, auth_headers, setup_vault):
    resp = await client.post(
        "/api/dataview/query",
        json={"query": 'TASK FROM "projects"'},
        headers=auth_headers,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_dataview_requires_auth(client, setup_vault):
    resp = await client.post("/api/dataview/query", json={"query": 'LIST FROM "projects"'})
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_dataview_rejects_queries_when_plugin_disabled(client, auth_headers, setup_vault):
    async with session_mod.async_session() as session:
        row = await ensure_app_settings(session)
        row.dataview_enabled = False
        await session.commit()

    resp = await client.post(
        "/api/dataview/query",
        json={"query": 'LIST FROM "projects"'},
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Dataview compatibility is disabled"
