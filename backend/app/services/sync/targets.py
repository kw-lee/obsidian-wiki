from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


_SCHEME_URL_PATTERN = re.compile(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s]+")
_SCP_REMOTE_PATTERN = re.compile(
    r"^(?:(?P<user>[^@/\s:]+)@)?(?P<host>\[[^\]]+\]|[^:/\s]+):(?P<path>.+)$"
)
_SENSITIVE_QUERY_KEYS = {"access_token", "auth", "key", "password", "secret", "token"}
_LOCAL_HOSTS = {"localhost", "localhost.localdomain"}
_LOCAL_SUFFIXES = (".internal", ".local", ".localdomain")


@dataclass(frozen=True)
class SyncTargetValidationError(ValueError):
    detail: str

    def __str__(self) -> str:
        return self.detail


def redact_url_secrets(value: str) -> str:
    text = value.strip()
    parsed = urlsplit(text)
    if not parsed.scheme or not parsed.netloc:
        return value

    hostname = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    host = hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"

    query_pairs = parse_qsl(parsed.query, keep_blank_values=True)
    redacted_query = urlencode(
        [
            (key, "[redacted]" if key.lower() in _SENSITIVE_QUERY_KEYS else current)
            for key, current in query_pairs
        ],
        doseq=True,
    )
    return urlunsplit((parsed.scheme, f"{host}{port}", parsed.path, redacted_query, parsed.fragment))


def scrub_secrets(text: str) -> str:
    return _SCHEME_URL_PATTERN.sub(lambda match: redact_url_secrets(match.group(0)), text)


def validate_git_remote_url(value: str, *, allow_private_targets: bool) -> str:
    normalized = value.strip()
    if not normalized:
        return ""

    if _looks_like_local_path(normalized):
        if not allow_private_targets:
            raise SyncTargetValidationError("Local filesystem Git remotes are not allowed")
        return normalized

    host = _extract_git_host(normalized)
    if host is None:
        raise SyncTargetValidationError("Git remote URL is invalid")
    if _has_url_credentials(normalized):
        raise SyncTargetValidationError("Git remote URL must not include embedded credentials")
    _validate_host(host, allow_private_targets=allow_private_targets)
    return normalized


def validate_webdav_url(value: str, *, allow_private_targets: bool) -> str:
    normalized = value.strip()
    if not normalized:
        return ""

    parsed = urlsplit(normalized)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise SyncTargetValidationError("WebDAV URL is invalid")
    if parsed.username or parsed.password:
        raise SyncTargetValidationError("WebDAV URL must not include embedded credentials")
    _validate_host(parsed.hostname or "", allow_private_targets=allow_private_targets)
    return normalized


def _has_url_credentials(value: str) -> bool:
    parsed = urlsplit(value)
    return bool(parsed.scheme and (parsed.username or parsed.password))


def _looks_like_local_path(value: str) -> bool:
    if value.startswith(("/", "./", "../", "~")):
        return True
    if re.match(r"^[A-Za-z]:[\\/]", value):
        return True
    return "://" not in value and _SCP_REMOTE_PATTERN.match(value) is None


def _extract_git_host(value: str) -> str | None:
    parsed = urlsplit(value)
    if parsed.scheme and parsed.hostname:
        return parsed.hostname

    scp_match = _SCP_REMOTE_PATTERN.match(value)
    if scp_match:
        return scp_match.group("host")
    return None


def _validate_host(host: str, *, allow_private_targets: bool) -> None:
    normalized = host.strip().strip("[]").lower()
    if not normalized:
        raise SyncTargetValidationError("Sync target host is invalid")
    if normalized in _LOCAL_HOSTS or normalized.endswith(_LOCAL_SUFFIXES):
        if not allow_private_targets:
            raise SyncTargetValidationError("Private or local sync targets are not allowed")
        return

    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return

    if not address.is_global and not allow_private_targets:
        raise SyncTargetValidationError("Private or local sync targets are not allowed")
