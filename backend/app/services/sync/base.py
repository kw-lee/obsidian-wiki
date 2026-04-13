from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import SyncStatus, SyncTestResult

ProgressCallback = Callable[..., Awaitable[None]]


async def emit_progress(
    progress: ProgressCallback | None,
    *,
    phase: str,
    message: str | None = None,
    current: int | None = None,
    total: int | None = None,
) -> None:
    if progress is None:
        return
    await progress(
        phase=phase,
        message=message,
        current=current,
        total=total,
    )


class SyncBackend(ABC):
    @abstractmethod
    async def pull(
        self,
        db: AsyncSession,
        *,
        progress: ProgressCallback | None = None,
    ) -> tuple[str | None, list[str]]:
        raise NotImplementedError

    @abstractmethod
    async def push(
        self,
        db: AsyncSession,
        *,
        progress: ProgressCallback | None = None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def bootstrap(
        self,
        db: AsyncSession,
        *,
        strategy: str,
        progress: ProgressCallback | None = None,
    ) -> tuple[str | None, list[str]]:
        raise NotImplementedError

    @abstractmethod
    async def status(self, db: AsyncSession) -> SyncStatus:
        raise NotImplementedError

    @abstractmethod
    async def test(self) -> SyncTestResult:
        raise NotImplementedError
