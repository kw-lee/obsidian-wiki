from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ── Wiki ──────────────────────────────────────────────
class DocMeta(BaseModel):
    path: str
    title: str
    tags: list[str] = []
    frontmatter: dict = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocDetail(DocMeta):
    content: str
    base_commit: str | None = None


class DocSaveRequest(BaseModel):
    content: str
    base_commit: str | None = None


class DocCreateRequest(BaseModel):
    path: str
    content: str = ""


# ── Tree ──────────────────────────────────────────────
class TreeNode(BaseModel):
    name: str
    path: str
    is_dir: bool
    children: list["TreeNode"] = []


# ── Search ────────────────────────────────────────────
class SearchResult(BaseModel):
    path: str
    title: str
    snippet: str
    score: float


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    total: int


# ── Links / Tags / Graph ─────────────────────────────
class BacklinkItem(BaseModel):
    source_path: str
    title: str


class TagInfo(BaseModel):
    name: str
    doc_count: int


class GraphNode(BaseModel):
    id: str
    title: str


class GraphEdge(BaseModel):
    source: str
    target: str


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


# ── Sync ──────────────────────────────────────────────
class SyncStatus(BaseModel):
    last_sync: datetime | None = None
    ahead: int = 0
    behind: int = 0
    dirty: bool = False
    backend: str | None = None
    head: str | None = None
    message: str | None = None


# ── Settings ──────────────────────────────────────────
class ProfileSettingsResponse(BaseModel):
    username: str
    must_change_credentials: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProfileSettingsUpdateRequest(BaseModel):
    current_password: str
    new_username: str | None = None
    new_password: str | None = None


class AuthTokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    must_change_credentials: bool = False


class SyncSettingsResponse(BaseModel):
    sync_backend: Literal["git", "webdav", "none"]
    sync_interval_seconds: int = Field(ge=60)
    sync_auto_enabled: bool = True
    git_remote_url: str = ""
    git_branch: str = "main"
    status: SyncStatus


class SyncSettingsUpdateRequest(BaseModel):
    sync_backend: Literal["git", "webdav", "none"]
    sync_interval_seconds: int = Field(ge=60)
    sync_auto_enabled: bool = True
    git_remote_url: str = ""
    git_branch: str = "main"
