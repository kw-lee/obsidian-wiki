from datetime import date, datetime
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
    rendered_content: str | None = None
    base_commit: str | None = None
    outgoing_links: list["ResolvedWikiLink"] = []


class DocSaveRequest(BaseModel):
    content: str
    base_commit: str | None = None


class DocCreateRequest(BaseModel):
    path: str
    content: str = ""


class FolderCreateRequest(BaseModel):
    path: str


class FolderCreateResponse(BaseModel):
    path: str


class MovePathRequest(BaseModel):
    source_path: str
    destination_path: str
    rewrite_links: bool = False


class MovePathResponse(BaseModel):
    path: str
    rewrite_links: bool = False
    rewritten_paths: list[str] = []
    rewritten_links: int = 0


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
    snippet: str | None = None
    mention_count: int = 1


class ResolvedWikiLink(BaseModel):
    raw_target: str
    display_text: str
    kind: Literal["note", "attachment", "heading", "block", "unresolved", "ambiguous"]
    vault_path: str | None = None
    subpath: str | None = None
    embed: bool = False
    exists: bool = False
    ambiguous_paths: list[str] = []
    mime_type: str | None = None


class TagInfo(BaseModel):
    name: str
    doc_count: int


class GraphNode(BaseModel):
    id: str
    title: str
    tags: list[str] = []
    kind: Literal["note", "unresolved", "attachment", "ambiguous"] = "note"
    candidate_paths: list[str] = []
    mime_type: str | None = None


class GraphEdge(BaseModel):
    source: str
    target: str


