from __future__ import annotations

import asyncio
import time
from collections import deque
from dataclasses import dataclass

from fastapi import HTTPException, Request, status
from redis.asyncio import Redis
from redis.asyncio import from_url as redis_from_url

from app.config import settings


@dataclass(frozen=True)
class RateLimitRule:
    bucket: str
    limit: int = settings.auth_rate_limit_max_attempts
    window_seconds: int = settings.auth_rate_limit_window_seconds


class _MemoryRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = {}
        self._lock = asyncio.Lock()

    async def count(self, key: str, *, window_seconds: int) -> int:
        now = time.monotonic()
        async with self._lock:
            queue = self._events.setdefault(key, deque())
            cutoff = now - window_seconds
            while queue and queue[0] <= cutoff:
                queue.popleft()
            return len(queue)

    async def hit(self, key: str, *, window_seconds: int) -> int:
        now = time.monotonic()
        async with self._lock:
            queue = self._events.setdefault(key, deque())
            cutoff = now - window_seconds
            while queue and queue[0] <= cutoff:
                queue.popleft()
            queue.append(now)
            return len(queue)

    async def clear(self, key: str) -> None:
        async with self._lock:
            self._events.pop(key, None)


_memory_limiter = _MemoryRateLimiter()
_redis_client: Redis | None = None


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    if forwarded:
        return forwarded
    client = request.client
    return client.host if client else "unknown"


def build_identifier(request: Request, *parts: str | int | None) -> str:
    raw = [client_ip(request), *(str(part) for part in parts if part not in (None, ""))]
    return ":".join(_normalize_identifier(part) for part in raw if part)


def _normalize_identifier(value: str) -> str:
    normalized = value.strip().lower()
    sanitized = "".join(
        ch if ch.isalnum() or ch in {"-", "_", ".", "@"} else "-" for ch in normalized
    )
    return sanitized or "anonymous"


def _key(rule: RateLimitRule, identifier: str) -> str:
    return f"rate-limit:{rule.bucket}:{identifier}"


def _get_redis_client() -> Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis_from_url(settings.redis_url, decode_responses=True)
    return _redis_client


async def _redis_count(key: str) -> int:
    raw = await _get_redis_client().get(key)
    return int(raw or 0)


async def _redis_hit(key: str, *, window_seconds: int) -> int:
    client = _get_redis_client()
    current = await client.incr(key)
    if current == 1:
        await client.expire(key, window_seconds)
    return int(current)


async def _redis_clear(key: str) -> None:
    await _get_redis_client().delete(key)


async def current_failures(rule: RateLimitRule, identifier: str) -> int:
    key = _key(rule, identifier)
    try:
        return await _redis_count(key)
    except Exception:
        return await _memory_limiter.count(key, window_seconds=rule.window_seconds)


async def record_failure(rule: RateLimitRule, identifier: str) -> int:
    key = _key(rule, identifier)
    try:
        return await _redis_hit(key, window_seconds=rule.window_seconds)
    except Exception:
        return await _memory_limiter.hit(key, window_seconds=rule.window_seconds)


async def clear_failures(rule: RateLimitRule, identifier: str) -> None:
    key = _key(rule, identifier)
    try:
        await _redis_clear(key)
    except Exception:
        await _memory_limiter.clear(key)


async def ensure_not_limited(rule: RateLimitRule, identifier: str) -> None:
    failures = await current_failures(rule, identifier)
    if failures >= rule.limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Please wait and try again.",
        )
