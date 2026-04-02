from datetime import datetime

from pydantic import BaseModel


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
