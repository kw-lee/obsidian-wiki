# Progress

Tracks implementation progress.

**Status convention**:
- `[ ]` TODO
- `[-]` WIP — include worker initials (e.g. `[-] @KW`)
- `[x]` Done

When multiple people work in parallel, always mark WIP items with an owner to avoid conflicts.

---

## Phase 1: Project Foundation

- [x] CLAUDE.md / docs cleanup
- [x] DB schema — `backend/app/db/init.sql`
- [x] docker-compose.yml + docker-compose.dev.yml
- [x] Dockerfile.frontend (multi-stage: deps→build→prod)
- [x] Dockerfile.backend (base→dev/prod)
- [x] .env.example
- [x] .pre-commit-config.yaml
- [x] .gitignore

## Phase 2: Backend Core

- [x] FastAPI project bootstrap — main.py, config.py, pyproject.toml
- [x] Auth (login / refresh / JWT)
- [x] DB models (SQLAlchemy ORM)
- [x] Alembic migration setup
- [x] Wiki CRUD API — read / save / delete / create
- [x] Git sync (pull / push) — git_ops.py, sync.py
- [x] Conflict detection / 3-way merge — conflict.py
- [x] Search API (FTS + trigram) — search.py
- [x] Attachment serving / upload
- [x] File tree API
- [x] Backlinks / tags / graph API
- [x] Full + incremental indexing
- [x] Unit tests (17 passed) — auth, conflict, vault, health

## Phase 3: Frontend Core

- [x] SvelteKit project bootstrap (adapter-node, vite proxy)
- [x] Login page
- [x] Layout (sidebar + main + right panel)
- [x] File tree component
- [x] Markdown renderer — wikilink / tag plugin (marked)
- [x] Document viewer
- [x] CodeMirror editor — CodeMirror 6 (markdown syntax highlighting, line numbers, Catppuccin theme, ⌘S save)
- [x] Search (Quick Switcher, ⌘K)
- [x] Backlinks panel
- [x] Mobile responsive
- [x] Dark / light theme (Catppuccin palette)

## Phase 4: Advanced Features

- [x] Graph view (d3-force, zoom / drag, node-click navigation)
- [x] Tasks plugin compatibility — checkbox + due date aggregated `/tasks` view
- [x] Dataview compatibility — static `LIST/TABLE FROM "folder"|#tag` renderer
- [x] Templater compatibility — safe subset renderer (`tp.date`, `tp.file`, `tp.frontmatter`, `tp.file.include`) + system toggle
- [x] Excalidraw read-only compatibility — exported PNG/SVG preview for `.excalidraw.md`
- [x] Command palette (⌘P) — new doc, search, graph, git sync, theme toggle
- [x] nginx reverse proxy + HTTPS template
- [x] Alembic async migration setup

## Phase 5: Docker Build / Deploy & Tests

- [x] `.dockerignore` — optimize backend / frontend build context
- [x] `docker-compose.test.yml` — test environment with PostgreSQL + Redis
- [x] `Makefile` — build, up, dev, test, lint, migrate, shell, clean commands
- [x] Backend test expansion — wiki, search, sync, tags, attachments, indexer (6 added)
- [x] Frontend Vitest setup — jsdom, setup, test scripts
- [x] Frontend tests — API client, wiki API, type contracts (3 added)
- [x] `llm-docs/DOCKER.md` — Docker build / deployment guide
- [x] `llm-docs/TESTING.md` — testing guide (backend, frontend, Docker integration)

## Phase 6: Auth Improvements (Docker env seed + forced change)

### Backend
- [x] Add `users` table (SQLAlchemy ORM model)
- [x] `config.py`: add `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD` (drop previous `admin_username`, `admin_password_hash`)
- [x] Server startup: if no user exists, create one from env (bcrypt hash, `must_change_credentials=true`)
- [x] `auth.py` refactor: env comparison → DB lookup
- [x] Include `must_change_credentials` in login response (JWT claim + response field)
- [x] `POST /api/auth/change-credentials` endpoint — username/password change + clear flag + issue new tokens
- [x] Tokens with `must_change=true` can only call the change-credentials endpoint (`get_current_user` dependency)
- [x] Update `.env.example`
- [x] Tests: initial account creation, forced change flow, post-change access (10 passed)

