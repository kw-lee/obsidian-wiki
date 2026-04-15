import asyncio
import logging
from datetime import UTC, datetime

import bcrypt
import pytest
from sqlalchemy import select

import app.db.session as session_mod
from app.db.models import AppSettings, AuditLog, Document, Tag, User
from app.main import app
from app.schemas import SyncStatus, SyncTestResult
from app.services.settings import ensure_app_settings
from app.services.sync.crypto import decrypt_secret, encrypt_secret
from app.services.sync_scheduler import SyncScheduler
from app.services.sync_triggers import enqueue_startup_sync_if_enabled
from app.services.vault import write_doc


@pytest.mark.asyncio
async def test_get_profile(client, auth_headers, setup_vault):
    resp = await client.get("/api/settings/profile", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin"
    assert data["git_display_name"] == "admin"
    assert data["git_email"] == "admin@obsidian-wiki.local"
    assert data["must_change_credentials"] is True


@pytest.mark.asyncio
async def test_update_profile_changes_username_and_password(client, auth_headers, setup_vault):
    resp = await client.put(
        "/api/settings/profile",
        json={
            "current_password": "testpass",
            "new_username": "writer",
            "git_display_name": "Writer One",
            "git_email": "writer@example.com",
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

    async with session_mod.async_session() as session:
        user = await session.scalar(select(User).where(User.username == "writer"))
        assert user is not None
        assert user.git_display_name == "Writer One"
        assert user.git_email == "writer@example.com"


@pytest.mark.asyncio
async def test_update_profile_rejects_wrong_current_password(client, auth_headers, setup_vault):
    resp = await client.put(
        "/api/settings/profile",
        json={
            "current_password": "wrongpass",
            "new_username": "writer",
            "git_display_name": "Writer",
            "git_email": "writer@example.com",
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
            "git_display_name": "Taken",
            "git_email": "taken@example.com",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Username already taken"


@pytest.mark.asyncio
async def test_get_profile_audit_returns_current_user_entries_newest_first(
    client, auth_headers, setup_vault
):
    async with session_mod.async_session() as session:
        current_user = await session.scalar(select(User).where(User.username == "admin"))
        assert current_user is not None
        other_user = User(
            username="other",
            password_hash=bcrypt.hashpw(b"secret123", bcrypt.gensalt()).decode(),
            git_display_name="Other User",
            git_email="other@example.com",
            must_change_credentials=False,
        )
        session.add(other_user)
        await session.flush()
        session.add_all(
            [
                AuditLog(
                    user_id=current_user.id,
                    username=current_user.username,
                    git_display_name="Admin Writer",
                    git_email="admin@example.com",
                    action="wiki.update",
                    path="notes/second.md",
                    commit_sha="bbb222",
                    created_at=datetime(2026, 4, 15, 12, 5, tzinfo=UTC),
                ),
                AuditLog(
                    user_id=current_user.id,
                    username=current_user.username,
                    git_display_name="Admin Writer",
                    git_email="admin@example.com",
                    action="wiki.create",
                    path="notes/first.md",
                    commit_sha="aaa111",
                    created_at=datetime(2026, 4, 15, 12, 0, tzinfo=UTC),
                ),
                AuditLog(
                    user_id=other_user.id,
                    username=other_user.username,
                    git_display_name=other_user.git_display_name,
                    git_email=other_user.git_email,
                    action="wiki.delete",
                    path="notes/other.md",
                    commit_sha="ccc333",
                    created_at=datetime(2026, 4, 15, 12, 10, tzinfo=UTC),
                ),
            ]
        )
        await session.commit()

    resp = await client.get("/api/settings/profile/audit?limit=5", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert [entry["path"] for entry in data["entries"]] == [
        "notes/second.md",
        "notes/first.md",
    ]
    assert all(entry["username"] == "admin" for entry in data["entries"])
    assert data["entries"][0]["commit_sha"] == "bbb222"


@pytest.mark.asyncio
async def test_sync_settings_persist(client, auth_headers, setup_vault):
    resp = await client.put(
        "/api/settings/sync",
        json={
            "sync_backend": "git",
            "sync_interval_seconds": 120,
            "sync_auto_enabled": False,
            "sync_mode": "pull-only",
            "sync_run_on_startup": True,
            "sync_startup_delay_seconds": 15,
            "sync_on_save": True,
            "git_remote_url": "git@github.com:test/vault.git",
            "git_branch": "develop",
            "webdav_url": "",
            "webdav_username": "",
            "webdav_password": "",
            "webdav_remote_root": "/",
            "webdav_verify_tls": True,
            "webdav_obsidian_policy": "ignore",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sync_backend"] == "git"
    assert data["sync_interval_seconds"] == 120
    assert data["sync_auto_enabled"] is False
    assert data["sync_mode"] == "pull-only"
    assert data["sync_run_on_startup"] is True
    assert data["sync_startup_delay_seconds"] == 15
    assert data["sync_on_save"] is True
    assert data["git_remote_url"] == "git@github.com:test/vault.git"
    assert data["git_branch"] == "develop"
    assert data["webdav_obsidian_policy"] == "ignore"
    assert data["status"]["message"] == "Automatic sync is disabled"

    read_resp = await client.get("/api/settings/sync", headers=auth_headers)
    assert read_resp.status_code == 200
    read_data = read_resp.json()
    assert read_data["sync_interval_seconds"] == 120
    assert read_data["git_branch"] == "develop"
    assert read_data["sync_mode"] == "pull-only"
    assert read_data["sync_run_on_startup"] is True
    assert read_data["sync_on_save"] is True

    async with session_mod.async_session() as session:
        row = await session.get(AppSettings, 1)
        assert row is not None
        assert row.git_remote_url == "git@github.com:test/vault.git"
        assert row.sync_auto_enabled is False
        assert row.sync_mode == "pull-only"
        assert row.sync_run_on_startup is True
        assert row.sync_startup_delay_seconds == 15
        assert row.sync_on_save is True
        assert row.webdav_obsidian_policy == "ignore"


@pytest.mark.asyncio
async def test_sync_settings_redact_credential_bearing_urls_in_response(
    client, auth_headers, setup_vault
):
    async with session_mod.async_session() as session:
        row = await ensure_app_settings(session)
        row.git_remote_url = "https://writer:secret@example.com/private/wiki.git"
        row.webdav_url = "https://davuser:secret@dav.example.com/remote.php/dav/files/me"
        await session.commit()

    resp = await client.get("/api/settings/sync", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["git_remote_url"] == "https://example.com/private/wiki.git"
    assert data["webdav_url"] == "https://dav.example.com/remote.php/dav/files/me"


@pytest.mark.asyncio
async def test_sync_settings_reject_embedded_git_credentials(
    client, auth_headers, monkeypatch, setup_vault
):
    monkeypatch.setattr("app.config.settings.allow_private_sync_targets", False)

    resp = await client.put(
        "/api/settings/sync",
        json={
            "sync_backend": "git",
            "sync_interval_seconds": 120,
            "sync_auto_enabled": False,
            "git_remote_url": "https://writer:secret@example.com/private/wiki.git",
            "git_branch": "main",
            "webdav_url": "",
            "webdav_username": "",
            "webdav_password": "",
            "webdav_remote_root": "/",
            "webdav_verify_tls": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "embedded credentials" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_sync_settings_reject_private_webdav_targets_when_disabled(
    client, auth_headers, monkeypatch, setup_vault
):
    monkeypatch.setattr("app.config.settings.allow_private_sync_targets", False)

    resp = await client.post(
        "/api/settings/sync/test",
        json={
            "sync_backend": "webdav",
            "git_remote_url": "",
            "git_branch": "main",
            "webdav_url": "http://127.0.0.1:1900/remote.php/dav/files/me",
            "webdav_username": "me",
            "webdav_password": "app-token",
            "webdav_remote_root": "/vault",
            "webdav_verify_tls": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "private or local" in resp.json()["detail"].lower()


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
async def test_sync_settings_include_last_successful_job_time(
    client, auth_headers, monkeypatch, setup_vault
):
    finished_at = datetime(2026, 4, 13, 8, 31, tzinfo=UTC)

    async def fake_status(self, db) -> SyncStatus:
        del self, db
        return SyncStatus(backend="webdav", message="WebDAV backend configured")

    async def fake_last_successful_finished_at(*, backend=None):  # noqa: ANN001
        assert backend == "webdav"
        return finished_at

    monkeypatch.setattr("app.services.sync.webdav_backend.WebDAVSyncBackend.status", fake_status)
    monkeypatch.setattr(
        app.state.sync_job_manager,
        "get_last_successful_finished_at",
        fake_last_successful_finished_at,
    )

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
    assert resp.json()["status"]["last_sync"] == "2026-04-13T08:31:00Z"

    read_resp = await client.get("/api/settings/sync", headers=auth_headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["status"]["last_sync"] == "2026-04-13T08:31:00Z"


@pytest.mark.asyncio
async def test_sync_test_endpoint_uses_webdav_backend(
    client, auth_headers, monkeypatch, setup_vault
):
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


@pytest.mark.asyncio
async def test_get_appearance_settings_defaults_to_system(client, auth_headers, setup_vault):
    resp = await client.get("/api/settings/appearance", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {
        "default_theme": "system",
        "theme_preset": "obsidian",
        "ui_font": "system",
        "editor_font": "system",
    }


@pytest.mark.asyncio
async def test_update_appearance_settings_persists_and_is_public(client, auth_headers, setup_vault):
    resp = await client.put(
        "/api/settings/appearance",
        json={
            "default_theme": "light",
            "theme_preset": "dawn",
            "ui_font": "nanum-square",
            "editor_font": "d2coding",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "default_theme": "light",
        "theme_preset": "dawn",
        "ui_font": "nanum-square",
        "editor_font": "d2coding",
    }

    public_resp = await client.get("/api/settings/appearance/public")
    assert public_resp.status_code == 200
    assert public_resp.json() == {
        "default_theme": "light",
        "theme_preset": "dawn",
        "ui_font": "nanum-square",
        "editor_font": "d2coding",
    }

    async with session_mod.async_session() as session:
        row = await session.get(AppSettings, 1)
        assert row is not None
        assert row.default_theme == "light"
        assert row.theme_preset == "dawn"
        assert row.ui_font == "nanum-square"
        assert row.editor_font == "d2coding"


@pytest.mark.asyncio
async def test_get_plugin_settings(client, auth_headers, setup_vault):
    resp = await client.get("/api/settings/plugin", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {
        "dataview_enabled": True,
        "folder_note_enabled": False,
        "templater_enabled": False,
    }


@pytest.mark.asyncio
async def test_update_plugin_settings_persists_values(client, auth_headers, setup_vault):
    resp = await client.put(
        "/api/settings/plugin",
        json={
            "dataview_enabled": False,
            "folder_note_enabled": True,
            "templater_enabled": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {
        "dataview_enabled": False,
        "folder_note_enabled": True,
        "templater_enabled": True,
    }

    read_resp = await client.get("/api/settings/plugin", headers=auth_headers)
    assert read_resp.status_code == 200
    assert read_resp.json() == {
        "dataview_enabled": False,
        "folder_note_enabled": True,
        "templater_enabled": True,
    }

    async with session_mod.async_session() as session:
        row = await session.get(AppSettings, 1)
        assert row is not None
        assert row.dataview_enabled is False
        assert row.folder_note_enabled is True
        assert row.templater_enabled is True


@pytest.mark.asyncio
async def test_get_system_settings(client, auth_headers, monkeypatch, setup_vault):
    started_at = datetime(2026, 4, 13, 1, 0, tzinfo=UTC)

    async def fake_database_ping(db):
        del db
        return True, "Database connection successful"

    async def fake_redis_ping():
        return False, "Connection refused"

    monkeypatch.setattr("app.routers.settings.get_app_version", lambda: "0.1.0")
    monkeypatch.setattr("app.routers.settings.get_process_started_at", lambda: started_at)
    monkeypatch.setattr("app.routers.settings.ping_database", fake_database_ping)
    monkeypatch.setattr("app.routers.settings.ping_redis", fake_redis_ping)
    monkeypatch.setattr(
        "app.routers.settings.get_vault_git_status",
        lambda: {
            "available": True,
            "branch": "main",
            "head": "abc123",
            "dirty": False,
            "has_origin": True,
            "message": None,
        },
    )

    resp = await client.get("/api/settings/system", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["version"] == "0.1.0"
    assert data["started_at"] == "2026-04-13T01:00:00Z"
    assert data["timezone"] == "Asia/Seoul"
    assert data["editor_split_preview_enabled"] is False
    assert data["sync_backend"] == "git"
    assert data["sync_auto_enabled"] is True
    assert data["database"] == {"ok": True, "detail": "Database connection successful"}
    assert data["redis"] == {"ok": False, "detail": "Connection refused"}
    assert data["vault_git"]["branch"] == "main"
    assert data["vault_git"]["has_origin"] is True
    assert data["uptime_seconds"] >= 0


@pytest.mark.asyncio
async def test_update_system_settings_persists_timezone_and_split_preview(
    client, auth_headers, setup_vault
):
    resp = await client.put(
        "/api/settings/system",
        json={
            "timezone": "America/New_York",
            "editor_split_preview_enabled": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["timezone"] == "America/New_York"
    assert resp.json()["editor_split_preview_enabled"] is True

    read_resp = await client.get("/api/settings/system", headers=auth_headers)
    assert read_resp.status_code == 200
    assert read_resp.json()["timezone"] == "America/New_York"
    assert read_resp.json()["editor_split_preview_enabled"] is True

    async with session_mod.async_session() as session:
        row = await session.get(AppSettings, 1)
        assert row is not None
        assert row.timezone == "America/New_York"
        assert row.editor_split_preview_enabled is True


@pytest.mark.asyncio
async def test_get_system_logs(client, auth_headers, setup_vault):
    logger = logging.getLogger("tests.system")
    logger.warning("System log tail smoke test")

    resp = await client.get("/api/settings/system/logs?limit=20", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert any(entry["message"] == "System log tail smoke test" for entry in data["entries"])


@pytest.mark.asyncio
async def test_get_system_logs_redacts_sync_url_secrets(client, auth_headers, setup_vault):
    logger = logging.getLogger("tests.system")
    logger.warning("Sync target https://writer:secret@example.com/private/wiki.git")

    resp = await client.get("/api/settings/system/logs?limit=20", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert any(
        entry["message"] == "Sync target https://example.com/private/wiki.git"
        for entry in data["entries"]
    )
    assert all("secret@" not in entry["message"] for entry in data["entries"])


@pytest.mark.asyncio
async def test_get_system_audit_returns_all_entries_newest_first(client, auth_headers, setup_vault):
    async with session_mod.async_session() as session:
        admin = await session.scalar(select(User).where(User.username == "admin"))
        assert admin is not None
        other = User(
            username="reviewer",
            password_hash=bcrypt.hashpw(b"secret123", bcrypt.gensalt()).decode(),
            git_display_name="Reviewer",
            git_email="reviewer@example.com",
            must_change_credentials=False,
        )
        session.add(other)
        await session.flush()
        session.add_all(
            [
                AuditLog(
                    user_id=admin.id,
                    username=admin.username,
                    git_display_name="Admin Writer",
                    git_email="admin@example.com",
                    action="wiki.update",
                    path="notes/admin.md",
                    commit_sha="bbb222",
                    created_at=datetime(2026, 4, 15, 14, 5, tzinfo=UTC),
                ),
                AuditLog(
                    user_id=other.id,
                    username=other.username,
                    git_display_name=other.git_display_name,
                    git_email=other.git_email,
                    action="attachment.upload",
                    path="attachments/image.png",
                    commit_sha="ccc333",
                    created_at=datetime(2026, 4, 15, 14, 10, tzinfo=UTC),
                ),
                AuditLog(
                    user_id=admin.id,
                    username=admin.username,
                    git_display_name="Admin Writer",
                    git_email="admin@example.com",
                    action="wiki.create",
                    path="notes/first.md",
                    commit_sha="aaa111",
                    created_at=datetime(2026, 4, 15, 14, 0, tzinfo=UTC),
                ),
            ]
        )
        await session.commit()

    resp = await client.get("/api/settings/system/audit?limit=2", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert [entry["path"] for entry in data["entries"]] == [
        "attachments/image.png",
        "notes/admin.md",
    ]
    assert data["entries"][0]["username"] == "reviewer"
    assert data["entries"][1]["username"] == "admin"


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


@pytest.mark.asyncio
async def test_enqueue_startup_sync_if_enabled_queues_automatic_sync(client):
    del client
    async with session_mod.async_session() as session:
        row = await ensure_app_settings(session)
        row.sync_backend = "git"
        row.sync_auto_enabled = False
        row.sync_run_on_startup = True
        row.sync_startup_delay_seconds = 12
        await session.commit()

    sleep_calls: list[float] = []
    job_calls: list[tuple[str, str]] = []

    async def fake_sleep(seconds: float) -> None:
        sleep_calls.append(seconds)

    class FakeManager:
        async def start_job(self, *, action, source="manual", bootstrap_strategy=None):  # noqa: ANN001
            del bootstrap_strategy
            job_calls.append((action, source))
            return None

    await enqueue_startup_sync_if_enabled(
        session_mod.async_session,
        FakeManager(),  # type: ignore[arg-type]
        sleep=fake_sleep,  # type: ignore[call-arg]
    )

    assert sleep_calls == [12]
    assert job_calls == [("sync", "automatic")]


@pytest.mark.asyncio
async def test_get_vault_settings(client, auth_headers, setup_vault):
    await write_doc("notes/test.md", "# Test\n#tag")
    (setup_vault / "assets").mkdir(parents=True, exist_ok=True)
    (setup_vault / "assets" / "image.png").write_bytes(b"pngdata")
    (setup_vault / ".obsidian").mkdir(parents=True, exist_ok=True)
    (setup_vault / ".obsidian" / "workspace.json").write_text("{}", encoding="utf-8")

    async with session_mod.async_session() as session:
        session.add(
            Document(
                path="notes/test.md",
                title="test",
                content_hash="hash",
                frontmatter="{}",
                tags="{tag}",
            )
        )
        session.add(Tag(name="tag", doc_count=1))
        await session.commit()

    resp = await client.get("/api/settings/vault", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["vault_path"] == str(setup_vault)
    assert data["disk_usage_bytes"] >= len(b"pngdata")
    assert data["document_count"] >= 1
    assert data["attachment_count"] == 1
    assert data["tag_count"] >= 1


@pytest.mark.asyncio
async def test_rebuild_vault_index(client, auth_headers, monkeypatch, setup_vault):
    await write_doc("alpha.md", "# Alpha")
    await write_doc("beta.md", "# Beta")

    async def fake_full_reindex(session):  # noqa: ANN001
        del session
        return 2

    monkeypatch.setattr("app.routers.settings.full_reindex", fake_full_reindex)
    resp = await client.post("/api/settings/vault/rebuild-index", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["indexed_documents"] == 2
