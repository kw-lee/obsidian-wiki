from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    CurrentUser,
    create_token,
    get_current_user,
    get_current_user_context,
    hash_password,
    normalize_git_display_name,
    normalize_git_email,
    verify_password,
)
from app.config import settings as app_settings
from app.db.models import AuditLog, Document, Tag, User
from app.db.session import get_db
from app.schemas import (
    AppearanceSettingsResponse,
    AppearanceSettingsUpdateRequest,
    AuthTokenPair,
    PluginSettingsResponse,
    PluginSettingsUpdateRequest,
    ProfileAuditEntry,
    ProfileAuditResponse,
    ProfileSettingsResponse,
    ProfileSettingsUpdateRequest,
    RebuildIndexResponse,
    SyncSettingsResponse,
    SyncSettingsTestRequest,
    SyncSettingsUpdateRequest,
    SyncStatus,
    SyncTestResult,
    SystemAuditResponse,
    SystemDependencyStatus,
    SystemLogEntry,
    SystemLogsResponse,
    SystemSettingsResponse,
    SystemSettingsUpdateRequest,
    VaultGitStatus,
    VaultSettingsResponse,
)
from app.services.indexer import full_reindex
from app.services.log_buffer import get_recent_logs
from app.services.settings import (
    ensure_app_settings,
    get_runtime_sync_settings,
    invalidate_settings_cache,
)
from app.services.sync.crypto import encrypt_secret
from app.services.sync.targets import (
    SyncTargetValidationError,
    redact_url_secrets,
    validate_git_remote_url,
    validate_webdav_url,
)
from app.services.sync_job_manager import SyncJobManager
from app.services.sync_scheduler import SyncScheduler
from app.services.sync_service import get_active_sync_status, test_sync_backend
from app.services.system_status import (
    get_app_version,
    get_process_started_at,
    get_vault_git_status,
    ping_database,
    ping_redis,
)

router = APIRouter()


def _normalize_username(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username cannot be empty",
        )
    return normalized


async def _with_last_sync_from_jobs(request: Request, status_data: SyncStatus) -> SyncStatus:
    if status_data.last_sync is not None:
        return status_data

    manager = getattr(request.app.state, "sync_job_manager", None)
    if not isinstance(manager, SyncJobManager):
        return status_data

    last_sync = await manager.get_last_successful_finished_at(backend=status_data.backend)
    if last_sync is None:
        return status_data
    return status_data.model_copy(update={"last_sync": last_sync})


def _normalize_remote_root(value: str) -> str:
    normalized = value.strip() or "/"
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    return normalized.rstrip("/") or "/"


def _normalize_timezone(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Timezone cannot be empty",
        )
    try:
        ZoneInfo(normalized)
    except ZoneInfoNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown timezone: {normalized}",
        ) from exc
    return normalized


def _redact_sync_url(value: str) -> str:
    return redact_url_secrets(value) if value else ""


def _validate_sync_targets(git_remote_url: str, webdav_url: str) -> tuple[str, str]:
    try:
        validated_git = validate_git_remote_url(
            git_remote_url,
            allow_private_targets=app_settings.allow_private_sync_targets,
        )
        validated_webdav = validate_webdav_url(
            webdav_url,
            allow_private_targets=app_settings.allow_private_sync_targets,
        )
    except SyncTargetValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return validated_git, validated_webdav


def _build_sync_settings_response(
    *,
    sync_backend: str,
    sync_interval_seconds: int,
    sync_auto_enabled: bool,
    sync_mode: str,
    sync_run_on_startup: bool,
    sync_startup_delay_seconds: int,
    sync_on_save: bool,
    git_remote_url: str,
    git_branch: str,
    webdav_url: str,
    webdav_username: str,
    webdav_remote_root: str,
    webdav_verify_tls: bool,
    webdav_obsidian_policy: str,
    has_webdav_password: bool,
    status_data: SyncStatus,
) -> SyncSettingsResponse:
    return SyncSettingsResponse(
        sync_backend=sync_backend,
        sync_interval_seconds=sync_interval_seconds,
        sync_auto_enabled=sync_auto_enabled,
        sync_mode=sync_mode,
        sync_run_on_startup=sync_run_on_startup,
        sync_startup_delay_seconds=sync_startup_delay_seconds,
        sync_on_save=sync_on_save,
        git_remote_url=_redact_sync_url(git_remote_url),
        git_branch=git_branch,
        webdav_url=_redact_sync_url(webdav_url),
        webdav_username=webdav_username,
        webdav_remote_root=webdav_remote_root,
        webdav_verify_tls=webdav_verify_tls,
        webdav_obsidian_policy=webdav_obsidian_policy,
        has_webdav_password=has_webdav_password,
        status=status_data,
    )


