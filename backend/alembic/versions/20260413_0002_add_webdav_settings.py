"""add webdav settings

Revision ID: 20260413_0002
Revises: 20260413_0001
Create Date: 2026-04-13 00:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260413_0002"
down_revision: str | None = "20260413_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("webdav_url", sa.Text(), nullable=False, server_default=""))
    op.add_column(
        "app_settings", sa.Column("webdav_username", sa.Text(), nullable=False, server_default="")
    )
    op.add_column(
        "app_settings",
        sa.Column("webdav_password_enc", sa.Text(), nullable=False, server_default=""),
    )
    op.add_column(
        "app_settings",
        sa.Column("webdav_remote_root", sa.Text(), nullable=False, server_default="/"),
    )
    op.add_column(
        "app_settings",
        sa.Column("webdav_verify_tls", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "webdav_manifest",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("etag", sa.Text(), nullable=True),
        sa.Column("mtime", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sha256", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("path"),
    )
    op.create_index("idx_webdav_manifest_path", "webdav_manifest", ["path"])


def downgrade() -> None:
    op.drop_index("idx_webdav_manifest_path", table_name="webdav_manifest")
    op.drop_table("webdav_manifest")
    op.drop_column("app_settings", "webdav_verify_tls")
    op.drop_column("app_settings", "webdav_remote_root")
    op.drop_column("app_settings", "webdav_password_enc")
    op.drop_column("app_settings", "webdav_username")
    op.drop_column("app_settings", "webdav_url")
