import subprocess
from pathlib import Path

import pytest
from sqlalchemy import select

from app.routers.attachments import MAX_ATTACHMENT_SIZE


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


def _make_sparse_file(path: Path, size: int) -> Path:
    with path.open("wb") as handle:
        handle.truncate(size)
    return path


@pytest.mark.asyncio
async def test_get_attachment_not_found(client, auth_headers, setup_vault):
    resp = await client.get("/api/attachments/nonexistent.png", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_and_get_attachment(client, auth_headers, setup_vault):
    from app.db.models import Attachment
    from app.db.session import async_session

    _git_init(setup_vault)
    # Upload
    resp = await client.post(
        "/api/attachments/upload",
        files={"file": ("test.txt", b"hello world", "text/plain")},
        params={"folder": "attachments"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["path"] == "attachments/test.txt"
    assert data["size"] == 11

    async with async_session() as session:
        result = await session.execute(select(Attachment).where(Attachment.path == data["path"]))
        attachment = result.scalar_one()

    assert attachment.mime_type == "text/plain"
    assert attachment.size_bytes == 11

    # Get
    resp = await client.get(f"/api/attachments/{data['path']}", headers=auth_headers)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_upload_requires_auth(client, setup_vault):
    resp = await client.post(
        "/api/attachments/upload",
        files={"file": ("test.txt", b"hello", "text/plain")},
    )
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_upload_rejects_traversal_in_folder(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    resp = await client.post(
        "/api/attachments/upload",
        files={"file": ("test.txt", b"hello", "text/plain")},
        params={"folder": "../outside"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "unsafe" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_rejects_hidden_folder(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    resp = await client.post(
        "/api/attachments/upload",
        files={"file": ("test.txt", b"hello", "text/plain")},
        params={"folder": "attachments/.obsidian"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "hidden" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_rejects_traversal_in_filename(client, auth_headers, setup_vault):
    _git_init(setup_vault)
    resp = await client.post(
        "/api/attachments/upload",
        files={"file": ("../escape.txt", b"hello", "text/plain")},
        params={"folder": "attachments"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "unsafe" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_upload_rejects_oversized_file(client, auth_headers, setup_vault, tmp_path):
    _git_init(setup_vault)
    big_file = _make_sparse_file(tmp_path / "big.bin", MAX_ATTACHMENT_SIZE + 1)
    with big_file.open("rb") as handle:
        resp = await client.post(
            "/api/attachments/upload",
            files={"file": ("big.bin", handle, "application/octet-stream")},
            params={"folder": "attachments"},
            headers=auth_headers,
        )
    assert resp.status_code == 413
    assert "too large" in resp.json()["detail"].lower()
