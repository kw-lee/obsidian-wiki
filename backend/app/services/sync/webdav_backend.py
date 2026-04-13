from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit
from xml.etree import ElementTree

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import WebDAVManifest
from app.schemas import SyncStatus, SyncTestResult
from app.services.conflict import merge_text_bytes
from app.services.settings import SyncRuntimeSettings
from app.services.sync.base import SyncBackend
from app.services.sync.crypto import decrypt_secret

_PROPFIND_BODY = """<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:">
  <d:prop>
    <d:getetag />
    <d:getlastmodified />
    <d:resourcetype />
  </d:prop>
</d:propfind>
"""

_DAV_NAMESPACE = {"d": "DAV:"}


@dataclass(frozen=True)
class RemoteEntry:
    path: str
    etag: str | None
    mtime: datetime | None


def _normalize_root(root: str) -> str:
    normalized = root.strip() or "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized.rstrip("/") or "/"


def build_webdav_url(base_url: str, remote_root: str) -> str:
    parsed = urlsplit(base_url.strip())
    if not parsed.scheme or not parsed.netloc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="WebDAV URL is invalid")
    joined_path = f"{parsed.path.rstrip('/')}{_normalize_root(remote_root)}"
    return urlunsplit((parsed.scheme, parsed.netloc, joined_path or "/", parsed.query, parsed.fragment))


def _hash_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _mtime_equal(left: datetime | None, right: datetime | None) -> bool:
    if left is None and right is None:
        return True
    if left is None or right is None:
        return False
    return left.astimezone(UTC).replace(microsecond=0) == right.astimezone(UTC).replace(microsecond=0)


def _is_obsidian_path(path: str) -> bool:
    return path == ".obsidian" or path.startswith(".obsidian/")


def _is_within_vault(path: Path, vault_root: Path) -> bool:
    try:
        path.resolve().relative_to(vault_root.resolve())
    except ValueError:
        return False
    return True