### Frontend
- [x] Forced credential change page (`/auth/setup`)
- [x] Redirect to setup when login response shows `must_change` (block all other routes)
- [x] After change, navigate to main page with new tokens

## Phase 7: Settings Page (Admin Dashboard)

Design: see [`llm-docs/SETTINGS.md`](SETTINGS.md). Move runtime-mutable values from `.env` into the DB and manage them from the web UI.

### Phase 7-1: MVP (Profile + Sync — Git backend)

#### Backend
- [x] Add `AppSettings` model (single-row, `CHECK(id=1)`) with `sync_backend` column (`'git' | 'webdav' | 'none'`)
- [x] Alembic migration — create table + seed from `.env` (`GIT_REMOTE_URL`/`GIT_BRANCH`/`GIT_SYNC_INTERVAL_SECONDS`)
- [x] Sync `init.sql`
- [x] `services/settings.py` — runtime DB settings loader (cache + invalidate)
- [x] Clean up `config.py` — keep bootstrap values only, remove sync-related ones
- [x] `GET/PUT /api/settings/profile` — username/password change + new token issuance
- [x] `GET/PUT /api/settings/sync` — read / update sync settings (Git fields)
- [x] `services/sync_scheduler.py` — asyncio.Task wrapper dispatching to the selected backend, cancel+restart on config change
- [x] Tests — profile change / validation, sync settings persistence, scheduler reload

#### Frontend
- [x] `/settings` layout + tab nav (`+layout.svelte`)
- [x] `/settings/profile` page — verify current password + change username / password
- [x] `/settings/sync` page — backend selector (git/webdav/none), Git form, interval / auto-sync toggle, manual pull/push, status card
- [x] `lib/api/settings.ts` — API wrapper
- [x] Command palette (⌘P) entry: "Open Settings"
- [x] Apply `mustChangeCredentials` guard

#### Cleanup
- [x] Remove sync-related variables from `.env.example` / `.env` + add explanatory comment
- [x] Mention the settings page in the README docs / `llm-docs/ARCHITECTURE.md`

### Phase 7-1b: WebDAV sync backend

Design: see [`llm-docs/SETTINGS.md`](SETTINGS.md) §3.2.c and [`llm-docs/ARCHITECTURE.md`](ARCHITECTURE.md) §Sync Backends.

#### Backend
- [x] `SyncBackend` abstract interface (`pull() / push() / status() / test()`) under `services/sync/base.py`
- [x] Refactor existing git logic into `services/sync/git_backend.py` implementing the interface
- [x] `services/sync/webdav_backend.py` using `httpx` + `aiohttp` / `webdav4`: PROPFIND / GET / PUT
- [x] `webdav_manifest` table (path, etag, mtime, sha256) + incremental diff algorithm
- [x] 3-way merge helper extracted so both backends share it
- [x] Scheduled auto-sync dispatch (`status → pull → push`) for both Git and WebDAV backends
- [x] Fernet-based encryption helper for `webdav_password_enc` (key derived from `JWT_SECRET`)
- [x] `POST /api/settings/sync/test` — validate credentials without persisting
- [x] Extend `AppSettings` schema with WebDAV columns + CHECK constraint
- [x] Tests — WebDAV mock server for pull / push / conflict / test-connection

#### Frontend
- [x] WebDAV form section in `/settings/sync` (URL, username, password, remote root, TLS verify)
- [x] "Test connection" button + result toast
- [x] Warning modal when switching active backend (no data migration)
- [x] Conditional rendering based on `sync_backend` selection

### Phase 7-2: Follow-up

