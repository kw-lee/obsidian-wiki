import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from app.config import settings
from app.db.models import AppSettings, Attachment, Document, EditSession, Link, Tag, User  # noqa: F401
from app.db.session import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.execute(
            text("select set_config('app.bootstrap_git_remote_url', :value, false)"),
            {"value": settings.bootstrap_git_remote_url},
        )
        await connection.execute(
            text("select set_config('app.bootstrap_git_branch', :value, false)"),
            {"value": settings.bootstrap_git_branch},
        )
        await connection.execute(
            text("select set_config('app.bootstrap_git_sync_interval_seconds', :value, false)"),
            {"value": str(settings.bootstrap_git_sync_interval_seconds)},
        )
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