def _vault_disk_usage_bytes(root: Path) -> int:
    total = 0
    if not root.exists():
        return total
    for path in root.rglob("*"):
        if path.is_file():
            total += path.stat().st_size
    return total


def _is_counted_attachment(path: Path, vault_root: Path) -> bool:
    if not path.is_file():
        return False
    if path.suffix.lower() == ".md":
        return False

    relative_parts = path.relative_to(vault_root).parts
    return not any(part.startswith(".") for part in relative_parts)


def _vault_attachment_count(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(1 for path in root.rglob("*") if _is_counted_attachment(path, root))


@router.get("/profile", response_model=ProfileSettingsResponse)
async def get_profile(
    current_user: CurrentUser = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
) -> ProfileSettingsResponse:
    user = await db.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return ProfileSettingsResponse(
        username=user.username,
        git_display_name=normalize_git_display_name(
            user.git_display_name, fallback_username=user.username
        ),
        git_email=normalize_git_email(user.git_email, fallback_username=user.username),
        must_change_credentials=user.must_change_credentials,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.put("/profile", response_model=AuthTokenPair)
async def update_profile(
    body: ProfileSettingsUpdateRequest,
    current_user: CurrentUser = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
) -> AuthTokenPair:
    user = await db.get(User, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid current password",
        )

    new_username = _normalize_username(body.new_username) or user.username
    new_password = body.new_password or None
    git_display_name = normalize_git_display_name(
        body.git_display_name, fallback_username=new_username
    )
    git_email = normalize_git_email(body.git_email)

    if new_password is not None and len(new_password) < 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 4 characters long",
        )
    if (
        new_username == user.username
        and new_password is None
        and git_display_name
        == normalize_git_display_name(user.git_display_name, fallback_username=user.username)
        and git_email == normalize_git_email(user.git_email, fallback_username=user.username)
    ):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No changes requested")

    if new_username != user.username:
        existing = await db.execute(select(User).where(User.username == new_username))
        if existing.scalar_one_or_none() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken",
            )

    user.username = new_username
    if new_password is not None:
        user.password_hash = hash_password(new_password)
    user.git_display_name = git_display_name
    user.git_email = git_email
    user.must_change_credentials = False
    await db.commit()

    return AuthTokenPair(
        access_token=create_token(user.id, "access", username=user.username, must_change=False),
        refresh_token=create_token(user.id, "refresh", username=user.username, must_change=False),
        must_change_credentials=False,
    )


@router.get("/profile/audit", response_model=ProfileAuditResponse)
async def get_profile_audit(
    limit: int = 20,
    current_user: CurrentUser = Depends(get_current_user_context),
    db: AsyncSession = Depends(get_db),
) -> ProfileAuditResponse:
    bounded_limit = max(1, min(limit, 100))
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == current_user.id)
        .order_by(desc(AuditLog.created_at), desc(AuditLog.id))
        .limit(bounded_limit)
    )
    entries = [
        ProfileAuditEntry(
            created_at=row.created_at,
            action=row.action,
            path=row.path,
            commit_sha=row.commit_sha,
            username=row.username,
            git_display_name=row.git_display_name,
            git_email=row.git_email,
        )
        for row in result.scalars().all()
    ]
    return ProfileAuditResponse(entries=entries)