- [x] Vault tab — disk / document / tag stats, rebuild-index button
- [x] Appearance tab — server default theme + theme preset gallery/live preview
- [x] System tab — version, uptime, DB/Redis ping, vault git status
- [x] (Optional) log tail viewer

### Phase 7-3: i18n (Internationalization)

- [x] Introduce an i18n framework in the frontend (e.g. svelte-i18n or similar)
- [x] Extract all user-facing Korean strings in the frontend into locale files (`ko`, `en`)
- [x] Default locale detection from the browser, with a manual switcher in Settings > Appearance
- [x] Translate login / setup / main layout / command palette / settings pages
- [x] Ensure `llm-docs/` stays English-only while the user-facing README docs are maintained in English and Korean

## Phase 8: Security Hardening

Reference: see [`llm-docs/SECURITY.md`](SECURITY.md).

### Audit

- [x] Pre-fix security review completed on 2026-04-13
- [x] SQL injection review completed — no confirmed direct injection path found in current backend routes/services
- [x] Document current security risks and remediation order in `llm-docs/SECURITY.md`

### Planned fixes

- [ ] Move auth away from `localStorage` token storage (`httpOnly` refresh cookie + safer access-token handling)
- [ ] Redact sync secrets from settings responses and log surfaces
- [ ] Add SSRF protections for WebDAV / Git remote targets
- [ ] Enforce write restrictions for `.obsidian/` and `.git/`
- [ ] Harden attachment upload path, filename, and size validation
- [x] Fail startup on placeholder or missing production secrets
- [x] Tighten CORS configuration for production
- [ ] Add auth rate limiting and strengthen password policy
- [ ] Expand negative/security regression tests

## Phase 9: Wiki Navigation & File Viewer Overhaul

Goal: make Obsidian-style links navigable in the web UI, handle note-vs-attachment targets correctly, and move from query-param selection to a stable document route model.

### 9-1. Current-state audit

- [ ] Reproduce broken navigation cases from real vault notes (`[[note]]`, `[[folder/note]]`, `[[note#heading]]`, `[[note|alias]]`, `![[embed]]`, `[[file.pdf]]`)
- [ ] Document current frontend limitations (`/?doc=` selection, `MarkdownView` inline parser assumptions, no canonical target resolver)
- [ ] Document backend data gaps needed for link resolution (path normalization, aliases, attachment metadata reuse, missing-target handling)

### 9-2. Canonical target resolution

- [x] Define a canonical "wiki target" contract shared by frontend/backend: note path, attachment path, heading block, alias text, existence state
- [x] Decide resolution rules compatible with Obsidian: relative path, same-folder priority, extension inference for `.md`, explicit extension for attachments, ambiguous match handling
- [x] Add/update backend response models so a document payload can include resolved outgoing links and attachment targets without reparsing ad hoc in multiple components
- [x] Decide how unresolved links should render (ghost link / create note CTA / plain text fallback)

### 9-3. Route model refactor

- [x] Replace `/?doc=` query-param navigation with a dedicated document route (for example `/wiki/[...path]`) while preserving deep-linking and browser history
- [x] Centralize navigation helpers so file tree, search, graph, backlinks, tasks, and wikilinks all use the same route builder
- [ ] Ensure direct page load / refresh opens the requested document via SSR-friendly load logic
- [x] Define route behavior for non-markdown assets (attachment preview route or download route)

### 9-4. File viewer split

- [x] Separate note viewer concerns from file viewer concerns instead of routing every target through `MarkdownView`
- [x] Add viewer dispatch by file type: markdown note, image, PDF, audio/video, unsupported binary download
- [x] Keep `.excalidraw.md` and future embed-capable note formats on the note-viewer path
- [x] Define empty / error / not-found states for deleted files, broken links, and unauthorized paths

### 9-5. Wikilink and embed rendering

- [x] Replace the current regex-only inline wikilink handling with a structured parser/renderer path that preserves alias, heading, embed, and attachment intent
- [x] Support clickable internal links in rendered markdown, backlinks panel, dataview results, graph nodes, and task list entries through the same resolver
- [x] Add attachment/embed rendering rules for `![[image.png]]`, `![[file.pdf]]`, and note embeds with recursion / safety limits
- [ ] Preserve external links and normal markdown links without changing current behavior

