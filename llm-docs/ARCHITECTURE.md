# Architecture

## System Overview

```
Obsidian(Desktop) ◄─git / WebDAV─► Remote ◄─git / WebDAV─► Server(Docker)
Browser(Mobile)   ◄─https─► SvelteKit:3000 → FastAPI:8000 → Postgres:5432
                                                            → Redis:6379
                                               └─► Vault PV (git repo or WebDAV mirror)
```

Single-user self-hosted wiki. An Obsidian vault is kept in sync with a remote (Git **or** WebDAV) and served over the web. The sync backend is selectable per-deployment (see §Sync Backends).

Runtime-mutable values such as sync backend, remote URL, branch, interval, profile credentials, and the server default theme are stored in the DB-backed `app_settings` row and managed from the `/settings` UI. `.env` is bootstrap-only.

Security risks and hardening priorities are tracked separately in `llm-docs/SECURITY.md`.

## Tech Stack Rationale

| Layer | Choice | Why |
|-------|--------|-----|
| Frontend | SvelteKit 5 (runes) | Fast rendering, small bundle, hybrid SSR+SPA |
| Backend | FastAPI (Python 3.12+) | Native async, type hints, mature Git/filesystem ecosystem |
| DB | PostgreSQL 16 | JSONB metadata, FTS + trigram for Korean search |
| Cache | Redis 7 | Search cache, edit locks, sessions. No persistence required |
| Auth | JWT + bcrypt | Single user, initial credentials from Docker env → forced change on first login |
| Sync | Git **or** WebDAV | Git matches Obsidian's native Git plugin; WebDAV matches Obsidian's Remotely Save / built-in WebDAV workflows. Selectable at runtime. |
| Deploy | Docker Compose | Three PVs (db, vault, config) to isolate state |

## Core Data Flows

### Document Read
```
Browser → SvelteKit SSR load → FastAPI GET /api/wiki/doc/{path}
  → Redis cache hit? → return
  → miss → read filesystem + query DB metadata → populate cache → return
  → SvelteKit: render HTML via remark+rehype pipeline
```

### Document Edit / Save
```
Edit start: fetch document payload including base_commit = current HEAD
Ctrl+S → PUT /api/wiki/doc/{path} (content + base_commit)
  → Compare HEAD:
    - Equal → write file → git add+commit → async DB update → optionally enqueue sync-on-save → invalidate cache
    - Changed → check if this specific file was modified
      - Untouched → same as above
      - Modified → attempt 3-way merge
          - Success → save merged result
          - Failure → return 409+diff → frontend keeps the local draft, opens a conflict modal, and lets the user reload the latest version or continue editing
```

### Sync (backend-agnostic loop)
```
Periodic (default 5 min, asyncio task):
  dispatch by settings.sync_backend:
    git    → git fetch → compare local vs remote
              - Local only changed  → push
              - Remote only changed → pull (fast-forward) → incremental index update
              - Both changed        → pull --rebase → per-file 3-way diff on conflict
    webdav → PROPFIND remote tree, compare mtime/etag vs local manifest
              - Remote newer  → download → incremental index update
              - Local  newer  → PUT upload
              - Both  newer   → per-file 3-way merge (same helper as git path) → on failure flag conflict
  .obsidian/ → always "theirs" strategy on either backend
```

Both backends feed the same downstream indexer and conflict handler. Only the transport and change-detection differ.

## Markdown Parsing Pipeline

```
Raw MD → split frontmatter (python-frontmatter) → remark-parse
  → remark-obsidian-wikilink (custom)
  → remark-obsidian-embed (custom, max recursion depth 3)
  → remark-obsidian-callout (custom, collapsible)
  → remark-obsidian-tag (custom, ignores # inside code blocks/URLs)
  → remark-gfm → remark-math
  → rehype-stringify → rehype-katex (SSR) → rehype-raw
  → HTML
```

- Mermaid: rendered client-side (mermaid.js)
- Code highlighting: shiki or rehype-prism-plus

## Wiki Navigation Model

The frontend now uses dedicated document routes (`/wiki/[...path]`) plus one shared target-resolution model across:

- file tree selection
- rendered wikilinks / embeds
- backlinks / frontlinks
- search / quick switcher
- graph node clicks
- tasks / dataview result links

### Canonical Target

Internal links should resolve into one canonical target shape before rendering or navigation:

