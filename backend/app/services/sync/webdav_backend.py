from __future__ import annotations

from typing import Final
from urllib.parse import urlsplit, urlunsplit

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import SyncStatus, SyncTestResult
from app.services.settings import SyncRuntimeSettings
from app.services.sync.base import SyncBackend
from app.services.sync.crypto import decrypt_secret

_PROPFIND_BODY: Final[str] = """<?xml version="1.0" encoding="utf-8" ?>
<d:propfind xmlns:d="DAV:">
  <d:prop>
    <d:displayname />
  </d:prop>
</d:propfind>
"""


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


class WebDAVSyncBackend(SyncBackend):
    def __init__(self, runtime: SyncRuntimeSettings) -> None:
        self.runtime = runtime

    async def pull(self, db: AsyncSession) -> tuple[str | None, list[str]]:
        del db
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="WebDAV sync pull is not implemented yet",
        )

    async def push(self, db: AsyncSession) -> None:
        del db
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="WebDAV sync push is not implemented yet",
        )

    async def status(self, db: AsyncSession) -> SyncStatus:
        del db
        if not self.runtime.webdav_url:
            return SyncStatus(
                backend="webdav",
                message="Configure a WebDAV URL to enable this backend",
            )
        return SyncStatus(
            backend="webdav",
            message="WebDAV backend configured. Use Test connection before enabling sync.",
        )

    async def test(self) -> SyncTestResult:
        url = build_webdav_url(self.runtime.webdav_url, self.runtime.webdav_remote_root)
        password = decrypt_secret(self.runtime.webdav_password_enc)
        auth = None
        if self.runtime.webdav_username or password:
            auth = (self.runtime.webdav_username, password)

        try:
            async with httpx.AsyncClient(verify=self.runtime.webdav_verify_tls, timeout=10.0) as client:
                response = await client.request(
                    "PROPFIND",
                    url,
                    headers={"Depth": "0", "Content-Type": "application/xml"},
                    content=_PROPFIND_BODY,
                    auth=auth,
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
