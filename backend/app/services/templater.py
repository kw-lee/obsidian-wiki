from __future__ import annotations

import re
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import vault
from app.services.wiki_links import ParsedWikiLink, load_resolver_catalog, resolve_wikilink

COMMAND_RE = re.compile(r"<%(?P<prefix>[+*_-]?)(?P<body>[\s\S]*?)(?P<suffix>[_-]?)%>")
FRONTMATTER_DOT_RE = re.compile(r"^tp\.frontmatter\.(?P<key>[A-Za-z0-9_-]+)$")
FRONTMATTER_BRACKET_RE = re.compile(
    r"""^tp\.frontmatter\[(?P<quote>['"])(?P<key>.+?)(?P=quote)\]$"""
)
MAX_INCLUDE_DEPTH = 8
DEFAULT_DATE_FORMAT = "YYYY-MM-DD"
DEFAULT_FILE_DATE_FORMAT = "YYYY-MM-DD HH:mm"

MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
MONTH_NAMES_SHORT = [name[:3] for name in MONTH_NAMES]
WEEKDAY_NAMES = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]
WEEKDAY_NAMES_SHORT = [name[:3] for name in WEEKDAY_NAMES]
FORMATTERS: list[tuple[str, Any]] = [
    ("YYYY", lambda dt: f"{dt.year:04d}"),
    ("MMMM", lambda dt: MONTH_NAMES[dt.month - 1]),
    ("MMM", lambda dt: MONTH_NAMES_SHORT[dt.month - 1]),
    ("MM", lambda dt: f"{dt.month:02d}"),
    ("Do", lambda dt: _ordinal(dt.day)),
    ("DD", lambda dt: f"{dt.day:02d}"),
    ("dddd", lambda dt: WEEKDAY_NAMES[dt.weekday()]),
    ("ddd", lambda dt: WEEKDAY_NAMES_SHORT[dt.weekday()]),
    ("HH", lambda dt: f"{dt.hour:02d}"),
    ("hh", lambda dt: f"{_to_12h(dt.hour):02d}"),
    ("mm", lambda dt: f"{dt.minute:02d}"),
    ("ss", lambda dt: f"{dt.second:02d}"),
    ("YY", lambda dt: f"{dt.year % 100:02d}"),
    ("A", lambda dt: "AM" if dt.hour < 12 else "PM"),
    ("a", lambda dt: "am" if dt.hour < 12 else "pm"),
    ("M", lambda dt: str(dt.month)),
    ("D", lambda dt: str(dt.day)),
    ("H", lambda dt: str(dt.hour)),
    ("h", lambda dt: str(_to_12h(dt.hour))),
    ("m", lambda dt: str(dt.minute)),
    ("s", lambda dt: str(dt.second)),
]


@dataclass(frozen=True)
class TemplaterRenderContext:
    note_path: str
    resolve_path: str
    title: str
    content: str
    frontmatter: dict[str, object]
    tags: list[str]
    created_at: datetime | None
    updated_at: datetime | None
    timezone: str


async def render_template_markdown(
    session: AsyncSession,
    source: str,
    context: TemplaterRenderContext,
    *,
    depth: int = 0,
    seen_paths: frozenset[str] | None = None,
    resolver_catalog=None,
) -> str:
    if "<%" not in source or depth > MAX_INCLUDE_DEPTH:
        return source

    if resolver_catalog is None:
        resolver_catalog = await load_resolver_catalog(session)
    seen_paths = seen_paths or frozenset({context.resolve_path})

    parts: list[str] = []
    last_index = 0
    trim_after: str | None = None

    for match in COMMAND_RE.finditer(source):
        literal = source[last_index : match.start()]
        literal = _trim_leading(literal, trim_after)
        trim_after = None

        trim_before = match.group("prefix") if match.group("prefix") in {"_", "-"} else None
        if trim_before:
            _trim_trailing(parts, trim_before)

        parts.append(literal)

        prefix = match.group("prefix")
        expression = match.group("body").strip()
        rendered = await _evaluate_command(
            session,
            expression,
            context,
            depth=depth,
            seen_paths=seen_paths,
            resolver_catalog=resolver_catalog,
            allow_dynamic=prefix != "*",
        )
        parts.append(match.group(0) if rendered is None else _serialize_value(rendered))

        trim_after = match.group("suffix") or None
        last_index = match.end()

    tail = _trim_leading(source[last_index:], trim_after)
    parts.append(tail)
    return "".join(parts)