### 9-6. Backend support

- [x] Expose a link-resolution helper/service that can normalize a raw wikilink target against the current note path
- [x] Reuse indexed metadata (`documents`, `links`, `attachments`) to avoid expensive per-request filesystem scans where possible
- [x] Extend indexing if needed to store aliases / headings / attachment metadata required by the resolver
- [x] Return enough metadata for frontend previews without duplicating parsing logic client-side

### 9-7. UX polish

- [x] Add hover states and status styles for resolved, unresolved, and attachment links
- [ ] Preserve scroll/reset behavior intentionally on navigation; decide how heading anchors should scroll into view
- [ ] Add mobile-friendly behavior for opening linked files while keeping sidebar/right-panel state predictable
- [x] Add note creation affordance from unresolved wikilinks if it fits the single-user workflow

### 9-8. Testing and rollout

- [x] Add frontend unit tests for route building, target resolution mapping, and markdown rendering edge cases
- [x] Add backend tests for resolver rules, ambiguous matches, attachment targets, and missing files
- [ ] Add integration tests covering click-through from rendered note → note / PDF / image / broken link
- [ ] Run regression checks for file tree, search modal, graph navigation, backlinks, tasks, and direct URL access

## Phase 10: Workspace UX & UI Improvements

Goal: make the main shell feel like a usable wiki workspace rather than a collection of separate pages, with clear navigation, richer discovery tools, and better file management.

### 10-0. Recommended rollout

#### MVP

- [x] Settings pages always provide an explicit "Back to Wiki" path and preserve the last-open note when returning
- [ ] Introduce the basic Obsidian-like shell layout: left icon rail, file explorer pane, main viewer/editor, right links panel
- [x] Upgrade the right panel from backlinks-only to a combined Links panel with backlinks + frontlinks tabs
- [x] Add a compact global sync indicator in the header/sidebar with idle/running/error/conflict states
- [x] Expand the command palette into a reliable global navigator for open graph, open tasks, open settings, sync now, new note, reveal current note

#### v1.1

- [x] Add file-explorer toolbar actions: new note, new folder, sort, collapse/expand all, reveal current note
- [x] Improve graph view with selection state, current-note highlighting, zoom reset, local-depth controls, and filter basics
- [x] Persist workspace UI state such as expanded folders, sidebar visibility, and selected auxiliary panel tab
- [x] Add note/folder drag-and-drop move for the common happy path with collision prevention and clear invalid-drop feedback
- [x] Improve Links panel with counts, snippets/previews, and better resolved/unresolved/attachment states
- [x] Add document save-conflict UX that preserves the local draft, surfaces backend diff details, and allows reloading the latest version from the editor

#### Later

- [ ] Add advanced left-rail tools such as bookmarks, history/recents, and optional alternate navigation modes
- [x] Add graph hover previews, richer connectivity metrics, and folder subgraph exploration basics
- [ ] Add tag subgraph exploration
- [x] Add optional link rewrite/update flow after note/folder moves
- [ ] Add more advanced command palette actions such as move/rename current note and context-sensitive actions
- [x] Add deeper sync drill-down surfaces in the main workspace
- [ ] Add richer job history/log visibility in the main workspace

### 10-1. Global navigation and app shell

- [ ] Add a clear path from `/settings/*` back to the main wiki screen without relying on browser back only
- [ ] Define global navigation behavior for header, sidebar, graph, tasks, settings, and command palette so page transitions feel consistent
- [ ] Decide which screens are full-page tools versus overlays/panels over the main workspace
- [ ] Preserve selected note / scroll / panel state intentionally when moving between main screen and auxiliary views

### 10-2. Sidebar overhaul

