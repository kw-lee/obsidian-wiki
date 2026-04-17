"""drop unused edit_sessions table

Revision ID: 20260415_0016
Revises: 20260415_0015
Create Date: 2026-04-17 17:05:00.000000
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260415_0016"
down_revision: str | None = "20260415_0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table("edit_sessions")


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE edit_sessions (
            id SERIAL PRIMARY KEY,
            doc_path TEXT NOT NULL,
            base_commit TEXT NOT NULL,
            started_at TIMESTAMPTZ DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL
        )
        """
    )
