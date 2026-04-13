from __future__ import annotations

from contextlib import suppress
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from git import InvalidGitRepositoryError, NoSuchPathError, Repo
from redis.asyncio import from_url as redis_from_url
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

_DEFAULT_APP_VERSION = "0.1.0"
_PROCESS_STARTED_AT = datetime.now(timezone.utc)


def get_app_version() -> str:
    try:
        return version("obsidian-wiki-backend")
    except PackageNotFoundError:
        return _DEFAULT_APP_VERSION


def get_process_started_at() -> datetime:
    return _PROCESS_STARTED_AT


async def ping_database(db: AsyncSession) -> tuple[bool, str]:
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        return False, str(exc)
    return True, "Database connection successful"


async def ping_redis() -> tuple[bool, str]:
    client = redis_from_url(settings.redis_url, decode_responses=True)
    try:
        await client.ping()
    except Exception as exc:
        return False, str(exc)
    finally:
        with suppress(Exception):
            await client.aclose()
    return True, "Redis ping successful"


def get_vault_git_status() -> dict[str, object]:
    vault_path = Path(settings.vault_local_path)
    try:
        repo = Repo(vault_path)
    except (InvalidGitRepositoryError, NoSuchPathError):
        return {
            "available": False,
            "branch": None,
            "head": None,
            "dirty": False,
            "has_origin": False,
            "message": "Vault is not a git repository",
        }

    branch: str | None = None
    if not repo.head.is_detached:
        with suppress(TypeError, ValueError):
            branch = repo.active_branch.name

    head = repo.head.commit.hexsha if repo.head.is_valid() else None
    has_origin = "origin" in [remote.name for remote in repo.remotes]
    return {
        "available": True,
        "branch": branch,
        "head": head,
        "dirty": repo.is_dirty(untracked_files=True),
        "has_origin": has_origin,
        "message": None,
    }
