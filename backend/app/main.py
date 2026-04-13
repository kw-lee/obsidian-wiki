from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import bcrypt
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.db.models import User
from app.db.session import Base, async_session, engine
from app.routers import attachments, auth, search, settings as settings_router, sync, tags, wiki
from app.services.settings import ensure_app_settings
from app.services.sync_scheduler import SyncScheduler


async def _ensure_initial_admin() -> None:
    """Create the initial admin user from env vars if no users exist.

    Safe against concurrent workers: relies on the unique constraint on
    ``users.username`` — if another worker wins the race, we swallow the
    IntegrityError instead of crashing startup.
    """
    async with async_session() as session:
        result = await session.execute(select(User).limit(1))
        if result.scalar_one_or_none() is not None:
            return
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
            # Another worker inserted the admin concurrently — fine.
            await session.rollback()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # startup: create tables (dev only; prod uses alembic)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _ensure_initial_admin()
    async with async_session() as session:
        await ensure_app_settings(session)

    scheduler = SyncScheduler(async_session)
    app.state.sync_scheduler = scheduler
    await scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()
        await engine.dispose()


app = FastAPI(title="Obsidian Wiki API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(wiki.router, prefix="/api/wiki", tags=["wiki"])
app.include_router(search.router, prefix="/api", tags=["search"])
app.include_router(attachments.router, prefix="/api/attachments", tags=["attachments"])
app.include_router(sync.router, prefix="/api/sync", tags=["sync"])
app.include_router(settings_router.router, prefix="/api/settings", tags=["settings"])
app.include_router(tags.router, prefix="/api", tags=["tags"])


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
