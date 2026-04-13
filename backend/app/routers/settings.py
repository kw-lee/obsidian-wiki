from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_token, get_current_user, hash_password, verify_password
from app.db.models import User
from app.db.session import get_db
from app.schemas import (
    AuthTokenPair,
    ProfileSettingsResponse,
    ProfileSettingsUpdateRequest,
    SyncSettingsResponse,
    SyncSettingsTestRequest,
    SyncSettingsUpdateRequest,
    SyncTestResult,
)
from app.services.settings import ensure_app_settings, get_runtime_sync_settings, invalidate_settings_cache
from app.services.sync_scheduler import SyncScheduler
from app.services.sync.crypto import encrypt_secret
from app.services.sync_service import get_active_sync_status, test_sync_backend

router = APIRouter()


def _normalize_username(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username cannot be empty")
    return normalized


def _normalize_remote_root(value: str) -> str:
    normalized = value.strip() or "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized.rstrip("/") or "/"


@router.get("/profile", response_model=ProfileSettingsResponse)
async def get_profile(
    username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ProfileSettingsResponse:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return ProfileSettingsResponse(
        username=user.username,
        must_change_credentials=user.must_change_credentials,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.put("/profile", response_model=AuthTokenPair)
async def update_profile(
    body: ProfileSettingsUpdateRequest,
    username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuthTokenPair:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password")

    new_username = _normalize_username(body.new_username) or user.username
    new_password = body.new_password or None

    if new_password is not None and len(new_password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 4 characters long",
        )
    if new_username == user.username and new_password is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No changes requested")

    if new_username != user.username:
        existing = await db.execute(select(User).where(User.username == new_username))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    user.username = new_username
    if new_password is not None:
        user.password_hash = hash_password(new_password)
    user.must_change_credentials = False
    await db.commit()

    return AuthTokenPair(
        access_token=create_token(new_username, "access", must_change=False),
        refresh_token=create_token(new_username, "refresh", must_change=False),
        must_change_credentials=False,
    )


@router.get("/sync", response_model=SyncSettingsResponse)
async def get_sync_settings(
    _username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncSettingsResponse:
    row = await ensure_app_settings(db)
    status_data = await get_active_sync_status(db)
    return SyncSettingsResponse(
        sync_backend=row.sync_backend,
        sync_interval_seconds=row.sync_interval_seconds,
        sync_auto_enabled=row.sync_auto_enabled,
        git_remote_url=row.git_remote_url,
        git_branch=row.git_branch,
        webdav_url=row.webdav_url,
        webdav_username=row.webdav_username,
        webdav_remote_root=row.webdav_remote_root,
        webdav_verify_tls=row.webdav_verify_tls,
        has_webdav_password=bool(row.webdav_password_enc),
        status=status_data,
    )


@router.put("/sync", response_model=SyncSettingsResponse)
async def update_sync_settings(
    body: SyncSettingsUpdateRequest,
    request: Request,
    _username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncSettingsResponse:
    row = await ensure_app_settings(db)

    git_branch = body.git_branch.strip() or "main"
    row.sync_backend = body.sync_backend
    row.sync_interval_seconds = body.sync_interval_seconds
    row.sync_auto_enabled = body.sync_auto_enabled
    row.git_remote_url = body.git_remote_url.strip()
    row.git_branch = git_branch
    row.webdav_url = body.webdav_url.strip()
    row.webdav_username = body.webdav_username.strip()
    row.webdav_remote_root = _normalize_remote_root(body.webdav_remote_root)
    row.webdav_verify_tls = body.webdav_verify_tls
    if body.webdav_password:
        row.webdav_password_enc = encrypt_secret(body.webdav_password)
    await db.commit()

    invalidate_settings_cache()
    scheduler = getattr(request.app.state, "sync_scheduler", None)
    if isinstance(scheduler, SyncScheduler):
        await scheduler.reload()

    await db.refresh(row)
    runtime = await get_runtime_sync_settings(db, use_cache=False)
    status_data = await get_active_sync_status(db)
    return SyncSettingsResponse(
        sync_backend=runtime.sync_backend,
        sync_interval_seconds=runtime.sync_interval_seconds,
        sync_auto_enabled=runtime.sync_auto_enabled,
        git_remote_url=runtime.git_remote_url,
        git_branch=runtime.git_branch,
        webdav_url=runtime.webdav_url,
        webdav_username=runtime.webdav_username,
        webdav_remote_root=runtime.webdav_remote_root,
        webdav_verify_tls=runtime.webdav_verify_tls,
        has_webdav_password=bool(runtime.webdav_password_enc),
        status=status_data,
    )


@router.post("/sync/test", response_model=SyncTestResult)
async def test_sync_settings(
    body: SyncSettingsTestRequest,
    _username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncTestResult:
    existing = await ensure_app_settings(db)
    runtime = await get_runtime_sync_settings(db)
    runtime = runtime.__class__(
        sync_backend=body.sync_backend,
        sync_interval_seconds=runtime.sync_interval_seconds,
        sync_auto_enabled=runtime.sync_auto_enabled,
        git_remote_url=body.git_remote_url.strip(),
        git_branch=body.git_branch.strip() or "main",
        webdav_url=body.webdav_url.strip(),
        webdav_username=body.webdav_username.strip(),
        webdav_password_enc=(
            encrypt_secret(body.webdav_password)
            if body.webdav_password
            else existing.webdav_password_enc
        ),
        webdav_remote_root=_normalize_remote_root(body.webdav_remote_root),
        webdav_verify_tls=body.webdav_verify_tls,
    )
    return await test_sync_backend(db, runtime_override=runtime)
