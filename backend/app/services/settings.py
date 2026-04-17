from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.models import AppSettings


@dataclass(frozen=True)
class SyncRuntimeSettings:
    sync_backend: str
    sync_interval_seconds: int
    sync_auto_enabled: bool
    sync_mode: str
    sync_run_on_startup: bool
    sync_startup_delay_seconds: int
    sync_on_save: bool
    git_remote_url: str
    git_branch: str
    webdav_url: str
    webdav_username: str
    webdav_password_enc: str
    webdav_remote_root: str
    webdav_verify_tls: bool
    webdav_obsidian_policy: str
    timezone: str
    default_theme: str
    theme_preset: str
    ui_font: str
    editor_font: str
    editor_split_preview_enabled: bool
    dataview_enabled: bool
    dataview_show_source: bool
    folder_note_enabled: bool
    templater_enabled: bool
    katex_enabled: bool


_settings_cache: SyncRuntimeSettings | None = None
_settings_lock = asyncio.Lock()


def _to_runtime_snapshot(row: AppSettings) -> SyncRuntimeSettings:
    return SyncRuntimeSettings(
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
        webdav_password_enc=row.webdav_password_enc,
        webdav_remote_root=row.webdav_remote_root,
        webdav_verify_tls=row.webdav_verify_tls,
        webdav_obsidian_policy=row.webdav_obsidian_policy,
        timezone=row.timezone,
        default_theme=row.default_theme,
        theme_preset=row.theme_preset,
        ui_font=row.ui_font,
        editor_font=row.editor_font,
        editor_split_preview_enabled=row.editor_split_preview_enabled,
        dataview_enabled=row.dataview_enabled,
        dataview_show_source=row.dataview_show_source,
        folder_note_enabled=row.folder_note_enabled,
        templater_enabled=row.templater_enabled,
        katex_enabled=row.katex_enabled,
    )


async def ensure_app_settings(db: AsyncSession) -> AppSettings:
    row = await db.get(AppSettings, 1)
    if row is not None:
        return row

    row = AppSettings(
        id=1,
        sync_backend="git",
        sync_interval_seconds=max(settings.bootstrap_git_sync_interval_seconds, 60),
        sync_auto_enabled=True,
        sync_mode="bidirectional",
        sync_run_on_startup=False,
        sync_startup_delay_seconds=10,
        sync_on_save=False,
        git_remote_url=settings.bootstrap_git_remote_url,
        git_branch=settings.bootstrap_git_branch,
        webdav_url="",
        webdav_username="",
        webdav_password_enc="",
        webdav_remote_root="/",
        webdav_verify_tls=True,
        webdav_obsidian_policy="remote-only",
        timezone=settings.app_timezone,
        default_theme="system",
        theme_preset="obsidian",
        ui_font="system",
        editor_font="system",
        editor_split_preview_enabled=False,
        dataview_enabled=True,
        dataview_show_source=False,
        folder_note_enabled=False,
        templater_enabled=False,
        katex_enabled=True,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    invalidate_settings_cache()
    return row


async def get_runtime_sync_settings(
    db: AsyncSession, *, use_cache: bool = True
) -> SyncRuntimeSettings:
    global _settings_cache
    if use_cache and _settings_cache is not None:
        return _settings_cache

    async with _settings_lock:
        if use_cache and _settings_cache is not None:
            return _settings_cache
        row = await ensure_app_settings(db)
        _settings_cache = _to_runtime_snapshot(row)
        return _settings_cache


def invalidate_settings_cache() -> None:
    global _settings_cache
    _settings_cache = None
