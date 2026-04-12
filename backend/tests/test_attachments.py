import subprocess

import pytest


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
async def test_get_attachment_not_found(client, auth_headers, setup_vault):
    resp = await client.get("/api/attachments/nonexistent.png", headers=auth_headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_upload_and_get_attachment(client, auth_headers, setup_vault):
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
async def test_attachment_path_traversal(client, auth_headers, setup_vault):
    resp = await client.get("/api/attachments/../../etc/passwd", headers=auth_headers)
    assert resp.status_code in (400, 404, 422, 500)
