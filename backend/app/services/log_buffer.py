from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone

_MAX_LOG_ENTRIES = 200
_LOG_ENTRIES: deque[dict[str, object]] = deque(maxlen=_MAX_LOG_ENTRIES)
_HANDLER: logging.Handler | None = None


class _InMemoryLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        _LOG_ENTRIES.append(
            {
                "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
        )


def install_log_buffer() -> None:
    global _HANDLER
    if _HANDLER is not None:
        return

    _HANDLER = _InMemoryLogHandler()
    _HANDLER.setLevel(logging.INFO)
    logging.getLogger().addHandler(_HANDLER)


def get_recent_logs(limit: int = 50) -> list[dict[str, object]]:
    if limit <= 0:
        return []
    return list(reversed(list(_LOG_ENTRIES)[-limit:]))


install_log_buffer()