class WebDAVSyncBackend(SyncBackend):
    def __init__(self, runtime: SyncRuntimeSettings) -> None:
        self.runtime = runtime
        self.root_url = build_webdav_url(runtime.webdav_url, runtime.webdav_remote_root)
        self.root_path = urlsplit(self.root_url).path.rstrip("/") or "/"

    async def pull(self, db: AsyncSession) -> tuple[str | None, list[str]]:
        self._validate_config()
        async with self._client() as client:
            remote_files = await self._list_remote_files(client)
            manifests = await self._load_manifests(db)
            local_hashes = self._local_hashes()
            changed_paths: set[str] = set()

            for path, remote in remote_files.items():
                manifest = manifests.get(path)
                local_sha = local_hashes.get(path)
                manifest_sha = manifest.sha256 if manifest else None
                remote_changed = manifest is None or manifest.etag != remote.etag or not _mtime_equal(manifest.mtime, remote.mtime)
                local_changed = local_sha is not None and local_sha != manifest_sha

                if not remote_changed:
                    continue

                remote_content = await self._download_file(client, path)
                remote_sha = _hash_bytes(remote_content)

                if _is_obsidian_path(path):
                    if local_sha != remote_sha:
                        self._write_local_file(path, remote_content)
                        changed_paths.add(path)
                    await self._upsert_manifest(
                        db,
                        path=path,
                        etag=remote.etag,
                        mtime=remote.mtime,
                        sha256=remote_sha,
                        base_content=self._decode_text(remote_content),
                    )
                    continue

                if manifest is None:
                    if local_sha is not None and local_sha != remote_sha:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail={"message": f"WebDAV pull conflict: {path}", "diff": None},
                        )
                    if local_sha != remote_sha:
                        self._write_local_file(path, remote_content)
                        changed_paths.add(path)
                    await self._upsert_manifest(
                        db,
                        path=path,
                        etag=remote.etag,
                        mtime=remote.mtime,
                        sha256=remote_sha,
                        base_content=self._decode_text(remote_content),
                    )
                    continue

                if local_changed and local_sha != remote_sha:
                    local_content = self._read_local_file(path)
                    merge_result = merge_text_bytes(manifest.base_content, local_content, remote_content)
                    if merge_result.merged_content is None:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail={"message": f"WebDAV pull conflict: {path}", "diff": merge_result.diff},
                        )
                    merged_content = merge_result.merged_content
                    merged_sha = _hash_bytes(merged_content)
                    if local_sha != merged_sha:
                        self._write_local_file(path, merged_content)
                        changed_paths.add(path)
                    if remote_sha != merged_sha:
                        await self._upload_file(client, path, merged_content)
                        remote = (await self._list_remote_files(client))[path]
                    await self._upsert_manifest(
                        db,
                        path=path,
                        etag=remote.etag,
                        mtime=remote.mtime,
                        sha256=merged_sha,
                        base_content=self._decode_text(merged_content),
                    )
                    continue

                if local_sha != remote_sha:
                    self._write_local_file(path, remote_content)
                    changed_paths.add(path)
                await self._upsert_manifest(
                    db,
                    path=path,
                    etag=remote.etag,
                    mtime=remote.mtime,
                    sha256=remote_sha,
                    base_content=self._decode_text(remote_content),
                )

            for path, manifest in manifests.items():
                if path in remote_files:
                    continue
                local_sha = local_hashes.get(path)
                local_changed = local_sha is not None and local_sha != manifest.sha256
                if _is_obsidian_path(path):
                    if local_sha is not None:
                        self._delete_local_file(path)
                        changed_paths.add(path)
                    await self._delete_manifest(db, path)
                    continue
                if local_changed:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"message": f"WebDAV pull conflict: {path}", "diff": None},
                    )
                if local_sha is not None:
                    self._delete_local_file(path)
                    changed_paths.add(path)
                await self._delete_manifest(db, path)

            await db.commit()
            return f"webdav:{len(remote_files)}", sorted(changed_paths)

    async def push(self, db: AsyncSession) -> None:
        self._validate_config()
        async with self._client() as client:
            remote_files = await self._list_remote_files(client)
            manifests = await self._load_manifests(db)
            local_hashes = self._local_hashes()
            touched_paths: set[str] = set()

            for path, local_sha in local_hashes.items():
                if _is_obsidian_path(path):
                    continue
                manifest = manifests.get(path)
                remote = remote_files.get(path)
                manifest_sha = manifest.sha256 if manifest else None
                local_changed = manifest is None or local_sha != manifest_sha
                remote_changed = False
                if remote is not None:
                    remote_changed = manifest is None or manifest.etag != remote.etag or not _mtime_equal(manifest.mtime, remote.mtime)

                if not local_changed:
                    continue

                local_content = self._read_local_file(path)

                if remote is None:
                    if manifest is not None:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail={"message": f"WebDAV push conflict: {path}", "diff": None},
                        )
                    await self._upload_file(client, path, local_content)
                    touched_paths.add(path)
                    continue

                remote_content = await self._download_file(client, path)
                remote_sha = _hash_bytes(remote_content)
                if remote_changed and remote_sha != local_sha:
                    merge_result = merge_text_bytes(manifest.base_content if manifest else None, local_content, remote_content)
                    if merge_result.merged_content is None:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail={"message": f"WebDAV push conflict: {path}", "diff": merge_result.diff},
                        )
                    merged_content = merge_result.merged_content
                    merged_sha = _hash_bytes(merged_content)
                    if local_sha != merged_sha:
                        self._write_local_file(path, merged_content)
                    if remote_sha != merged_sha:
                        await self._upload_file(client, path, merged_content)
                    touched_paths.add(path)
                    continue

                if remote_sha != local_sha:
                    await self._upload_file(client, path, local_content)
                touched_paths.add(path)

            for path, manifest in manifests.items():
                if path in local_hashes or _is_obsidian_path(path):
                    continue
                remote = remote_files.get(path)
                if remote is None:
                    await self._delete_manifest(db, path)
                    continue
                remote_changed = manifest.etag != remote.etag or not _mtime_equal(manifest.mtime, remote.mtime)
                if remote_changed:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"message": f"WebDAV push conflict: {path}", "diff": None},
                    )
                await self._delete_remote_file(client, path)
                touched_paths.add(path)

            refreshed_remote = await self._list_remote_files(client)
            for path in touched_paths:
                remote = refreshed_remote.get(path)
                if remote is None:
                    await self._delete_manifest(db, path)
                    continue
                content = self._read_local_file(path)
                await self._upsert_manifest(
                    db,
                    path=path,
                    etag=remote.etag,
                    mtime=remote.mtime,
                    sha256=_hash_bytes(content),
                    base_content=self._decode_text(content),
                )

            await db.commit()

    async def status(self, db: AsyncSession) -> SyncStatus:
        self._validate_config()
        async with self._client() as client:
            remote_files = await self._list_remote_files(client)
        manifests = await self._load_manifests(db)
        local_hashes = self._local_hashes()
        ahead = 0
        behind = 0
        conflicts = 0

        all_paths = set(remote_files) | set(manifests) | set(local_hashes)
        for path in all_paths:
            manifest = manifests.get(path)
            remote = remote_files.get(path)
            local_sha = local_hashes.get(path)
            manifest_sha = manifest.sha256 if manifest else None
            local_changed = False if _is_obsidian_path(path) else local_sha is not None and local_sha != manifest_sha

            if remote is None:
                remote_changed = manifest is not None
            elif manifest is None:
                remote_changed = True
            else:
                remote_changed = manifest.etag != remote.etag or not _mtime_equal(manifest.mtime, remote.mtime)

            if _is_obsidian_path(path):
                if remote_changed:
                    behind += 1
                continue

            if local_changed and remote_changed:
                conflicts += 1
                ahead += 1
                behind += 1
            elif local_changed:
                ahead += 1
            elif remote_changed:
                behind += 1

        message = None
        if conflicts:
            message = f"{conflicts} WebDAV conflict(s) need manual resolution"
        elif not self.runtime.sync_auto_enabled:
            message = "Automatic sync is disabled"

        return SyncStatus(
            backend="webdav",
            head=f"webdav:{len(remote_files)}",
            ahead=ahead,
            behind=behind,
            dirty=bool(ahead or conflicts),
            message=message,
        )

    async def test(self) -> SyncTestResult:
        self._validate_config()
        async with self._client() as client:
            try:
                response = await client.request(
                    "PROPFIND",
                    self.root_url,
                    headers={"Depth": "0", "Content-Type": "application/xml"},
                    content=_PROPFIND_BODY,
                    auth=self._auth,
                )
            except httpx.HTTPError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"WebDAV connection failed: {exc}",
                ) from exc

        if response.status_code in (200, 207):
            return SyncTestResult(ok=True, backend="webdav", detail="WebDAV connection successful")
        if response.status_code in (401, 403):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="WebDAV authentication failed",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"WebDAV server returned {response.status_code}",
        )

    @property
    def _auth(self) -> tuple[str, str] | None:
        password = decrypt_secret(self.runtime.webdav_password_enc)
        if self.runtime.webdav_username or password:
            return (self.runtime.webdav_username, password)
        return None

    def _validate_config(self) -> None:
        if not self.runtime.webdav_url:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="WebDAV URL is required",
            )

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(verify=self.runtime.webdav_verify_tls, timeout=15.0)

    def _remote_file_url(self, relative_path: str) -> str:
        encoded = "/".join(quote(part) for part in relative_path.split("/") if part)
        return f"{self.root_url.rstrip('/')}/{encoded}" if encoded else self.root_url

    async def _list_remote_files(self, client: httpx.AsyncClient) -> dict[str, RemoteEntry]:
        response = await client.request(
            "PROPFIND",
            self.root_url,
            headers={"Depth": "infinity", "Content-Type": "application/xml"},
            content=_PROPFIND_BODY,
            auth=self._auth,
        )
        if response.status_code in (404,):
            return {}
        if response.status_code not in (200, 207):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"WebDAV server returned {response.status_code}",
            )

        root = ElementTree.fromstring(response.text)
        files: dict[str, RemoteEntry] = {}
        for item in root.findall("d:response", _DAV_NAMESPACE):
            href = item.findtext("d:href", default="", namespaces=_DAV_NAMESPACE)
            relative = self._href_to_relative_path(href)
            if relative is None:
                continue
            if self._is_collection(item):
                continue
            files[relative] = RemoteEntry(
                path=relative,
                etag=item.findtext(".//d:getetag", default=None, namespaces=_DAV_NAMESPACE),
                mtime=self._parse_http_datetime(
                    item.findtext(".//d:getlastmodified", default=None, namespaces=_DAV_NAMESPACE)
                ),
            )
        return files

    async def _download_file(self, client: httpx.AsyncClient, relative_path: str) -> bytes:
        response = await client.get(self._remote_file_url(relative_path), auth=self._auth)
        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"WebDAV download failed for {relative_path}: {response.status_code}",
            )
        return response.content

    async def _upload_file(self, client: httpx.AsyncClient, relative_path: str, content: bytes) -> None:
        response = await client.put(self._remote_file_url(relative_path), content=content, auth=self._auth)
        if response.status_code not in (200, 201, 204):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"WebDAV upload failed for {relative_path}: {response.status_code}",
            )

    async def _delete_remote_file(self, client: httpx.AsyncClient, relative_path: str) -> None:
        response = await client.request("DELETE", self._remote_file_url(relative_path), auth=self._auth)
        if response.status_code not in (200, 204, 404):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"WebDAV delete failed for {relative_path}: {response.status_code}",
            )

    def _href_to_relative_path(self, href: str) -> str | None:
        path = unquote(urlsplit(href).path).rstrip("/")
        if path == self.root_path:
            return None
        prefix = f"{self.root_path}/"
        if not path.startswith(prefix):
            return None
        return path.removeprefix(prefix)

    def _is_collection(self, item: ElementTree.Element) -> bool:
        return item.find(".//d:collection", _DAV_NAMESPACE) is not None

    def _parse_http_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        return parsedate_to_datetime(value).astimezone(UTC)

    def _vault_root(self) -> Path:
        return Path(settings.vault_local_path)

    def _local_hashes(self) -> dict[str, str]:
        root = self._vault_root()
        hashes: dict[str, str] = {}
        if not root.exists():
            return hashes
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts:
                continue
            relative = path.relative_to(root).as_posix()
            hashes[relative] = _hash_bytes(path.read_bytes())
        return hashes

    def _write_local_file(self, relative_path: str, content: bytes) -> None:
        full = (self._vault_root() / relative_path).resolve()
        if not _is_within_vault(full, self._vault_root()):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid vault path")
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_bytes(content)

    def _read_local_file(self, relative_path: str) -> bytes:
        full = (self._vault_root() / relative_path).resolve()
        if not _is_within_vault(full, self._vault_root()) or not full.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Local file not found: {relative_path}")
        return full.read_bytes()

    def _delete_local_file(self, relative_path: str) -> None:
        full = (self._vault_root() / relative_path).resolve()
        if not _is_within_vault(full, self._vault_root()):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid vault path")
        full.unlink(missing_ok=True)

    async def _load_manifests(self, db: AsyncSession) -> dict[str, WebDAVManifest]:
        result = await db.execute(select(WebDAVManifest))
        rows = result.scalars().all()
        return {row.path: row for row in rows}

    async def _upsert_manifest(
        self,
        db: AsyncSession,
        *,
        path: str,
        etag: str | None,
        mtime: datetime | None,
        sha256: str,
        base_content: str | None,
    ) -> None:
        row = await db.execute(select(WebDAVManifest).where(WebDAVManifest.path == path))
        manifest = row.scalar_one_or_none()
        if manifest is None:
            db.add(
                WebDAVManifest(
                    path=path,
                    etag=etag,
                    mtime=mtime,
                    sha256=sha256,
                    base_content=base_content,
                )
            )
            await db.flush()
            return
        manifest.etag = etag
        manifest.mtime = mtime
        manifest.sha256 = sha256
        manifest.base_content = base_content
        await db.flush()

    async def _delete_manifest(self, db: AsyncSession, path: str) -> None:
        row = await db.execute(select(WebDAVManifest).where(WebDAVManifest.path == path))
        manifest = row.scalar_one_or_none()
        if manifest is not None:
            await db.delete(manifest)
            await db.flush()

    def _decode_text(self, content: bytes) -> str | None:
        try:
            return content.decode("utf-8")
        except UnicodeDecodeError:
            return None