async def _evaluate_command(
    session: AsyncSession,
    expression: str,
    context: TemplaterRenderContext,
    *,
    depth: int,
    seen_paths: frozenset[str],
    resolver_catalog,
    allow_dynamic: bool,
) -> object | None:
    if not allow_dynamic:
        return None

    normalized = expression.strip()
    if normalized.startswith("await "):
        normalized = normalized[6:].strip()

    return await _resolve_expression(
        session,
        normalized,
        context,
        depth=depth,
        seen_paths=seen_paths,
        resolver_catalog=resolver_catalog,
    )


async def _resolve_expression(
    session: AsyncSession,
    expression: str,
    context: TemplaterRenderContext,
    *,
    depth: int,
    seen_paths: frozenset[str],
    resolver_catalog,
) -> object | None:
    expression = expression.strip()
    if not expression:
        return ""

    concat_parts = _split_top_level(expression, "+")
    if len(concat_parts) > 1:
        resolved_parts: list[str] = []
        for part in concat_parts:
            value = await _resolve_expression(
                session,
                part,
                context,
                depth=depth,
                seen_paths=seen_paths,
                resolver_catalog=resolver_catalog,
            )
            if value is None:
                return None
            resolved_parts.append(_serialize_value(value))
        return "".join(resolved_parts)

    if expression.startswith(("'", '"')) and expression.endswith(("'", '"')):
        return _parse_string_literal(expression)

    if expression in {"true", "false"}:
        return expression == "true"

    if re.fullmatch(r"-?\d+", expression):
        return int(expression)

    direct_value = _resolve_direct_value(expression, context)
    if direct_value is not None:
        return direct_value

    function_call = _parse_function_call(expression)
    if function_call is None:
        return None

    module_name, function_name, arg_source = function_call
    args = _split_arguments(arg_source)
    resolved_args: list[object] = []
    for arg in args:
        value = await _resolve_expression(
            session,
            arg,
            context,
            depth=depth,
            seen_paths=seen_paths,
            resolver_catalog=resolver_catalog,
        )
        if value is None:
            return None
        resolved_args.append(value)

    if module_name == "date":
        return _call_date_function(function_name, resolved_args, context)
    if module_name == "file":
        return await _call_file_function(
            session,
            function_name,
            resolved_args,
            context,
            depth=depth,
            seen_paths=seen_paths,
            resolver_catalog=resolver_catalog,
        )
    return None


def _resolve_direct_value(expression: str, context: TemplaterRenderContext) -> object | None:
    if expression == "tp.file.title":
        return context.title
    if expression == "tp.file.content":
        return context.content
    if expression == "tp.file.tags":
        return context.tags

    frontmatter_dot = FRONTMATTER_DOT_RE.match(expression)
    if frontmatter_dot:
        return context.frontmatter.get(frontmatter_dot.group("key"))

    frontmatter_bracket = FRONTMATTER_BRACKET_RE.match(expression)
    if frontmatter_bracket:
        return context.frontmatter.get(frontmatter_bracket.group("key"))

    return None


def _parse_function_call(expression: str) -> tuple[str, str, str] | None:
    match = re.fullmatch(
        r"tp\.(?P<module>[a-z_]+)\.(?P<name>[A-Za-z_][\w]*)\((?P<args>[\s\S]*)\)", expression
    )
    if not match:
        return None
    return match.group("module"), match.group("name"), match.group("args")


def _split_arguments(source: str) -> list[str]:
    if not source.strip():
        return []
    return _split_top_level(source, ",")


def _split_top_level(source: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    quote: str | None = None
    escape = False

    for char in source:
        if quote is not None:
            current.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == quote:
                quote = None
            continue

        if char in {"'", '"'}:
            quote = char
            current.append(char)
            continue

        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)

        if char == delimiter and depth == 0:
            parts.append("".join(current).strip())
            current = []
            continue

        current.append(char)

    parts.append("".join(current).strip())
    return [part for part in parts if part]


def _parse_string_literal(source: str) -> str:
    quote = source[0]
    body = source[1:-1]
    return body.replace(f"\\{quote}", quote).replace("\\n", "\n").replace("\\t", "\t")


def _call_date_function(
    name: str,
    args: list[object],
    context: TemplaterRenderContext,
) -> str | None:
    if name not in {"now", "tomorrow", "yesterday"}:
        return None

    format_string = str(args[0]) if args else DEFAULT_DATE_FORMAT
    offset = args[1] if len(args) > 1 else None
    reference = args[2] if len(args) > 2 else None
    reference_format = str(args[3]) if len(args) > 3 else format_string

    current = _now_in_timezone(context.timezone)
    if reference is not None:
        parsed_reference = _parse_datetime(str(reference), reference_format, context.timezone)
        if parsed_reference is not None:
            current = parsed_reference

    if name == "tomorrow":
        current += timedelta(days=1)
    elif name == "yesterday":
        current -= timedelta(days=1)

    current = _apply_offset(current, offset)
    return _format_datetime(current, format_string)