@router.get("/system/audit", response_model=SystemAuditResponse)
async def get_system_audit(
    limit: int = 50,
    _username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SystemAuditResponse:
    bounded_limit = max(1, min(limit, 200))
    result = await db.execute(
        select(AuditLog).order_by(desc(AuditLog.created_at), desc(AuditLog.id)).limit(bounded_limit)
    )
    entries = [
        ProfileAuditEntry(
            created_at=row.created_at,
            action=row.action,
            path=row.path,
            commit_sha=row.commit_sha,
            username=row.username,
            git_display_name=row.git_display_name,
            git_email=row.git_email,
        )
        for row in result.scalars().all()
    ]
    return SystemAuditResponse(entries=entries)


@router.get("/sync", response_model=SyncSettingsResponse)
async def get_sync_settings(
    request: Request,
    _username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncSettingsResponse:
    row = await ensure_app_settings(db)
    status_data = await get_active_sync_status(db)
    status_data = await _with_last_sync_from_jobs(request, status_data)
    return _build_sync_settings_response(
        sync_backend=row.sync_backend,
        sync_interval_seconds=row.sync_interval_seconds,
        sync_auto_enabled=row.sync_auto_enabled,
        sync_mode=row.sync_mode,
        sync_run_on_startup=row.sync_run_on_startup,
        sync_startup_delay_seconds=row.sync_startup_delay_seconds,
        sync_on_save=row.sync_on_save,
        git_remote_url=row.git_remote_url,
        git_branch=row.git_branch,
        webdav_url=row.webdav_url,
        webdav_username=row.webdav_username,
        webdav_remote_root=row.webdav_remote_root,
        webdav_verify_tls=row.webdav_verify_tls,
        webdav_obsidian_policy=row.webdav_obsidian_policy,
        has_webdav_password=bool(row.webdav_password_enc),
        status_data=status_data,
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
    git_remote_url, webdav_url = _validate_sync_targets(body.git_remote_url, body.webdav_url)
    row.sync_backend = body.sync_backend
    row.sync_interval_seconds = body.sync_interval_seconds
    row.sync_auto_enabled = body.sync_auto_enabled
    row.sync_mode = body.sync_mode
    row.sync_run_on_startup = body.sync_run_on_startup
    row.sync_startup_delay_seconds = body.sync_startup_delay_seconds
    row.sync_on_save = body.sync_on_save
    row.git_remote_url = git_remote_url
    row.git_branch = git_branch
    row.webdav_url = webdav_url
    row.webdav_username = body.webdav_username.strip()
    row.webdav_remote_root = _normalize_remote_root(body.webdav_remote_root)
    row.webdav_verify_tls = body.webdav_verify_tls
    row.webdav_obsidian_policy = body.webdav_obsidian_policy
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
    status_data = await _with_last_sync_from_jobs(request, status_data)
    return _build_sync_settings_response(
        sync_backend=runtime.sync_backend,
        sync_interval_seconds=runtime.sync_interval_seconds,
        sync_auto_enabled=runtime.sync_auto_enabled,
        sync_mode=runtime.sync_mode,
        sync_run_on_startup=runtime.sync_run_on_startup,
        sync_startup_delay_seconds=runtime.sync_startup_delay_seconds,
        sync_on_save=runtime.sync_on_save,
        git_remote_url=runtime.git_remote_url,
        git_branch=runtime.git_branch,
        webdav_url=runtime.webdav_url,
        webdav_username=runtime.webdav_username,
        webdav_remote_root=runtime.webdav_remote_root,
        webdav_verify_tls=runtime.webdav_verify_tls,
        webdav_obsidian_policy=runtime.webdav_obsidian_policy,
        has_webdav_password=bool(runtime.webdav_password_enc),
        status_data=status_data,
    )


@router.post("/sync/test", response_model=SyncTestResult)
async def test_sync_settings(
    body: SyncSettingsTestRequest,
    _username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SyncTestResult:
    existing = await ensure_app_settings(db)
    runtime = await get_runtime_sync_settings(db)
    git_remote_url, webdav_url = _validate_sync_targets(body.git_remote_url, body.webdav_url)
    runtime = replace(
        runtime,
        sync_backend=body.sync_backend,
        sync_interval_seconds=runtime.sync_interval_seconds,
        sync_auto_enabled=runtime.sync_auto_enabled,
        git_remote_url=git_remote_url,
        git_branch=body.git_branch.strip() or "main",
        webdav_url=webdav_url,
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


@router.get("/vault", response_model=VaultSettingsResponse)
async def get_vault_settings(
    _username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VaultSettingsResponse:
    vault_path = Path(app_settings.vault_local_path)
    document_count = await db.scalar(select(func.count(Document.id)))
    tag_count = await db.scalar(select(func.count(Tag.id)))
    return VaultSettingsResponse(
        vault_path=str(vault_path),
        disk_usage_bytes=_vault_disk_usage_bytes(vault_path),
        attachment_count=_vault_attachment_count(vault_path),
        document_count=document_count or 0,
        tag_count=tag_count or 0,
    )


@router.post("/vault/rebuild-index", response_model=RebuildIndexResponse)
async def rebuild_vault_index(
    _username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RebuildIndexResponse:
    count = await full_reindex(db)
    return RebuildIndexResponse(indexed_documents=count)


@router.get("/appearance", response_model=AppearanceSettingsResponse)
async def get_appearance_settings(
    _username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AppearanceSettingsResponse:
    row = await ensure_app_settings(db)
    return AppearanceSettingsResponse(
        default_theme=row.default_theme,
        theme_preset=row.theme_preset,
        ui_font=row.ui_font,
        editor_font=row.editor_font,
    )


@router.put("/appearance", response_model=AppearanceSettingsResponse)
async def update_appearance_settings(
    body: AppearanceSettingsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _username: str = Depends(get_current_user),
) -> AppearanceSettingsResponse:
    row = await ensure_app_settings(db)
    row.default_theme = body.default_theme
    row.theme_preset = body.theme_preset
    row.ui_font = body.ui_font
    row.editor_font = body.editor_font
    await db.commit()
    invalidate_settings_cache()
    return AppearanceSettingsResponse(
        default_theme=row.default_theme,
        theme_preset=row.theme_preset,
        ui_font=row.ui_font,
        editor_font=row.editor_font,
    )


@router.get("/appearance/public", response_model=AppearanceSettingsResponse)
async def get_public_appearance_settings(
    db: AsyncSession = Depends(get_db),
) -> AppearanceSettingsResponse:
    row = await ensure_app_settings(db)
    return AppearanceSettingsResponse(
        default_theme=row.default_theme,
        theme_preset=row.theme_preset,
        ui_font=row.ui_font,
        editor_font=row.editor_font,
    )


@router.get("/plugin", response_model=PluginSettingsResponse)
async def get_plugin_settings(
    _username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PluginSettingsResponse:
    row = await ensure_app_settings(db)
    return PluginSettingsResponse(
        dataview_enabled=row.dataview_enabled,
        dataview_show_source=row.dataview_show_source,
        folder_note_enabled=row.folder_note_enabled,
        templater_enabled=row.templater_enabled,
    )


@router.put("/plugin", response_model=PluginSettingsResponse)
async def update_plugin_settings(
    body: PluginSettingsUpdateRequest,
    _username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PluginSettingsResponse:
    row = await ensure_app_settings(db)
    row.dataview_enabled = body.dataview_enabled
    row.dataview_show_source = body.dataview_show_source
    row.folder_note_enabled = body.folder_note_enabled
    row.templater_enabled = body.templater_enabled
    await db.commit()
    invalidate_settings_cache()
    return PluginSettingsResponse(
        dataview_enabled=row.dataview_enabled,
        dataview_show_source=row.dataview_show_source,
        folder_note_enabled=row.folder_note_enabled,
        templater_enabled=row.templater_enabled,
    )


@router.get("/system", response_model=SystemSettingsResponse)
async def get_system_settings(
    _username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SystemSettingsResponse:
    row = await ensure_app_settings(db)
    runtime = await get_runtime_sync_settings(db)
    sync_status = await get_active_sync_status(db)
    database_ok, database_detail = await ping_database(db)
    redis_ok, redis_detail = await ping_redis()
    started_at = get_process_started_at()
    now = datetime.now(UTC)
    uptime_seconds = max(0, int((now - started_at).total_seconds()))

    return SystemSettingsResponse(
        version=get_app_version(),
        started_at=started_at,
        timezone=row.timezone,
        editor_split_preview_enabled=row.editor_split_preview_enabled,
        uptime_seconds=uptime_seconds,
        sync_backend=runtime.sync_backend,
        sync_auto_enabled=runtime.sync_auto_enabled,
        sync_status=sync_status,
        database=SystemDependencyStatus(ok=database_ok, detail=database_detail),
        redis=SystemDependencyStatus(ok=redis_ok, detail=redis_detail),
        vault_git=VaultGitStatus(**get_vault_git_status()),
    )


@router.put("/system", response_model=SystemSettingsResponse)
async def update_system_settings(
    body: SystemSettingsUpdateRequest,
    _username: str = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SystemSettingsResponse:
    row = await ensure_app_settings(db)
    row.timezone = _normalize_timezone(body.timezone)
    row.editor_split_preview_enabled = body.editor_split_preview_enabled
    await db.commit()
    invalidate_settings_cache()
    return await get_system_settings(db=db, _username=_username)


@router.get("/system/logs", response_model=SystemLogsResponse)
async def get_system_logs(
    limit: int = 50,
    _username: str = Depends(get_current_user),
) -> SystemLogsResponse:
    bounded_limit = max(1, min(limit, 200))
    entries = [SystemLogEntry(**entry) for entry in get_recent_logs(bounded_limit)]
    return SystemLogsResponse(entries=entries)
