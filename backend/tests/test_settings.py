import asyncio

import bcrypt
import pytest

import app.db.session as session_mod
from app.db.models import AppSettings, User
from app.schemas import SyncStatus, SyncTestResult
from app.services.sync_scheduler import SyncScheduler
from app.services.sync.crypto import decrypt_secret, encrypt_secret


@pytest.mark.asyncio
async def test_get_profile(client, auth_headers, setup_vault):
    resp = await client.get("/api/settings/profile", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin"
    assert data["must_change_credentials"] is True


@pytest.mark.asyncio
async def test_update_profile_changes_username_and_password(client, auth_headers, setup_vault):
    resp = await client.put(
        "/api/settings/profile",
        json={
            "current_password": "testpass",
            "new_username": "writer",
            "new_password": "newpass123",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["must_change_credentials"] is False
    assert "access_token" in data
    assert "refresh_token" in data

    login_resp = await client.post(
        "/api/auth/login",
        json={"username": "writer", "password": "newpass123"},
    )
    assert login_resp.status_code == 200
    assert login_resp.json()["must_change_credentials"] is False


@pytest.mark.asyncio
async def test_update_profile_rejects_wrong_current_password(client, auth_headers, setup_vault):
    resp = await client.put(
        "/api/settings/profile",
        json={
            "current_password": "wrongpass",
            "new_username": "writer",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid current password"


@pytest.mark.asyncio
async def test_update_profile_rejects_username_conflict(client, auth_headers, setup_vault):
    async with session_mod.async_session() as session:
        session.add(
            User(
                username="taken",
                password_hash=bcrypt.hashpw(b"secret123", bcrypt.gensalt()).decode(),
                must_change_credentials=False,
            )
        )
        await session.commit()

    resp = await client.put(
        "/api/settings/profile",
        json={
            "current_password": "testpass",
            "new_username": "taken",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Username already taken"


@pytest.mark.asyncio
async def test_sync_settings_persist(client, auth_headers, setup_vault):
    resp = await client.put(
        "/api/settings/sync",
        json={
            "sync_backend": "git",
            "sync_interval_seconds": 120,
            "sync_auto_enabled": False,
            "git_remote_url": "git@github.com:test/vault.git",
            "git_branch": "develop",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sync_backend"] == "git"
    assert data["sync_interval_seconds"] == 120
    assert data["sync_auto_enabled"] is False
    assert data["git_remote_url"] == "git@github.com:test/vault.git"
    assert data["git_branch"] == "develop"
    assert data["status"]["message"] == "Automatic sync is disabled"

    read_resp = await client.get("/api/settings/sync", headers=auth_headers)
    assert read_resp.status_code == 200
    read_data = read_resp.json()
    assert read_data["sync_interval_seconds"] == 120
    assert read_data["git_branch"] == "develop"

    async with session_mod.async_session() as session:
        row = await session.get(AppSettings, 1)
        assert row is not None
        assert row.git_remote_url == "git@github.com:test/vault.git"
        assert row.sync_auto_enabled is False


@pytest.mark.asyncio
async def test_sync_status_reflects_disabled_backend(client, auth_headers, setup_vault):
    resp = await client.put(
        "/api/settings/sync",
        json={
            "sync_backend": "none",
            "sync_interval_seconds": 300,
            "sync_auto_enabled": False,
            "git_remote_url": "",
            "git_branch": "main",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"]["backend"] == "none"

    status_resp = await client.get("/api/sync/status", headers=auth_headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["message"] == "Sync is disabled"

    pull_resp = await client.post("/api/sync/pull", headers=auth_headers)
    assert pull_resp.status_code == 409


@pytest.mark.asyncio
async def test_sync_settings_redact_and_persist_webdav_password(
    client, auth_headers, monkeypatch, setup_vault
):
    async def fake_status(self, db) -> SyncStatus:
        del db
        return SyncStatus(backend="webdav", message="WebDAV backend configured")

    monkeypatch.setattr("app.services.sync.webdav_backend.WebDAVSyncBackend.status", fake_status)

    resp = await client.put(
        "/api/settings/sync",
        json={
            "sync_backend": "webdav",
            "sync_interval_seconds": 300,
            "sync_auto_enabled": False,
            "git_remote_url": "",
            "git_branch": "main",
            "webdav_url": "https://dav.example.com/remote.php/dav/files/me",
            "webdav_username": "me",
            "webdav_password": "app-token",
            "webdav_remote_root": "/vault",
            "webdav_verify_tls": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sync_backend"] == "webdav"
    assert data["has_webdav_password"] is True
    assert data["webdav_url"] == "https://dav.example.com/remote.php/dav/files/me"
    assert data["status"]["backend"] == "webdav"

    async with session_mod.async_session() as session:
        row = await session.get(AppSettings, 1)
        assert row is not None
        assert row.webdav_password_enc != "app-token"
        assert decrypt_secret(row.webdav_password_enc) == "app-token"

    read_resp = await client.get("/api/settings/sync", headers=auth_headers)
    assert read_resp.status_code == 200
    read_data = read_resp.json()
    assert read_data["has_webdav_password"] is True
    assert "webdav_password" not in read_data


@pytest.mark.asyncio
async def test_sync_test_endpoint_uses_webdav_backend(client, auth_headers, monkeypatch, setup_vault):
    async def fake_test(self) -> SyncTestResult:
        assert self.runtime.webdav_url == "https://dav.example.com/remote.php/dav/files/me"
        assert decrypt_secret(self.runtime.webdav_password_enc) == "app-token"
        return SyncTestResult(ok=True, backend="webdav", detail="WebDAV connection successful")

    monkeypatch.setattr("app.services.sync.webdav_backend.WebDAVSyncBackend.test", fake_test)

    resp = await client.post(
        "/api/settings/sync/test",
        json={
            "sync_backend": "webdav",
            "git_remote_url": "",
            "git_branch": "main",
            "webdav_url": "https://dav.example.com/remote.php/dav/files/me",
            "webdav_username": "me",
            "webdav_password": "app-token",
            "webdav_remote_root": "/vault",
            "webdav_verify_tls": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["detail"] == "WebDAV connection successful"


def test_encrypt_secret_roundtrip():
    encrypted = encrypt_secret("secret")
    assert encrypted != "secret"
    assert decrypt_secret(encrypted) == "secret"


@pytest.mark.asyncio
async def test_sync_scheduler_reload_restarts_task():
    scheduler = SyncScheduler(session_mod.async_session)
    starts: list[str] = []

    async def fake_run_loop() -> None:
        starts.append("start")
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            starts.append("cancel")
            raise

    scheduler._run_loop = fake_run_loop  # type: ignore[method-assign]

    await scheduler.start()
    first_task = scheduler._task
    await asyncio.sleep(0)

    await scheduler.reload()
    second_task = scheduler._task
    await asyncio.sleep(0)

    assert first_task is not None
    assert second_task is not None
    assert first_task is not second_task
    assert starts.count("start") == 2
    assert starts.count("cancel") >= 1

    await scheduler.stop()
    await asyncio.sleep(0)
    assert starts.count("cancel") >= 2
