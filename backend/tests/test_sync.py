import asyncio
import shutil
from datetime import UTC, datetime
from pathlib import Path

import pytest
from git import Actor, GitCommandError, Repo

import app.db.session as session_mod
from app.main import app
from app.schemas import SyncJobResponse, SyncStatus
from app.services.settings import ensure_app_settings
from app.services.sync_service import run_scheduled_sync

_TEST_GIT_ACTOR = Actor("Test User", "test@example.com")


async def _wait_for_job(client, auth_headers):
    for _ in range(40):
        resp = await client.get("/api/sync/job", headers=auth_headers)
        assert resp.status_code == 200
        payload = resp.json()
        if payload and payload["status"] in {"succeeded", "failed", "conflict"}:
            return payload
        await asyncio.sleep(0.05)
    raise AssertionError("Timed out waiting for sync job to finish")


async def _configure_git(client, auth_headers, remote_url: str, branch: str = "main"):
    resp = await client.put(
        "/api/settings/sync",
        json={
            "sync_backend": "git",
            "sync_interval_seconds": 300,
            "sync_auto_enabled": False,
            "git_remote_url": remote_url,
            "git_branch": branch,
            "webdav_url": "",
            "webdav_username": "",
            "webdav_password": "",
            "webdav_remote_root": "/",
            "webdav_verify_tls": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200


def _seed_git_remote(remote_path: Path, files: dict[str, str], *, branch: str = "main") -> None:
    worktree = remote_path.parent / f"{remote_path.stem}-seed"
    shutil.rmtree(worktree, ignore_errors=True)
    repo = Repo.clone_from(str(remote_path), worktree)
    repo.git.checkout("-B", branch)
    for relative_path, content in files.items():
        target = worktree / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    repo.git.add(A=True)
    repo.index.commit("seed remote", author=_TEST_GIT_ACTOR, committer=_TEST_GIT_ACTOR)
    repo.git.push("--force", "origin", f"{branch}:refs/heads/{branch}")
    shutil.rmtree(worktree, ignore_errors=True)


@pytest.fixture
def git_remote_repo(tmp_path: Path):
    remote_path = tmp_path / "remote.git"
    Repo.init(remote_path, bare=True)
    return remote_path


@pytest.fixture
def stub_git_reindex(monkeypatch):
    calls: list[int] = []

    async def fake_full_reindex(db):  # noqa: ANN001
        calls.append(1)
        await db.commit()
        return 0

    monkeypatch.setattr("app.services.sync.git_backend.full_reindex", fake_full_reindex)
    return calls


@pytest.mark.asyncio
async def test_sync_status(client, auth_headers, setup_vault):
    resp = await client.get("/api/sync/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "ahead" in data
    assert "behind" in data
    assert "dirty" in data
    assert data["timezone"] == "Asia/Seoul"


@pytest.mark.asyncio
async def test_sync_status_uses_last_successful_job_when_backend_omits_last_sync(
    client, auth_headers, setup_vault, monkeypatch
):
    finished_at = datetime(2026, 4, 13, 8, 31, tzinfo=UTC)

    async def fake_status(db):  # noqa: ANN001
        del db
        return SyncStatus(backend="webdav", head="webdav:1", timezone="Asia/Seoul")

    async def fake_last_successful_finished_at(*, backend=None):  # noqa: ANN001
        assert backend == "webdav"
        return finished_at

    monkeypatch.setattr("app.routers.sync.get_active_sync_status", fake_status)
    monkeypatch.setattr(
        app.state.sync_job_manager,
        "get_last_successful_finished_at",
        fake_last_successful_finished_at,
    )

    resp = await client.get("/api/sync/status", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["last_sync"] == "2026-04-13T08:31:00Z"
    assert resp.json()["timezone"] == "Asia/Seoul"


@pytest.mark.asyncio
async def test_sync_requires_auth(client, setup_vault):
    resp = await client.get("/api/sync/status")
    assert resp.status_code in (401, 403)

    resp = await client.post("/api/sync/pull")
    assert resp.status_code in (401, 403)

    resp = await client.post("/api/sync/push")
    assert resp.status_code in (401, 403)


@pytest.mark.asyncio
async def test_start_sync_job_endpoint_returns_job_payload(
    client, auth_headers, setup_vault, monkeypatch
):
    async def fake_start_job(*, action, source, bootstrap_strategy=None):  # noqa: ANN001
        return SyncJobResponse(
            id="job-1",
            action=action,
            source=source,
            backend="webdav",
            status="queued",
            bootstrap_strategy=bootstrap_strategy,
            message="queued",
        )

    monkeypatch.setattr(app.state.sync_job_manager, "start_job", fake_start_job)

    resp = await client.post(
        "/api/sync/job",
        json={"action": "bootstrap", "bootstrap_strategy": "remote"},
        headers=auth_headers,
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["id"] == "job-1"
    assert data["bootstrap_strategy"] == "remote"


@pytest.mark.asyncio
async def test_get_current_sync_job_endpoint_returns_latest_job(
    client, auth_headers, setup_vault, monkeypatch
):
    async def fake_get_current_job():  # noqa: ANN001
        return SyncJobResponse(
            id="job-2",
            action="pull",
            source="manual",
            backend="git",
            status="running",
            message="Fetching",
            current=1,
            total=3,
        )

    monkeypatch.setattr(app.state.sync_job_manager, "get_current_job", fake_get_current_job)

    resp = await client.get("/api/sync/job", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "job-2"
    assert data["status"] == "running"


@pytest.mark.asyncio
async def test_manual_sync_job_runs_bidirectional_cycle_even_when_auto_sync_is_disabled(
    client, auth_headers, setup_vault, monkeypatch
):
    async with session_mod.async_session() as session:
        row = await ensure_app_settings(session)
        row.sync_backend = "git"
        row.sync_auto_enabled = False
        await session.commit()

    calls: list[str] = []
    statuses = iter(
        [
            SyncStatus(backend="git", head="before", ahead=1, behind=1, dirty=False),
            SyncStatus(backend="git", head="after-pull", ahead=1, behind=0, dirty=False),
            SyncStatus(backend="git", head="after-push", ahead=0, behind=0, dirty=False),
        ]
    )

    async def fake_status(self, db):  # noqa: ANN001
        del db
        calls.append("status")
        return next(statuses)

    async def fake_pull(self, db, *, progress=None):  # noqa: ANN001
        del db
        calls.append("pull")
        if progress is not None:
            await progress(phase="pulling", message="Fetching remote changes", current=1, total=2)
        return ("after-pull", ["note.md"])

    async def fake_push(self, db, *, progress=None):  # noqa: ANN001
        del db
        calls.append("push")
        if progress is not None:
            await progress(phase="pushing", message="Pushing local changes", current=2, total=2)

    monkeypatch.setattr("app.services.sync.git_backend.GitSyncBackend.status", fake_status)
    monkeypatch.setattr("app.services.sync.git_backend.GitSyncBackend.pull", fake_pull)
    monkeypatch.setattr("app.services.sync.git_backend.GitSyncBackend.push", fake_push)

    start_resp = await client.post(
        "/api/sync/job",
        json={"action": "sync"},
        headers=auth_headers,
    )
    assert start_resp.status_code == 202
    assert start_resp.json()["action"] == "sync"

    job = await _wait_for_job(client, auth_headers)
    assert calls == ["status", "pull", "status", "push", "status"]
    assert job["status"] == "succeeded"
    assert job["action"] == "sync"
    assert job["head"] == "after-push"
    assert job["changed_files"] == 1


@pytest.mark.asyncio
async def test_git_bootstrap_remote_job_applies_remote_baseline(
    client, auth_headers, setup_vault, git_remote_repo, stub_git_reindex
):
    _seed_git_remote(git_remote_repo, {"remote.md": "# Remote Baseline\n"})
    (setup_vault / "local.md").write_text("# Local only\n", encoding="utf-8")
    await _configure_git(client, auth_headers, str(git_remote_repo))

    start_resp = await client.post(
        "/api/sync/job",
        json={"action": "bootstrap", "bootstrap_strategy": "remote"},
        headers=auth_headers,
    )
    assert start_resp.status_code == 202

    job = await _wait_for_job(client, auth_headers)
    assert job["status"] == "succeeded"
    assert job["backend"] == "git"
    assert job["bootstrap_strategy"] == "remote"
    assert (setup_vault / "remote.md").read_text(encoding="utf-8") == "# Remote Baseline\n"
    assert not (setup_vault / "local.md").exists()
    assert stub_git_reindex == [1]


@pytest.mark.asyncio
async def test_git_bootstrap_local_job_applies_local_baseline(
    client, auth_headers, setup_vault, git_remote_repo, stub_git_reindex
):
    _seed_git_remote(git_remote_repo, {"remote.md": "# Old Remote\n"})
    (setup_vault / "local.md").write_text("# Local Baseline\n", encoding="utf-8")
    await _configure_git(client, auth_headers, str(git_remote_repo))

    start_resp = await client.post(
        "/api/sync/job",
        json={"action": "bootstrap", "bootstrap_strategy": "local"},
        headers=auth_headers,
    )
    assert start_resp.status_code == 202

    job = await _wait_for_job(client, auth_headers)
    assert job["status"] == "succeeded"
    assert job["backend"] == "git"
    assert job["bootstrap_strategy"] == "local"
    assert stub_git_reindex == [1]

    remote_repo = Repo(git_remote_repo)
    assert remote_repo.git.show("refs/heads/main:local.md").strip() == "# Local Baseline"
    with pytest.raises(GitCommandError):
        remote_repo.git.show("refs/heads/main:remote.md")


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

    async def fake_pull(self, db, *, progress=None):  # noqa: ANN001
        del db
        del progress
        calls.append("pull")
        return ("sha", ["note.md"])

    async def fake_push(self, db, *, progress=None):  # noqa: ANN001
        del db
        del progress
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

    async def fake_pull(self, db, *, progress=None):  # noqa: ANN001
        del db
        del progress
        calls.append("pull")
        return ("webdav:1", ["note.md"])

    async def fake_push(self, db, *, progress=None):  # noqa: ANN001
        del db
        del progress
        calls.append("push")

    monkeypatch.setattr("app.services.sync.webdav_backend.WebDAVSyncBackend.status", fake_status)
    monkeypatch.setattr("app.services.sync.webdav_backend.WebDAVSyncBackend.pull", fake_pull)
    monkeypatch.setattr("app.services.sync.webdav_backend.WebDAVSyncBackend.push", fake_push)

    async with session_mod.async_session() as session:
        result = await run_scheduled_sync(session)

    assert calls == ["status", "pull", "status", "push", "status"]
    assert result.backend == "webdav"
    assert result.dirty is False


@pytest.mark.asyncio
async def test_run_scheduled_sync_pull_only_skips_push(client, monkeypatch, setup_vault):
    async with session_mod.async_session() as session:
        row = await ensure_app_settings(session)
        row.sync_backend = "git"
        row.sync_auto_enabled = True
        row.sync_mode = "pull-only"
        await session.commit()

    calls: list[str] = []
    statuses = iter(
        [
            SyncStatus(backend="git", ahead=1, behind=1, dirty=False),
            SyncStatus(backend="git", ahead=1, behind=0, dirty=False),
            SyncStatus(backend="git", ahead=1, behind=0, dirty=False),
        ]
    )

    async def fake_status(self, db):  # noqa: ANN001
        del db
        calls.append("status")
        return next(statuses)

    async def fake_pull(self, db, *, progress=None):  # noqa: ANN001
        del db, progress
        calls.append("pull")
        return ("sha", ["note.md"])

    async def fake_push(self, db, *, progress=None):  # noqa: ANN001
        del db, progress
        calls.append("push")

    monkeypatch.setattr("app.services.sync.git_backend.GitSyncBackend.status", fake_status)
    monkeypatch.setattr("app.services.sync.git_backend.GitSyncBackend.pull", fake_pull)
    monkeypatch.setattr("app.services.sync.git_backend.GitSyncBackend.push", fake_push)

    async with session_mod.async_session() as session:
        result = await run_scheduled_sync(session)

    assert calls == ["status", "pull", "status", "status"]
    assert result.ahead == 1
    assert result.behind == 0


@pytest.mark.asyncio
async def test_run_scheduled_sync_push_only_skips_pull(client, monkeypatch, setup_vault):
    async with session_mod.async_session() as session:
        row = await ensure_app_settings(session)
        row.sync_backend = "git"
        row.sync_auto_enabled = True
        row.sync_mode = "push-only"
        await session.commit()

    calls: list[str] = []
    statuses = iter(
        [
            SyncStatus(backend="git", ahead=1, behind=1, dirty=False),
            SyncStatus(backend="git", ahead=0, behind=1, dirty=False),
        ]
    )

    async def fake_status(self, db):  # noqa: ANN001
        del db
        calls.append("status")
        return next(statuses)

    async def fake_pull(self, db, *, progress=None):  # noqa: ANN001
        del db, progress
        calls.append("pull")
        return ("sha", ["note.md"])

    async def fake_push(self, db, *, progress=None):  # noqa: ANN001
        del db, progress
        calls.append("push")

    monkeypatch.setattr("app.services.sync.git_backend.GitSyncBackend.status", fake_status)
    monkeypatch.setattr("app.services.sync.git_backend.GitSyncBackend.pull", fake_pull)
    monkeypatch.setattr("app.services.sync.git_backend.GitSyncBackend.push", fake_push)

    async with session_mod.async_session() as session:
        result = await run_scheduled_sync(session)

    assert calls == ["status", "push", "status"]
    assert result.ahead == 0
    assert result.behind == 1


@pytest.mark.asyncio
async def test_run_scheduled_sync_pushes_dirty_git_worktree_even_without_ahead_commits(
    client, monkeypatch, setup_vault
):
    async with session_mod.async_session() as session:
        row = await ensure_app_settings(session)
        row.sync_backend = "git"
        row.sync_auto_enabled = True
        await session.commit()

    calls: list[str] = []
    statuses = iter(
        [
            SyncStatus(backend="git", ahead=0, behind=0, dirty=True),
            SyncStatus(backend="git", ahead=0, behind=0, dirty=False),
        ]
    )

    async def fake_status(self, db):  # noqa: ANN001
        del db
        calls.append("status")
        return next(statuses)

    async def fake_push(self, db, *, progress=None):  # noqa: ANN001
        del db, progress
        calls.append("push")

    monkeypatch.setattr("app.services.sync.git_backend.GitSyncBackend.status", fake_status)
    monkeypatch.setattr("app.services.sync.git_backend.GitSyncBackend.push", fake_push)

    async with session_mod.async_session() as session:
        result = await run_scheduled_sync(session)

    assert calls == ["status", "push", "status"]
    assert result.dirty is False


@pytest.mark.asyncio
async def test_manual_git_push_commits_pending_worktree_changes_before_pushing(
    client, auth_headers, setup_vault, git_remote_repo
):
    repo = Repo.init(setup_vault)
    with repo.config_writer() as config:
        config.set_value("user", "name", _TEST_GIT_ACTOR.name)
        config.set_value("user", "email", _TEST_GIT_ACTOR.email)

    repo.git.checkout("--orphan", "main")
    note = setup_vault / "note.md"
    note.write_text("# Initial\n", encoding="utf-8")
    repo.git.add(A=True)
    repo.index.commit("seed local", author=_TEST_GIT_ACTOR, committer=_TEST_GIT_ACTOR)

    await _configure_git(client, auth_headers, str(git_remote_repo), branch="main")

    note.write_text("# Updated from web\n", encoding="utf-8")

    resp = await client.post("/api/sync/push", headers=auth_headers)
    assert resp.status_code == 200

    local_repo = Repo(setup_vault)
    remote_repo = Repo(git_remote_repo)
    assert local_repo.head.commit.message == "sync: checkpoint local changes before push"
    assert remote_repo.git.show("refs/heads/main:note.md").strip() == "# Updated from web"
