from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.config import settings


async def _scalar_bool(conn: AsyncConnection, sql: str, **params: object) -> bool:
    value = await conn.scalar(text(sql), params)
    return bool(value)


async def detect_legacy_revision(conn: AsyncConnection) -> str | None:
    current_version: str | None = None
    has_alembic_version_table = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'alembic_version'
        )
        """,
    )
    if has_alembic_version_table:
        current_version = await conn.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))

    has_app_settings = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'app_settings'
        )
        """,
    )
    if not has_app_settings:
        return None

    has_katex_enabled = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'app_settings'
              AND column_name = 'katex_enabled'
        )
        """,
    )
    if has_katex_enabled:
        has_edit_sessions = await _scalar_bool(
            conn,
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name = 'edit_sessions'
            )
            """,
        )
        detected_revision = "20260415_0015" if has_edit_sessions else "20260415_0016"
        if current_version and current_version >= detected_revision:
            return None
        return detected_revision

    has_dataview_show_source = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'app_settings'
              AND column_name = 'dataview_show_source'
        )
        """,
    )
    if has_dataview_show_source:
        if current_version and current_version >= "20260415_0014":
            return None
        return "20260415_0014"

    has_audit_logs = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_name = 'audit_logs'
        )
        """,
    )
    has_git_email = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'users'
              AND column_name = 'git_email'
        )
        """,
    )
    if has_audit_logs or has_git_email:
        if current_version and current_version >= "20260415_0013":
            return None
        return "20260415_0013"

    has_sync_mode = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'app_settings'
              AND column_name = 'sync_mode'
        )
        """,
    )
    if has_sync_mode:
        if current_version and current_version >= "20260415_0012":
            return None
        return "20260415_0012"

    has_editor_font = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'app_settings'
              AND column_name = 'editor_font'
        )
        """,
    )
    has_editor_split_preview_enabled = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'app_settings'
              AND column_name = 'editor_split_preview_enabled'
        )
        """,
    )
    if has_editor_split_preview_enabled:
        if current_version and current_version >= "20260415_0011":
            return None
        return "20260415_0011"
    if has_editor_font:
        if current_version and current_version >= "20260415_0010":
            return None
        return "20260415_0010"

    has_dataview_enabled = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'app_settings'
              AND column_name = 'dataview_enabled'
        )
        """,
    )
    if has_dataview_enabled:
        if current_version and current_version >= "20260415_0009":
            return None
        return "20260415_0009"

    has_templater_enabled = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'app_settings'
              AND column_name = 'templater_enabled'
        )
        """,
    )
    if has_templater_enabled:
        if current_version and current_version >= "20260414_0008":
            return None
        return "20260414_0008"

    has_folder_note_enabled = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'app_settings'
              AND column_name = 'folder_note_enabled'
        )
        """,
    )
    if has_folder_note_enabled:
        if current_version and current_version >= "20260414_0007":
            return None
        return "20260414_0007"

    has_theme_preset = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'app_settings'
              AND column_name = 'theme_preset'
        )
        """,
    )
    if has_theme_preset:
        if current_version and current_version >= "20260413_0006":
            return None
        return "20260413_0006"

    has_timezone = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'app_settings'
              AND column_name = 'timezone'
        )
        """,
    )
    if has_timezone:
        if current_version and current_version >= "20260413_0005":
            return None
        return "20260413_0005"

    has_default_theme = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'app_settings'
              AND column_name = 'default_theme'
        )
        """,
    )
    if has_default_theme:
        if current_version and current_version >= "20260413_0004":
            return None
        return "20260413_0004"

    has_base_content = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'webdav_manifest'
              AND column_name = 'base_content'
        )
        """,
    )
    if has_base_content:
        if current_version and current_version >= "20260413_0003":
            return None
        return "20260413_0003"

    has_webdav_url = await _scalar_bool(
        conn,
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'app_settings'
              AND column_name = 'webdav_url'
        )
        """,
    )
    if has_webdav_url:
        if current_version and current_version >= "20260413_0002":
            return None
        return "20260413_0002"

    if current_version and current_version >= "20260413_0001":
        return None
    return "20260413_0001"


async def bootstrap_alembic_version() -> None:
    engine = create_async_engine(settings.database_url)
    try:
        async with engine.begin() as conn:
            revision = await detect_legacy_revision(conn)
            if revision is None:
                return

            print(f"Recording legacy schema as Alembic revision {revision}", flush=True)
            await conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS alembic_version (
                        version_num VARCHAR(32) NOT NULL PRIMARY KEY
                    )
                    """
                )
            )
            await conn.execute(text("DELETE FROM alembic_version"))
            await conn.execute(
                text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
                {"revision": revision},
            )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(bootstrap_alembic_version())
