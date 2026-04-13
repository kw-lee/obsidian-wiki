from __future__ import annotations

import base64
import threading
from datetime import UTC, datetime
from email.utils import format_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest
from sqlalchemy import select

import app.db.session as session_mod
from app.db.models import WebDAVManifest


class _WebDAVState:
    def __init__(self, root_prefix: str, username: str, password: str) -> None:
        self.root_prefix = root_prefix.rstrip("/")
        self.username = username
        self.password = password
        self.files: dict[str, bytes] = {}
        self.mtimes: dict[str, datetime] = {}
        self.lock = threading.Lock()

    def set_file(self, path: str, content: bytes) -> None:
        normalized = path.lstrip("/")
        with self.lock:
            self.files[normalized] = content
            self.mtimes[normalized] = datetime.now(UTC)

    def delete_file(self, path: str) -> None:
        normalized = path.lstrip("/")
        with self.lock:
            self.files.pop(normalized, None)
            self.mtimes.pop(normalized, None)


@pytest.fixture
def webdav_server():
    state = _WebDAVState("/webdav/vault", "davuser", "davpass")

    class Handler(BaseHTTPRequestHandler):
        server_version = "TestWebDAV/1.0"

        def log_message(self, format, *args):  # noqa: A003
            return

        def _authorized(self) -> bool:
            header = self.headers.get("Authorization", "")
            if not header.startswith("Basic "):
                return False
            token = base64.b64decode(header.split(" ", 1)[1]).decode("utf-8")
            return token == f"{state.username}:{state.password}"

        def _require_auth(self) -> bool:
            if self._authorized():
                return True
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="test"')
            self.end_headers()
            return False

        def _relative_path(self) -> str | None:
            path = urlsplit(self.path).path.rstrip("/")
            if path == state.root_prefix:
                return ""
            prefix = f"{state.root_prefix}/"
            if not path.startswith(prefix):
                return None
            return path.removeprefix(prefix)

        def do_PROPFIND(self):  # noqa: N802
            if not self._require_auth():
                return
            rel = self._relative_path()
            if rel is None:
                self.send_response(404)
                self.end_headers()
                return

            depth = self.headers.get("Depth", "0")
            with state.lock:
                files = dict(state.files)
                mtimes = dict(state.mtimes)

            responses = [
                self._response_xml(state.root_prefix, is_collection=True, etag=None, mtime=None)
            ]
            if depth == "infinity":
                for path, content in sorted(files.items()):
                    responses.append(
                        self._response_xml(
                            f"{state.root_prefix}/{path}",
                            is_collection=False,
                            etag=self._etag(content),
                            mtime=mtimes[path],
                        )
                    )

            body = (
                '<?xml version="1.0" encoding="utf-8"?>'
                '<d:multistatus xmlns:d="DAV:">'
                + "".join(responses)
                + "</d:multistatus>"
            ).encode("utf-8")
            self.send_response(207)
            self.send_header("Content-Type", "application/xml; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            if not self._require_auth():
                return
            rel = self._relative_path()
            if rel is None:
                self.send_response(404)
                self.end_headers()
                return
            with state.lock:
                content = state.files.get(rel)
            if content is None:
                self.send_response(404)
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_PUT(self):  # noqa: N802
            if not self._require_auth():
                return
            rel = self._relative_path()
            if rel is None:
                self.send_response(404)
                self.end_headers()
                return
            length = int(self.headers.get("Content-Length", "0"))
            content = self.rfile.read(length)
            state.set_file(rel, content)
            self.send_response(201)
            self.end_headers()

        def do_DELETE(self):  # noqa: N802
            if not self._require_auth():
                return
            rel = self._relative_path()
            if rel is None:
                self.send_response(404)
                self.end_headers()
                return
            state.delete_file(rel)
            self.send_response(204)
            self.end_headers()

        def _etag(self, content: bytes) -> str:
            token = base64.urlsafe_b64encode(content).decode("ascii").rstrip("=") or "empty"
            return f'"{token}"'

        def _response_xml(
            self,
            href: str,
            *,
            is_collection: bool,
            etag: str | None,
            mtime: datetime | None,
        ) -> str:
            resource = "<d:collection />" if is_collection else ""
            etag_xml = f"<d:getetag>{etag}</d:getetag>" if etag else ""
            mtime_xml = (
                f"<d:getlastmodified>{format_datetime(mtime, usegmt=True)}</d:getlastmodified>"
                if mtime
                else ""
            )
            return f"""
                <d:response>
                    <d:href>{href}</d:href>
                    <d:propstat>
                        <d:prop>
                            {etag_xml}
                            {mtime_xml}
                            <d:resourcetype>{resource}</d:resourcetype>
                        </d:prop>
                        <d:status>HTTP/1.1 200 OK</d:status>
                    </d:propstat>
                </d:response>
            """

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{httpd.server_address[1]}/webdav"
    try:
        yield state, base_url
    finally:
        httpd.shutdown()
        thread.join(timeout=2)


async def _configure_webdav(client, auth_headers, base_url: str):
    resp = await client.put(
        "/api/settings/sync",
        json={
            "sync_backend": "webdav",
            "sync_interval_seconds": 300,
            "sync_auto_enabled": False,
            "git_remote_url": "",
            "git_branch": "main",
            "webdav_url": base_url,
            "webdav_username": "davuser",
            "webdav_password": "davpass",
            "webdav_remote_root": "/vault",
            "webdav_verify_tls": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_webdav_test_connection(client, auth_headers, webdav_server, setup_vault):
    _state, base_url = webdav_server
    resp = await client.post(
        "/api/settings/sync/test",
        json={
            "sync_backend": "webdav",
            "git_remote_url": "",
            "git_branch": "main",
            "webdav_url": base_url,
            "webdav_username": "davuser",
            "webdav_password": "davpass",
            "webdav_remote_root": "/vault",
            "webdav_verify_tls": True,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@pytest.mark.asyncio
async def test_webdav_pull_downloads_remote_files(client, auth_headers, webdav_server, setup_vault):
    state, base_url = webdav_server
    state.set_file("remote.md", b"# Remote\n")
    await _configure_webdav(client, auth_headers, base_url)

    resp = await client.post("/api/sync/pull", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["changed_files"] == 1
    assert (setup_vault / "remote.md").read_text(encoding="utf-8") == "# Remote\n"

    async with session_mod.async_session() as session:
        result = await session.execute(select(WebDAVManifest).where(WebDAVManifest.path == "remote.md"))
        manifest = result.scalar_one_or_none()
        assert manifest is not None


@pytest.mark.asyncio
async def test_webdav_push_uploads_local_files(client, auth_headers, webdav_server, setup_vault):
    state, base_url = webdav_server
    (setup_vault / "local.md").write_text("# Local\n", encoding="utf-8")
    await _configure_webdav(client, auth_headers, base_url)

    resp = await client.post("/api/sync/push", headers=auth_headers)
    assert resp.status_code == 200
    assert state.files["local.md"] == b"# Local\n"

    status_resp = await client.get("/api/sync/status", headers=auth_headers)
    assert status_resp.status_code == 200
    assert status_resp.json()["ahead"] == 0


@pytest.mark.asyncio
async def test_webdav_pull_detects_conflict(client, auth_headers, webdav_server, setup_vault):
    state, base_url = webdav_server
    state.set_file("note.md", b"base\n")
    await _configure_webdav(client, auth_headers, base_url)

    first_pull = await client.post("/api/sync/pull", headers=auth_headers)
    assert first_pull.status_code == 200

    (setup_vault / "note.md").write_text("local change\n", encoding="utf-8")
    state.set_file("note.md", b"remote change\n")

    resp = await client.post("/api/sync/pull", headers=auth_headers)
    assert resp.status_code == 409
    assert "note.md" in resp.json()["detail"]["message"]


@pytest.mark.asyncio
async def test_webdav_pull_auto_merges_non_overlapping_changes(
    client, auth_headers, webdav_server, setup_vault
):
    state, base_url = webdav_server
    state.set_file("merge.md", b"line1\nline2\nline3\n")
    await _configure_webdav(client, auth_headers, base_url)

    first_pull = await client.post("/api/sync/pull", headers=auth_headers)
    assert first_pull.status_code == 200

    (setup_vault / "merge.md").write_text("local\nline2\nline3\n", encoding="utf-8")
    state.set_file("merge.md", b"line1\nline2\nremote\n")

    resp = await client.post("/api/sync/pull", headers=auth_headers)
    assert resp.status_code == 200
    merged = (setup_vault / "merge.md").read_text(encoding="utf-8")
    assert merged == "local\nline2\nremote\n"
    assert state.files["merge.md"] == b"local\nline2\nremote\n"

    async with session_mod.async_session() as session:
        result = await session.execute(select(WebDAVManifest).where(WebDAVManifest.path == "merge.md"))
        manifest = result.scalar_one_or_none()
        assert manifest is not None
        assert manifest.base_content == "local\nline2\nremote\n"


@pytest.mark.asyncio
async def test_webdav_status_reports_divergence(client, auth_headers, webdav_server, setup_vault):
    state, base_url = webdav_server
    state.set_file("shared.md", b"base\n")
    state.set_file("remote-only.md", b"remote\n")
    await _configure_webdav(client, auth_headers, base_url)
    first_pull = await client.post("/api/sync/pull", headers=auth_headers)
    assert first_pull.status_code == 200

    (setup_vault / "shared.md").write_text("local changed\n", encoding="utf-8")
    state.set_file("remote-only.md", b"remote changed\n")

    status_resp = await client.get("/api/sync/status", headers=auth_headers)
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert data["backend"] == "webdav"
    assert data["ahead"] >= 1
    assert data["behind"] >= 1
