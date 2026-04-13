"""add app settings

Revision ID: 20260413_0001
Revises:
Create Date: 2026-04-13 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260413_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "app_settings",
        sa.Column("id", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("sync_backend", sa.Text(), nullable=False, server_default="git"),
        sa.Column("sync_interval_seconds", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("sync_auto_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("git_remote_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("git_branch", sa.Text(), nullable=False, server_default="main"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("id = 1", name="ck_app_settings_single_row"),
        sa.CheckConstraint(
            "sync_backend IN ('git', 'webdav', 'none')",
            name="ck_app_settings_sync_backend",
        ),
        sa.CheckConstraint(
            "sync_interval_seconds >= 60",
            name="ck_app_settings_sync_interval_seconds",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.execute(
        sa.text(
            """
            INSERT INTO app_settings (
                id,
                sync_backend,
                sync_interval_seconds,
                sync_auto_enabled,
                git_remote_url,
                git_branch
            ) VALUES (
                1,
                'git',
                GREATEST(COALESCE(NULLIF(current_setting('app.bootstrap_git_sync_interval_seconds', true), ''), '300')::int, 60),
                TRUE,
                COALESCE(current_setting('app.bootstrap_git_remote_url', true), ''),
                COALESCE(NULLIF(current_setting('app.bootstrap_git_branch', true), ''), 'main')
            )
            ON CONFLICT (id) DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_table("app_settings")
