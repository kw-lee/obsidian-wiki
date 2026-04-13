"""Vault filesystem operations — read/write markdown files."""

import hashlib
from pathlib import Path

import aiofiles

from app.config import settings


class VaultPathPolicyError(ValueError):
    """Raised when a vault path violates application-level policy."""


def vault_path() -> Path:
    return Path(settings.vault_local_path)


def _normalized_parts(relative: str) -> tuple[str, tuple[str, ...]]:
    normalized = relative.strip().replace("\\", "/").strip("/")
    if not normalized:
        raise VaultPathPolicyError("Path is required")
    if normalized.startswith("/"):
        raise VaultPathPolicyError("Absolute paths are not allowed")

    parts = tuple(part for part in normalized.split("/") if part)
    if not parts:
        raise VaultPathPolicyError("Path is required")
    if any(part in {".", ".."} for part in parts):
        raise VaultPathPolicyError("Dot path segments are not allowed")
    return normalized, parts


def _validate_policy(parts: tuple[str, ...], *, for_write: bool) -> None:
    if ".git" in parts:
        raise VaultPathPolicyError("Paths inside .git are not allowed")
    if for_write and ".obsidian" in parts:
        raise VaultPathPolicyError(".obsidian is read-only from the web")


def resolve(relative: str, *, for_write: bool = False) -> Path:
    """Resolve a relative vault path, ensuring it stays within the vault."""
    normalized, parts = _normalized_parts(relative)
    _validate_policy(parts, for_write=for_write)

    full = (vault_path() / normalized).resolve()
    if not str(full).startswith(str(vault_path().resolve())):
        raise ValueError("Path traversal detected")
    return full


async def read_doc(relative: str) -> str:
    path = resolve(relative)
    async with aiofiles.open(path, encoding="utf-8") as f:
        return await f.read()


async def write_doc(relative: str, content: str) -> str:
    """Write content and return its sha256 hash."""
    path = resolve(relative, for_write=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(content)
    return hashlib.sha256(content.encode()).hexdigest()


async def create_folder(relative: str) -> str:
    """Create a folder and a hidden placeholder so git can track it."""
    path = resolve(relative, for_write=True)
    path.mkdir(parents=True, exist_ok=False)
    placeholder = path / ".gitkeep"
    async with aiofiles.open(placeholder, "w", encoding="utf-8") as f:
        await f.write("")
    return str(placeholder.relative_to(vault_path()))


async def move_path(source_relative: str, destination_relative: str) -> str:
    source = resolve(source_relative)
    destination = resolve(destination_relative, for_write=True)

    if not source.exists():
        raise FileNotFoundError(source_relative)
    if destination.exists():
        raise FileExistsError(destination_relative)

    destination.parent.mkdir(parents=True, exist_ok=True)
    source.rename(destination)

    if destination.is_dir():
        has_visible_entries = any(not child.name.startswith(".") for child in destination.iterdir())
        if not has_visible_entries:
            placeholder = destination / ".gitkeep"
            async with aiofiles.open(placeholder, "w", encoding="utf-8") as f:
                await f.write("")

    return str(destination.relative_to(vault_path()))


async def delete_doc(relative: str) -> None:
    path = resolve(relative, for_write=True)
    path.unlink(missing_ok=True)


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def build_tree(root: Path | None = None, prefix: str = "") -> list[dict]:
    """Build a nested tree structure of .md files in the vault."""
    root = root or vault_path()
    nodes: list[dict] = []
    try:
        entries = sorted(root.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    except FileNotFoundError:
        return nodes

    for entry in entries:
        if entry.name.startswith("."):
            continue
        rel = f"{prefix}/{entry.name}" if prefix else entry.name
        if entry.is_dir():
            children = build_tree(entry, rel)
            node = {"name": entry.name, "path": rel, "is_dir": True, "children": children}
            nodes.append(node)
        elif entry.suffix.lower() in (".md", ".mdx"):
            nodes.append({"name": entry.name, "path": rel, "is_dir": False, "children": []})
    return nodes
