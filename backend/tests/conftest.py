import os

# Set default env vars only if not already provided (Docker sets them)
_defaults = {
    "DATABASE_URL": "sqlite+aiosqlite:///test.db",
    "REDIS_URL": "redis://localhost:6379/15",
    "JWT_SECRET": "test-secret-key-for-testing-only",
    "INIT_ADMIN_USERNAME": "admin",
    "INIT_ADMIN_PASSWORD": "testpass",
    "VAULT_LOCAL_PATH": "/tmp/test_vault",
}
for key, value in _defaults.items():
    os.environ.setdefault(key, value)

import shutil
from pathlib import Path

import bcrypt
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import pool, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import create_token
from app.config import settings

_is_sqlite = "sqlite" in settings.database_url

# Create a test-specific engine with NullPool to avoid asyncpg connection conflicts
_test_engine = create_async_engine(settings.database_url, echo=False, poolclass=pool.NullPool)
_test_session = async_sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)

# ── SQLite compatibility: map PostgreSQL-only types ──────────
if _is_sqlite:
    from sqlalchemy import Text, event
    from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR

    _pg_type_map = {JSONB: Text, ARRAY: Text, TSVECTOR: Text}

    @event.listens_for(_test_engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()


@pytest.fixture(autouse=True)
def setup_vault(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    os.environ["VAULT_LOCAL_PATH"] = str(vault)
    settings.vault_local_path = str(vault)
    yield vault
    shutil.rmtree(vault, ignore_errors=True)


@pytest.fixture
def auth_headers():
    token = create_token("admin", "access")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client():
    import app.db.session as session_mod
    from app.db.models import User  # noqa: F401
    from app.db.session import Base

    # Override the app's engine and session with test versions (NullPool)
    _orig_engine = session_mod.engine
    _orig_session = session_mod.async_session
    session_mod.engine = _test_engine
    session_mod.async_session = _test_session

    try:
        if _is_sqlite:
            for table in Base.metadata.tables.values():
                for column in table.columns:
                    for pg_type, sqlite_type in _pg_type_map.items():
                        if isinstance(column.type, pg_type):
                            column.type = sqlite_type()
                            break
            async with _test_engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)

        # Ensure initial admin user exists
        async with _test_session() as session:
            result = await session.execute(select(User).limit(1))
            if result.scalar_one_or_none() is None:
                hashed = bcrypt.hashpw(
                    settings.init_admin_password.encode(), bcrypt.gensalt()
                ).decode()
                session.add(
                    User(
                        username=settings.init_admin_username,
                        password_hash=hashed,
                        must_change_credentials=True,
                    )
                )
                await session.commit()

        from app.main import app
        from app.services.sync_job_manager import SyncJobManager

        if not hasattr(app.state, "sync_job_manager"):
            app.state.sync_job_manager = SyncJobManager(_test_session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        # Restore original engine/session
        session_mod.engine = _orig_engine
        session_mod.async_session = _orig_session