class GraphData(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class TaskItem(BaseModel):
    path: str
    line_number: int
    text: str
    completed: bool
    due_date: date | None = None
    priority: Literal["low", "medium", "high"] | None = None


class TaskListResponse(BaseModel):
    tasks: list[TaskItem]


class DataviewQueryRequest(BaseModel):
    query: str


class DataviewCell(BaseModel):
    value: str
    link_path: str | None = None


class DataviewRow(BaseModel):
    cells: list[DataviewCell]


class DataviewQueryResponse(BaseModel):
    kind: Literal["list", "table"]
    columns: list[str]
    rows: list[DataviewRow]


class DataviewLinkSnapshot(BaseModel):
    path: str
    display: str


class DataviewPageFileSnapshot(BaseModel):
    name: str
    path: str
    folder: str
    ext: str
    link: DataviewLinkSnapshot
    ctime: datetime | None = None
    mtime: datetime | None = None
    tags: list[str] = []
    inlinks: list[DataviewLinkSnapshot] = []
    outlinks: list[DataviewLinkSnapshot] = []
    tasks: list[TaskItem] = []


class DataviewPageSnapshot(BaseModel):
    path: str
    title: str
    tags: list[str] = []
    frontmatter: dict = {}
    file: DataviewPageFileSnapshot


class DataviewContextResponse(BaseModel):
    pages: list[DataviewPageSnapshot]


# ── Sync ──────────────────────────────────────────────
class SyncStatus(BaseModel):
    last_sync: datetime | None = None
    timezone: str | None = None
    ahead: int = 0
    behind: int = 0
    dirty: bool = False
    backend: str | None = None
    head: str | None = None
    message: str | None = None


class SyncJobResponse(BaseModel):
    id: str
    action: Literal["pull", "push", "bootstrap", "sync"]
    source: Literal["manual", "automatic"]
    backend: str | None = None
    status: Literal["queued", "running", "succeeded", "failed", "conflict"]
    phase: str | None = None
    message: str | None = None
    current: int = 0
    total: int = 0
    progress_percent: int | None = None
    bootstrap_strategy: Literal["remote", "local"] | None = None
    head: str | None = None
    changed_files: int = 0
    started_at: datetime | None = None
    updated_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None


class SyncJobStartRequest(BaseModel):
    action: Literal["pull", "push", "bootstrap", "sync"]
    bootstrap_strategy: Literal["remote", "local"] | None = None


# ── Settings ──────────────────────────────────────────
class ProfileSettingsResponse(BaseModel):
    username: str
    git_display_name: str
    git_email: str
    must_change_credentials: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProfileSettingsUpdateRequest(BaseModel):
    current_password: str
    new_username: str | None = None
    git_display_name: str
    git_email: str
    new_password: str | None = None


class ProfileAuditEntry(BaseModel):
    created_at: datetime
    action: str
    path: str
    commit_sha: str | None = None
    username: str
    git_display_name: str
    git_email: str


class ProfileAuditResponse(BaseModel):
    entries: list[ProfileAuditEntry]


class SystemAuditResponse(BaseModel):
    entries: list[ProfileAuditEntry]


class AuthTokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    must_change_credentials: bool = False


class SyncSettingsResponse(BaseModel):
    sync_backend: Literal["git", "webdav", "none"]
    sync_interval_seconds: int = Field(ge=60)
    sync_auto_enabled: bool = True
    sync_mode: Literal["bidirectional", "pull-only", "push-only"] = "bidirectional"
    sync_run_on_startup: bool = False
    sync_startup_delay_seconds: int = Field(default=10, ge=0)
    sync_on_save: bool = False
    git_remote_url: str = ""
    git_branch: str = "main"
    webdav_url: str = ""
    webdav_username: str = ""
    webdav_remote_root: str = "/"
    webdav_verify_tls: bool = True
    webdav_obsidian_policy: Literal["remote-only", "ignore", "include"] = "remote-only"
    has_webdav_password: bool = False
    status: SyncStatus


class SyncSettingsUpdateRequest(BaseModel):
    sync_backend: Literal["git", "webdav", "none"]
    sync_interval_seconds: int = Field(ge=60)
    sync_auto_enabled: bool = True
    sync_mode: Literal["bidirectional", "pull-only", "push-only"] = "bidirectional"
    sync_run_on_startup: bool = False
    sync_startup_delay_seconds: int = Field(default=10, ge=0)
    sync_on_save: bool = False
    git_remote_url: str = ""
    git_branch: str = "main"
    webdav_url: str = ""
    webdav_username: str = ""
    webdav_password: str | None = None
    webdav_remote_root: str = "/"
    webdav_verify_tls: bool = True
    webdav_obsidian_policy: Literal["remote-only", "ignore", "include"] = "remote-only"


class SyncSettingsTestRequest(BaseModel):
    sync_backend: Literal["git", "webdav", "none"]
    git_remote_url: str = ""
    git_branch: str = "main"
    webdav_url: str = ""
    webdav_username: str = ""
    webdav_password: str | None = None
    webdav_remote_root: str = "/"
    webdav_verify_tls: bool = True


class SyncTestResult(BaseModel):
    ok: bool
    backend: str
    detail: str


class VaultSettingsResponse(BaseModel):
    vault_path: str
    disk_usage_bytes: int
    document_count: int
    attachment_count: int
    tag_count: int


class RebuildIndexResponse(BaseModel):
    indexed_documents: int


class AppearanceSettingsResponse(BaseModel):
    default_theme: Literal["light", "dark", "system"]
    theme_preset: Literal["obsidian", "graphite", "dawn", "forest"]
    ui_font: Literal["system", "nanum-square", "nanum-square-ac"]
    editor_font: Literal["system", "d2coding"]


class AppearanceSettingsUpdateRequest(BaseModel):
    default_theme: Literal["light", "dark", "system"]
    theme_preset: Literal["obsidian", "graphite", "dawn", "forest"]
    ui_font: Literal["system", "nanum-square", "nanum-square-ac"]
    editor_font: Literal["system", "d2coding"]


class PluginSettingsResponse(BaseModel):
    dataview_enabled: bool = True
    folder_note_enabled: bool = False
    templater_enabled: bool = False


class PluginSettingsUpdateRequest(BaseModel):
    dataview_enabled: bool = True
    folder_note_enabled: bool = False
    templater_enabled: bool = False


class SystemDependencyStatus(BaseModel):
    ok: bool
    detail: str


class VaultGitStatus(BaseModel):
    available: bool
    branch: str | None = None
    head: str | None = None
    dirty: bool = False
    has_origin: bool = False
    message: str | None = None


class SystemSettingsResponse(BaseModel):
    version: str
    started_at: datetime
    timezone: str
    editor_split_preview_enabled: bool = False
    uptime_seconds: int = Field(ge=0)
    sync_backend: Literal["git", "webdav", "none"]
    sync_auto_enabled: bool
    sync_status: SyncStatus
    database: SystemDependencyStatus
    redis: SystemDependencyStatus
    vault_git: VaultGitStatus


class SystemLogEntry(BaseModel):
    timestamp: datetime
    level: str
    logger: str
    message: str


class SystemSettingsUpdateRequest(BaseModel):
    timezone: str
    editor_split_preview_enabled: bool = False


class SystemLogsResponse(BaseModel):
    entries: list[SystemLogEntry]


DocDetail.model_rebuild()
TreeNode.model_rebuild()
