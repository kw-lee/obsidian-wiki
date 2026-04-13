from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app.config import settings

_TASK_RE = re.compile(r"^\s*[-*+]\s+\[(?P<state>[ xX])\]\s+(?P<body>.+?)\s*$")
_DUE_RE = re.compile(r"(?:📅|due::)\s*(?P<date>\d{4}-\d{2}-\d{2})")


@dataclass(frozen=True)
class ParsedTask:
    path: str
    line_number: int
    text: str
    completed: bool
    due_date: date | None
    priority: str | None


def _parse_due_date(body: str) -> date | None:
    match = _DUE_RE.search(body)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group("date"))
    except ValueError:
        return None


def _parse_priority(body: str) -> str | None:
    if "⏫" in body:
        return "high"
    if "🔼" in body:
        return "medium"
    if "🔽" in body:
        return "low"
    return None


def _normalize_text(body: str) -> str:
    body = _DUE_RE.sub("", body)
    body = body.replace("⏫", "").replace("🔼", "").replace("🔽", "")
    return re.sub(r"\s+", " ", body).strip()


def extract_tasks_from_content(path: str, content: str) -> list[ParsedTask]:
    tasks: list[ParsedTask] = []
    for line_number, line in enumerate(content.splitlines(), start=1):
        match = _TASK_RE.match(line)
        if not match:
            continue
        body = match.group("body")
        tasks.append(
            ParsedTask(
                path=path,
                line_number=line_number,
                text=_normalize_text(body),
                completed=match.group("state").lower() == "x",
                due_date=_parse_due_date(body),
                priority=_parse_priority(body),
            )
        )
    return tasks


def list_vault_tasks(*, include_done: bool = False) -> list[ParsedTask]:
    vault = Path(settings.vault_local_path)
    tasks: list[ParsedTask] = []
    if not vault.exists():
        return tasks

    for md_file in vault.rglob("*.md"):
        if md_file.name.startswith(".") or ".obsidian" in md_file.parts:
            continue
        relative_path = str(md_file.relative_to(vault))
        content = md_file.read_text(encoding="utf-8", errors="replace")
        tasks.extend(extract_tasks_from_content(relative_path, content))

    if not include_done:
        tasks = [task for task in tasks if not task.completed]

    return sorted(
        tasks,
        key=lambda task: (
            task.completed,
            task.due_date is None,
            task.due_date or date.max,
            task.path,
            task.line_number,
        ),
    )
