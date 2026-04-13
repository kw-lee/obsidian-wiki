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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.auth import create_token
from app.config import settings

_is_sqlite = "sqlite" in settings.database_url


def _sqlite_db_path(database_url: str) -> Path | None:
    prefix = "sqlite+aiosqlite:///"
    if not database_url.startswith(prefix):
        return None
    return Path(database_url.removeprefix(prefix))

# ── SQLite compatibility: map PostgreSQL-only types ──────────
if _is_sqlite:
    from sqlalchemy import Text, event
    from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR

    _pg_type_map = {JSONB: Text, ARRAY: Text, TSVECTOR: Text}

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
async def client(tmp_path: Path):
    import app.db.session as session_mod
    from app.db.models import User  # noqa: F401
    from app.db.session import Base
    from app.services.settings import invalidate_settings_cache

    original_database_url = settings.database_url
    database_url = settings.database_url
    if _is_sqlite:
        database_url = f"sqlite+aiosqlite:///{(tmp_path / 'test.db').as_posix()}"
        settings.database_url = database_url

    test_engine = create_async_engine(database_url, echo=False, poolclass=pool.NullPool)
    test_session = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)
    if _is_sqlite:
        event.listen(test_engine.sync_engine, "connect", _set_sqlite_pragma)

    # Override the app's engine and session with test versions (NullPool)
    _orig_engine = session_mod.engine
    _orig_session = session_mod.async_session
    session_mod.engine = test_engine
    session_mod.async_session = test_session
    invalidate_settings_cache()

    try:
        if _is_sqlite:
            db_path = _sqlite_db_path(database_url)
            await test_engine.dispose()
            if db_path and db_path.exists():
                db_path.unlink()
            for table in Base.metadata.tables.values():
                for column in table.columns:
                    for pg_type, sqlite_type in _pg_type_map.items():
                        if isinstance(column.type, pg_type):
                            column.type = sqlite_type()
                            break
            async with test_engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
                await conn.run_sync(Base.metadata.create_all)

        # Ensure initial admin user exists
        async with test_session() as session:
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
                try:
                    await session.commit()
                except IntegrityError:
                    await session.rollback()

        from app.main import app
        from app.services.sync_job_manager import SyncJobManager

        app.state.sync_job_manager = SyncJobManager(test_session)

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            yield c
    finally:
        # Restore original engine/session
        session_mod.engine = _orig_engine
        session_mod.async_session = _orig_session
        settings.database_url = original_database_url
        await test_engine.dispose()