- `kind`: `note | attachment | heading | block | unresolved | ambiguous`
- `vault_path`: normalized vault-relative path
- `display_text`: alias or fallback label
- `subpath`: optional heading/block target
- `embed`: whether the link came from `![[...]]`

The resolver is aware of the current note path, so relative links, same-folder priority, heading/block targets, and attachment-vs-note disambiguation follow Obsidian-style expectations.

### Routing Direction

- note route: `/wiki/[...path]`
- attachment fetch path: `/api/attachments/{path}` with a thin frontend viewer wrapper

This keeps browser history, deep links, refresh, SSR load, and cross-feature navigation consistent.

### Viewer Dispatch

After resolution, the frontend dispatches by target kind/file type instead of forcing every target through the markdown viewer:

- markdown note → note viewer/editor
- image → inline preview
- PDF → embedded viewer
- audio/video → native media viewer
- unsupported binary → download affordance

The markdown renderer also supports clickable internal links, note/attachment embeds, hover previews, and unresolved-link creation affordances from the shared resolver output.

### Indexing / API Implications

To avoid reparsing and path guessing in many UI components, the backend exposes normalized link targets and reuses indexed metadata where possible:

- `documents` for canonical note paths / titles
- `links` for graph/backlink relationships
- `attachments` for non-markdown targets
- resolver metadata returned with document payloads so the frontend can render and navigate without ad hoc reparsing

Some direct-load/edge-case parity and integration coverage are still tracked in `llm-docs/PROGRESS.md`.

## Workspace UX Model

The app now uses a persistent workspace shell so the main wiki view, settings, graph, tasks, and command palette feel like parts of one system rather than isolated pages.

### App Shell Navigation

The header/sidebar provides stable movement between:

- main wiki screen
- settings
- graph view
- tasks view
- sync/status surfaces

A user always has an explicit way back to the main note view from `/settings/*`, and the app preserves the last-open note path when returning.

### Relationship Surfaces

Document relationships are visible in more than one way:

- backlinks: incoming links to the current note
- frontlinks: outgoing links from the current note
- graph: spatial overview of note connectivity

These all draw from the same canonical link-resolution model so counts and targets stay consistent.

### Sidebar as Workspace Control

The workspace uses an Obsidian-style shell:

- left icon rail for major navigation modes/tools
- file explorer pane for folders/notes and tree actions
- main content area for viewer/editor with optional split preview
- right contextual panel for links/metadata/outline

Within that shell, the sidebar is the primary filesystem/workspace control surface:

- browse folders and notes
- expose current selection clearly
- support drag-and-drop moves for notes/folders
- surface shortcuts such as create, reveal, sort, and link-rewrite-on-move

The file explorer pane includes lightweight toolbar actions similar to desktop note apps:

- new note / new folder
- sort options
- collapse or expand tree
- reveal/open current note in the tree

Drag-and-drop moves enforce collision prevention and can optionally rewrite affected wiki links after the move.

### Command Palette Role

The command palette acts as the global action router for both navigation and note operations. It can trigger page navigation, document actions, sync/system actions, language/theme toggles, and current-note actions from one searchable entry point.

### Sync Status Surface

Sync state is not buried only in settings. The workspace shell exposes a lightweight status pill at all times, with drill-down details for backend, freshness, ahead/behind counts, active job progress, and recent failure/conflict state.

## Search Engine

**Hybrid strategy**: trigram similarity (Korean + English) combined with tsvector full-text search (strong for English).

- Weights: title similarity ×3, FTS rank ×2, content similarity ×1
- PostgreSQL: `pg_trgm` + `unaccent` extensions, Korean FTS uses the `simple` dictionary config
- Redis cache: search results TTL 5 min; file tree keyed by commit hash

## Indexing

- **Full rebuild**: truncate → walk vault `.md`/`.mdx` → extract frontmatter/wikilinks/tags → upsert into DB → invalidate all caches
- **Incremental**: only changed/deleted files from git pull → refresh tag counts → invalidate affected caches

## Authentication Flow

### Initial Setup
Initial account is created from Docker env:
- `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD` (plaintext) → bcrypt-hashed and persisted on first server start
- If a user row already exists in the DB, env values are ignored (restart-safe)

### Forced Change on First Login
- `users` table has a `must_change_credentials: bool` flag
- Initial account is created with `must_change_credentials=true`
- On successful login, if the flag is true the token carries a `must_change=true` claim
- Frontend: when it sees `must_change=true` it redirects to the forced credential-change screen and blocks all other routes
- `POST /api/auth/change-credentials` → updates both username and password → clears the flag → issues new tokens

