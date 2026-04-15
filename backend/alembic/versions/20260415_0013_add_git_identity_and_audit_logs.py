"""add git identity fields and audit logs

Revision ID: 20260415_0013
Revises: 20260415_0012
Create Date: 2026-04-15 20:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260415_0013"
down_revision: str | None = "20260415_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("git_display_name", sa.Text(), nullable=False, server_default="")
    )
    op.add_column("users", sa.Column("git_email", sa.Text(), nullable=False, server_default=""))

    op.execute(
        sa.text(
            """
            UPDATE users
            SET git_display_name = username
            WHERE git_display_name IS NULL OR git_display_name = ''
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET git_email = LOWER(
                REGEXP_REPLACE(username, '[^A-Za-z0-9]+', '-', 'g')
            ) || '@obsidian-wiki.local'
            WHERE git_email IS NULL OR git_email = ''
            """
        )
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.Text(), nullable=False),
        sa.Column("git_display_name", sa.Text(), nullable=False),
        sa.Column("git_email", sa.Text(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("commit_sha", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("idx_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("idx_audit_logs_user_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_column("users", "git_email")
    op.drop_column("users", "git_display_name")
