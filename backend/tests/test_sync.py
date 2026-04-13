import pytest

import app.db.session as session_mod
from app.schemas import SyncStatus
from app.services.settings import ensure_app_settings
from app.services.sync_service import run_scheduled_sync


@pytest.mark.asyncio
async def test_sync_status(client, auth_headers, setup_vault):
    resp = await client.get("/api/sync/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "ahead" in data
    assert "behind" in data
    assert "dirty" in data


@pytest.mark.asyncio
async def test_sync_requires_auth(client, setup_vault):
    resp = await client.get("/api/sync/status")
    assert resp.status_code in (401, 403)

    resp = await client.post("/api/sync/pull")
    assert resp.status_code in (401, 403)

    resp = await client.post("/api/sync/push")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_run_scheduled_sync_drives_git_bidirectionally(client, monkeypatch, setup_vault):
    async with session_mod.async_session() as session:
        row = await ensure_app_settings(session)
        row.sync_backend = "git"
        row.sync_auto_enabled = True
        await session.commit()

    calls: list[str] = []
    statuses = iter(
        [
            SyncStatus(backend="git", ahead=1, behind=1, dirty=False),
            SyncStatus(backend="git", ahead=1, behind=0, dirty=False),
            SyncStatus(backend="git", ahead=0, behind=0, dirty=False),
        ]
    )

    async def fake_status(self, db):  # noqa: ANN001
        del db
        calls.append("status")
        return next(statuses)

    async def fake_pull(self, db):  # noqa: ANN001
        del db
        calls.append("pull")
        return ("sha", ["note.md"])

    async def fake_push(self, db):  # noqa: ANN001
        del db
        calls.append("push")

    monkeypatch.setattr("app.services.sync.git_backend.GitSyncBackend.status", fake_status)
    monkeypatch.setattr("app.services.sync.git_backend.GitSyncBackend.pull", fake_pull)
    monkeypatch.setattr("app.services.sync.git_backend.GitSyncBackend.push", fake_push)

    async with session_mod.async_session() as session:
        result = await run_scheduled_sync(session)

    assert calls == ["status", "pull", "status", "push", "status"]
    assert result.ahead == 0
    assert result.behind == 0


@pytest.mark.asyncio
async def test_run_scheduled_sync_drives_webdav_bidirectionally(client, monkeypatch, setup_vault):
    async with session_mod.async_session() as session:
        row = await ensure_app_settings(session)
        row.sync_backend = "webdav"
        row.sync_auto_enabled = True
        row.webdav_url = "https://dav.example.com/remote.php/dav/files/me"
        await session.commit()

    calls: list[str] = []
    statuses = iter(
        [
            SyncStatus(backend="webdav", ahead=1, behind=2, dirty=True),
            SyncStatus(backend="webdav", ahead=1, behind=0, dirty=True),
            SyncStatus(backend="webdav", ahead=0, behind=0, dirty=False),
        ]
    )

    async def fake_status(self, db):  # noqa: ANN001
        del db
        calls.append("status")
        return next(statuses)

    async def fake_pull(self, db):  # noqa: ANN001
        del db
        calls.append("pull")
        return ("webdav:1", ["note.md"])

    async def fake_push(self, db):  # noqa: ANN001
        del db
        calls.append("push")

    monkeypatch.setattr("app.services.sync.webdav_backend.WebDAVSyncBackend.status", fake_status)
    monkeypatch.setattr("app.services.sync.webdav_backend.WebDAVSyncBackend.pull", fake_pull)
    monkeypatch.setattr("app.services.sync.webdav_backend.WebDAVSyncBackend.push", fake_push)

    async with session_mod.async_session() as session:
        result = await run_scheduled_sync(session)

    assert calls == ["status", "pull", "status", "push", "status"]
    assert result.backend == "webdav"
    assert result.dirty is False