### `users` table
```sql
CREATE TABLE users (
    id                      SERIAL PRIMARY KEY,
    username                TEXT UNIQUE NOT NULL,
    password_hash           TEXT NOT NULL,
    must_change_credentials BOOLEAN DEFAULT TRUE,
    created_at              TIMESTAMPTZ DEFAULT NOW(),
    updated_at              TIMESTAMPTZ DEFAULT NOW()
);
```

## DB Schema

See `backend/app/db/init.sql`. Main tables:
- `users`: username (UNIQUE), password_hash, must_change_credentials (auth)
- `app_settings`: single-row runtime config for sync backend / interval / git settings / appearance defaults
- `documents`: path (UNIQUE), frontmatter (JSONB), tags (TEXT[]), search_vector (TSVECTOR)
- `links`: source_path → target_path (wikilink graph)
- `tags`: name (UNIQUE) + doc_count
- `attachments`: path, mime_type, size
- `edit_sessions`: doc_path, base_commit, expires_at (conflict prevention)

GIN indexes: search_vector, tags, path (trigram). B-tree: links source/target.

## Sync Backends

Two interchangeable implementations behind a common interface (`app.services.sync.SyncBackend`):

### Git Backend (`services/git_ops.py`)
- Clones the remote on first boot into `$VAULT_LOCAL_PATH`
- Uses gitpython; SSH auth via `/root/.ssh/` bind-mounted key
- Commit on every server-side write; periodic `fetch` + rebase loop
- Conflict resolution: Git merge tooling + 3-way file merge for text; binary `.obsidian/` files resolved "theirs"
- Pros: full history, atomic commits, matches Obsidian Git plugin on desktop
- Cons: requires SSH key management; larger repo on binary-heavy vaults

### WebDAV Backend (`services/sync/webdav_backend.py`)
- Stateless HTTP PROPFIND / GET / PUT against a configured WebDAV endpoint (Nextcloud, Synology, dedicated dav server, etc.)
- Local manifest table (`webdav_manifest`: path, etag, mtime, sha256) tracks last-seen remote state to detect drift and avoid redundant transfers
- Conflict detection: manifest-backed local/remote drift is detected per file; UTF-8 text files reuse the shared 3-way merge helper, while binary/unsupported conflicts still return an explicit conflict response
- Auth: basic (username/password) or bearer token, stored encrypted-at-rest (or as-is if the server enforces TLS only)
- Pros: matches Obsidian's built-in WebDAV / Remotely Save plugin workflow; no Git knowledge needed on mobile
- Cons: no history; race windows wider than git push/pull; depends on server's ETag/mtime quality

### Backend Selection
- `app_settings.sync_backend` column: `'git' | 'webdav' | 'none'`
- The scheduler (see `services/sync_scheduler.py`) picks the backend on start and on settings change (cancel + restart)
- Each auto-sync iteration reads backend status first, then runs `pull` when remote changes exist and `push` when local changes remain
- Switching backends at runtime is allowed but **does not migrate data** — the operator is expected to point both desktop Obsidian and the server at the same remote after the switch. The UI warns accordingly.
- Current implementation status: Git, WebDAV, and None are live end-to-end. WebDAV password encryption, connection testing, manifest-backed status, manual/automatic pull-push flow, and shared text merge are live; richer binary conflict handling remains follow-up work.

## Plugin Compatibility

| Plugin | Strategy | Difficulty |
|--------|----------|-----------|
| Dataview | static `LIST/TABLE FROM "folder"|#tag` → server-side rendered list/table | Medium |
| Excalidraw | `.excalidraw.md` → exported PNG/SVG read-only preview | Medium |
| Tasks | checkbox + due date → `/tasks` aggregated view | Low |
| Callout / MathJax | Implemented directly | Low |

Configuration: `config/obsidian-compat.json`. `.obsidian/plugins/*/data.json` is referenced read-only.

## UI Layout

```
┌─ Header: logo · search (Cmd+K) · sync status · settings ──┐
├─ Sidebar ─┬─ Main Content ──────────┬─ Right Panel ────────┤
│ File tree │ viewer / editor / split │ links · outline · meta│
│ DnD / move│                         │                      │
├───────────┴─────────────────────────┴──────────────────────┤
│ Mobile: sidebar → hamburger, main surface prioritized       │
└────────────────────────────────────────────────────────────┘
```

Dark/light: `prefers-color-scheme` + manual toggle, CSS-variable themes.
