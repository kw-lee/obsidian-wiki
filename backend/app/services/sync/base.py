from __future__ import annotations

from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import SyncStatus, SyncTestResult


class SyncBackend(ABC):
    @abstractmethod
    async def pull(self, db: AsyncSession) -> tuple[str | None, list[str]]:
        raise NotImplementedError

    @abstractmethod
    async def push(self, db: AsyncSession) -> None:
        raise NotImplementedError

    @abstractmethod
    async def status(self, db: AsyncSession) -> SyncStatus:
        raise NotImplementedError

    @abstractmethod
    async def test(self) -> SyncTestResult:
        raise NotImplementedError