async def _call_file_function(
    session: AsyncSession,
    name: str,
    args: list[object],
    context: TemplaterRenderContext,
    *,
    depth: int,
    seen_paths: frozenset[str],
    resolver_catalog,
) -> object | None:
    if name == "folder":
        absolute = bool(args[0]) if args else False
        parent = PurePosixPath(context.note_path).parent
        if absolute:
            return "" if str(parent) == "." else parent.as_posix()
        return "" if str(parent) == "." else parent.name

    if name == "path":
        relative = bool(args[0]) if args else False
        if relative:
            return context.note_path
        return str(vault.resolve(context.note_path))

    if name == "creation_date":
        format_string = str(args[0]) if args else DEFAULT_FILE_DATE_FORMAT
        created_at, _ = _file_datetimes(context)
        return _format_datetime(created_at, format_string)

    if name == "last_modified_date":
        format_string = str(args[0]) if args else DEFAULT_FILE_DATE_FORMAT
        _, updated_at = _file_datetimes(context)
        return _format_datetime(updated_at, format_string)

    if name == "exists" and args:
        try:
            return vault.resolve(str(args[0])).exists()
        except ValueError:
            return False

    if name == "include" and args:
        include_target = str(args[0]).strip()
        resolved = resolve_wikilink(
            ParsedWikiLink(
                raw_target=_strip_wikilink(include_target),
                display_text=include_target,
                embed=False,
            ),
            context.resolve_path,
            resolver_catalog,
        )
        if not resolved.exists or not resolved.vault_path:
            return None
        if resolved.vault_path in seen_paths:
            return None

        included_content = await vault.read_doc(resolved.vault_path)
        included_content = _extract_include_content(
            included_content, resolved.subpath, resolved.kind
        )
        child_context = replace(context, resolve_path=resolved.vault_path)
        return await render_template_markdown(
            session,
            included_content,
            child_context,
            depth=depth + 1,
            seen_paths=seen_paths | {resolved.vault_path},
            resolver_catalog=resolver_catalog,
        )

    return None


def _strip_wikilink(value: str) -> str:
    match = re.fullmatch(r"!? ?\[\[(?P<body>[^\]]+)\]\]", value)
    if not match:
        return value
    target, _, _alias = match.group("body").partition("|")
    return target.strip()


def _extract_include_content(source: str, subpath: str | None, kind: str) -> str:
    if not subpath:
        return source
    if kind == "block":
        return _extract_block(source, subpath) or source
    return _extract_heading_section(source, subpath)


def _extract_block(source: str, block_id: str) -> str | None:
    pattern = re.compile(rf"^(?P<line>.*\^\s*{re.escape(block_id)}\s*)$", re.MULTILINE)
    match = pattern.search(source)
    return match.group("line").strip() if match else None


def _extract_heading_section(source: str, heading: str) -> str:
    lines = source.splitlines()
    target = _normalize_heading(heading)
    start_index = -1

    for index, line in enumerate(lines):
        match = re.match(r"^(#{1,6})\s+(.*)$", line.strip())
        if match and _normalize_heading(match.group(2)) == target:
            start_index = index
            break

    if start_index == -1:
        return source

    section: list[str] = []
    for index in range(start_index, len(lines)):
        trimmed = lines[index].strip()
        if index > start_index and re.match(r"^#{1,6}\s+", trimmed):
            break
        section.append(lines[index])
    return "\n".join(section)


def _normalize_heading(value: str) -> str:
    return (
        value.lower()
        .replace("*", "")
        .replace("_", "")
        .replace("`", "")
        .replace("~", "")
        .replace("[", "")
        .replace("]", "")
        .replace("(", "")
        .replace(")", "")
        .replace("/", "")
        .replace("\\", "")
    )


def _file_datetimes(context: TemplaterRenderContext) -> tuple[datetime, datetime]:
    timezone = _timezone(context.timezone)
    path = vault.resolve(context.note_path)
    stat = path.stat()
    created_ts = getattr(stat, "st_birthtime", stat.st_ctime)
    created_at = datetime.fromtimestamp(created_ts, tz=timezone)
    updated_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone)

    if context.created_at is not None:
        created_at = _coerce_timezone(context.created_at, timezone)
    if context.updated_at is not None:
        updated_at = _coerce_timezone(context.updated_at, timezone)
    return created_at, updated_at