- [ ] Audit current sidebar behavior on desktop/mobile: collapse, resize expectations, folder expansion persistence, selected item visibility
- [ ] Restructure the left workspace to match an Obsidian-like shell: icon rail, file-explorer pane, and contextual right panel
- [ ] Define the sidebar information architecture: vault tree, favorites/recent, tags, sync status shortcut, create note/folder actions
- [x] Add file-explorer toolbar actions such as new note, new folder, sort, collapse/expand all, and reveal current note
- [ ] Improve selected-state, hover, drag target, and empty-folder states
- [ ] Decide which left-rail icons/actions are core for MVP (files, graph, calendar/tasks, bookmarks, recents/history, settings shortcut)
- [x] Add persistence for sidebar open/closed state and expanded folders

### 10-3. Backlinks and frontlinks

- [x] Expand backlinks from a simple list into a real document relationship panel with counts, snippets, and click-through
- [x] Add frontlinks/outgoing links view for the current note using the same canonical resolver as wikilinks
- [x] Distinguish resolved, unresolved, attachment, and ambiguous links in the relationship UI
- [x] Decide whether backlinks/frontlinks live in the right panel, tabs, or a combined "Links" section

### 10-4. Graph view improvements

- [x] Define graph UX goals in implementation: overview, local neighborhood exploration, and quick navigation basics
- [x] Add visual states for degree, selected node, and current note
- [x] Add controls for zoom reset, local graph depth, label visibility, and filtering by folder
- [ ] Add unresolved-link graph state and filtering by tag
- [x] Add physics on/off control
- [x] Define interactions for node click, node hover preview, keyboard escape/reset, and returning to the main note view
- [x] Preserve/share graph control state through the URL for direct reload and deep-linking

### 10-5. Drag-and-drop note/folder move

- [ ] Design drag-and-drop rules for moving notes and folders inside the sidebar tree
- [ ] Define rename/move semantics for paths, including nested children, collision handling, and `.obsidian/` restrictions
- [x] Decide how moved note links should be handled: optional rewrite/update step on move
- [ ] Add confirmation/error UX for invalid drops, overwrite conflicts, and large folder moves

### 10-6. Command palette expansion

- [ ] Audit current command palette commands and group them by navigation, note actions, sync, and settings
- [x] Add document-aware actions such as open current note in edit mode, copy path, reveal in tree, create note, and move/rename
- [x] Add global actions for graph, tasks, settings, sync pull/push, rebuild index, and theme/language toggles where appropriate
- [x] Improve search ranking, keyboard navigation, and action descriptions so the palette can become the main power-user entry point

### 10-7. Sync status visibility

- [x] Define a compact global sync status indicator in the header/sidebar with backend, freshness, and error/conflict state
- [x] Add drill-down details for last sync time, ahead/behind/dirty counts, active job progress, and recent failures
- [ ] Make manual sync actions discoverable from both the main screen and settings without duplicating confusing controls
- [ ] Decide how sync conflict/warning states should surface in the workspace shell and current document view

### 10-8. Testing and rollout

- [ ] Add frontend tests for global navigation helpers, sidebar state, command palette actions, and relationship panels
- [ ] Add integration tests for settings → main navigation, graph → note navigation, and drag-and-drop move flows
- [ ] Add regression coverage for sync status rendering during idle/running/conflict/error states
- [ ] Run manual UX smoke tests on desktop and mobile layouts before implementation is marked complete

### 10-9. Suggested implementation order

- [ ] Step 1: app-shell navigation cleanup (`/settings/*` back-to-main, consistent route helpers, selected-note preservation)
- [ ] Step 2: shell layout refactor (left rail + file explorer pane + right links panel skeleton)
- [ ] Step 3: links panel upgrade (frontlinks + backlinks, shared states, right-panel tabs)
- [ ] Step 4: global sync indicator and command palette expansion
- [ ] Step 5: graph view quality pass
- [ ] Step 6: sidebar toolbar + persisted tree state
- [ ] Step 7: drag-and-drop note/folder move
- [ ] Step 8: advanced polish and non-MVP tools
