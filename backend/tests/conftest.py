import os

# Override settings before any app imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only"
os.environ["INIT_ADMIN_USERNAME"] = "admin"
os.environ["INIT_ADMIN_PASSWORD"] = "testpass"
os.environ["VAULT_LOCAL_PATH"] = "/tmp/test_vault"

import shutil
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Text, event
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR

from app.auth import create_token

# ── SQLite compatibility: map PostgreSQL-only types ──────────
from app.db.session import engine

_pg_type_map = {JSONB: Text, ARRAY: Text, TSVECTOR: Text}


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable WAL mode for SQLite test db."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


@pytest.fixture(autouse=True)
def setup_vault(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    os.environ["VAULT_LOCAL_PATH"] = str(vault)
    from app.config import settings

    settings.vault_local_path = str(vault)
    yield vault
    shutil.rmtree(vault, ignore_errors=True)


@pytest.fixture
def auth_headers():
    token = create_token("admin", "access")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client():
    from app.db.models import User  # noqa: F401
    from app.db.session import Base, engine

    # Patch PG-specific column types for SQLite
    for table in Base.metadata.tables.values():
        for column in table.columns:
            for pg_type, sqlite_type in _pg_type_map.items():
                if isinstance(column.type, pg_type):
                    column.type = sqlite_type()
                    break

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    from app.main import _ensure_initial_admin

    await _ensure_initial_admin()

    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
