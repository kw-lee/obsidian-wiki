from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from app.config import settings


async def _scalar_bool(conn: AsyncConnection, sql: str, **params: object) -> bool:
    value = await conn.scalar(text(sql), params)
    return bool(value)


async def detect_legacy_revision(conn: AsyncConnection) -> str | None:
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
        if current_version:
            return None

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
        return "20260413_0002"

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