def _now_in_timezone(timezone_name: str) -> datetime:
    return datetime.now(_timezone(timezone_name))


def _timezone(timezone_name: str):
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return UTC


def _coerce_timezone(value: datetime, timezone) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone)
    return value.astimezone(timezone)


def _parse_datetime(value: str, format_string: str, timezone_name: str) -> datetime | None:
    token_patterns = {
        "YYYY": r"(?P<year>\d{4})",
        "YY": r"(?P<year_short>\d{2})",
        "MM": r"(?P<month>\d{2})",
        "M": r"(?P<month>\d{1,2})",
        "DD": r"(?P<day>\d{2})",
        "D": r"(?P<day>\d{1,2})",
        "HH": r"(?P<hour>\d{2})",
        "H": r"(?P<hour>\d{1,2})",
        "mm": r"(?P<minute>\d{2})",
        "m": r"(?P<minute>\d{1,2})",
        "ss": r"(?P<second>\d{2})",
        "s": r"(?P<second>\d{1,2})",
    }
    ordered_tokens = sorted(token_patterns, key=len, reverse=True)

    regex_parts: list[str] = []
    index = 0
    while index < len(format_string):
        matched = False
        for token in ordered_tokens:
            if format_string.startswith(token, index):
                regex_parts.append(token_patterns[token])
                index += len(token)
                matched = True
                break
        if matched:
            continue
        regex_parts.append(re.escape(format_string[index]))
        index += 1

    match = re.fullmatch("".join(regex_parts), value)
    if not match:
        return None

    year = int(
        match.groupdict().get("year") or 2000 + int(match.groupdict().get("year_short") or 0)
    )
    month = int(match.groupdict().get("month") or 1)
    day = int(match.groupdict().get("day") or 1)
    hour = int(match.groupdict().get("hour") or 0)
    minute = int(match.groupdict().get("minute") or 0)
    second = int(match.groupdict().get("second") or 0)
    try:
        return datetime(year, month, day, hour, minute, second, tzinfo=_timezone(timezone_name))
    except ValueError:
        return None


def _apply_offset(value: datetime, offset: object) -> datetime:
    if offset is None:
        return value
    if isinstance(offset, int):
        return value + timedelta(days=offset)
    if isinstance(offset, str):
        match = re.fullmatch(r"(?P<count>[+-]?\d+)\s*(?P<unit>[A-Za-z]+)", offset.strip())
        if match:
            amount = int(match.group("count"))
            unit = match.group("unit").lower()
            if unit in {"d", "day", "days"}:
                return value + timedelta(days=amount)
            if unit in {"w", "week", "weeks"}:
                return value + timedelta(weeks=amount)
            if unit in {"h", "hour", "hours"}:
                return value + timedelta(hours=amount)
            if unit in {"m", "min", "mins", "minute", "minutes"}:
                return value + timedelta(minutes=amount)
    return value


def _format_datetime(value: datetime, format_string: str) -> str:
    parts: list[str] = []
    index = 0
    ordered_tokens = sorted((token for token, _ in FORMATTERS), key=len, reverse=True)
    formatter_map = {token: formatter for token, formatter in FORMATTERS}

    while index < len(format_string):
        matched = False
        for token in ordered_tokens:
            if format_string.startswith(token, index):
                parts.append(str(formatter_map[token](value)))
                index += len(token)
                matched = True
                break
        if matched:
            continue
        parts.append(format_string[index])
        index += 1

    return "".join(parts)


def _serialize_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(_serialize_value(item) for item in value)
    return str(value)


def _trim_trailing(parts: list[str], mode: str) -> None:
    pattern = r"\s+$" if mode == "_" else r"(?:\r?\n)[ \t]*$"
    while parts:
        updated = re.sub(pattern, "", parts[-1])
        if updated == parts[-1]:
            break
        if updated:
            parts[-1] = updated
            break
        parts.pop()


def _trim_leading(value: str, mode: str | None) -> str:
    if mode == "_":
        return re.sub(r"^\s+", "", value)
    if mode == "-":
        return re.sub(r"^[ \t]*\r?\n", "", value, count=1)
    return value


def _ordinal(value: int) -> str:
    suffix = "th" if 10 <= value % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def _to_12h(hour: int) -> int:
    return 12 if hour % 12 == 0 else hour % 12
