# Obsidian Web Wiki

[한국어 README](README.ko.md)

Self-hosted web wiki for a personal [Obsidian](https://obsidian.md) vault. You keep using the Obsidian desktop app on desktop, and access the same vault from a web browser on mobile or remotely.

## What This Is

- **Single-user** self-hosted wiki for a home server or VPS running Docker.
- **Selectable bidirectional sync**: Obsidian ↔ remote Git or WebDAV ↔ server. Text conflicts attempt a 3-way merge; failures surface as conflicts with a diff.
- **Save conflict handling**: if another change lands first while editing on the web, the app keeps your local draft, opens a conflict diff modal, and lets you reload the latest version or keep editing.
- **Obsidian-compatible parsing**: supports `[[wikilink]]`, `![[embed]]`, `#tag`, YAML frontmatter, callouts, Mermaid, KaTeX, checkboxes, and heading/block targets.
- **Plugin and format compatibility**: aggregated Tasks view (`/tasks`), static Dataview `LIST/TABLE`, a safe Templater subset, and read-only Excalidraw previews.
- **Navigation and file viewing**: dedicated `/wiki/...` document routes, internal link/embed resolution, create-note CTA for unresolved links, and viewers for images, PDFs, audio, video, and other attachments.
- **Workspace UX**: CodeMirror 6 editor, optional split preview, backlinks/frontlinks/outline panel, graph view, global sync indicator, command palette (`Cmd+P`), and Quick Switcher (`Cmd+K`) in an Obsidian-like shell.
- **File management**: explorer toolbar actions (new note/folder, sort, expand/collapse, reveal current note), drag-and-drop moves, and optional wikilink rewriting on move.
- **Admin UI**: forced credential change after first login, `/settings/profile|sync|vault|appearance|system`, server default theme presets, and Korean/English UI switching.
- **Search**: hybrid PostgreSQL `tsvector` + `pg_trgm` search (Korean/English), with graph, link panels, and command palette sharing the same routing model.

## Tech Stack

- **Frontend**: SvelteKit 5 (runes) · TypeScript · CodeMirror 6 · d3
- **Backend**: Python 3.12 · FastAPI (async) · SQLAlchemy 2.0 · pydantic v2
- **DB / Cache**: PostgreSQL 16 · Redis 7
- **Auth**: JWT (15 min access / 7 day refresh) + bcrypt
- **Sync**: Git or WebDAV
- **Deploy**: Docker Compose

Architecture and data flow are documented in [`llm-docs/ARCHITECTURE.md`](llm-docs/ARCHITECTURE.md).

## Quick Start

### Requirements

- Docker + Docker Compose
- A remote store for your vault
- If using the Git backend: a remote Git repository (for example, a private GitHub repo) and an SSH key
- If using the WebDAV backend: a WebDAV URL and account credentials

### Repository Scope

- This repository is intended to stay public-safe: application source, deployment files, and project docs live here.
- Keep your real vault contents, `.env`, SSH keys, and runtime volumes private and out of Git.
- Bundled font assets under [`frontend/static/fonts/`](frontend/static/fonts/) are third-party files and keep their upstream license terms.

### 1. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env`:

```ini
APP_ENV=production
POSTGRES_PASSWORD=...                         # strong password, at least 8 chars
JWT_SECRET=$(openssl rand -hex 32)            # 32+ chars, must be replaced
INIT_ADMIN_USERNAME=admin                     # initial admin account; forced change after first login
INIT_ADMIN_PASSWORD=...                       # strong password, at least 12 chars
CORS_ALLOWED_ORIGINS=https://wiki.example.com # comma-separated if multiple origins
```

Sync is configured after first login from **`/settings/sync`**. There you can choose Git / WebDAV / disabled, run connection tests, trigger manual pull/push, and inspect sync status. If needed, you can still place `GIT_REMOTE_URL`, `GIT_BRANCH`, and `GIT_SYNC_INTERVAL_SECONDS` in `.env` to seed initial Git values into the first `app_settings` row only. Server default theme and language defaults are managed in **`/settings/appearance`**, while status checks and rebuild operations live in **`/settings/vault`** and **`/settings/system`**.

### 2. Run

```bash
make up        # production: start in background
make dev       # development: hot reload + foreground logs
make logs      # view logs
make down      # stop
```

Open **`http://localhost:${WEB_PORT}`** in your browser (default: `80`) and log in with `INIT_ADMIN_*`.

> `BACKEND_PORT` and `FRONTEND_PORT` are for direct debug access without nginx. The real entrypoint is `WEB_PORT`. After login, complete the forced credential-change flow at **`/auth/setup`**, then use **`/settings/profile`**, **`/settings/sync`**, **`/settings/appearance`**, and **`/settings/system`** to review and adjust account, sync, theme, and server state.

### 3. DB Migrations (When Schema Changes)

```bash
make migrate                          # upgrade to latest
make migrate-generate msg="add xyz"   # create a new revision (autogenerate)
```

## Development

```bash
make dev                 # run the full stack with hot reload
make shell-backend       # backend container shell
make shell-frontend      # frontend container shell
make shell-db            # psql
make lint                # ruff + prettier + svelte-check
make lint-fix            # auto-format / auto-fix
```

## Testing

All tests run in Docker (including PostgreSQL + Redis containers).

```bash
make test              # full backend + frontend suite
make test-backend      # backend only (pytest)
make test-frontend     # frontend only (vitest)
make test-clean        # clean test containers / volumes
```

See [`llm-docs/TESTING.md`](llm-docs/TESTING.md) for more details.

## Deployment

Includes an nginx reverse proxy + HTTPS template. See [`llm-docs/DOCKER.md`](llm-docs/DOCKER.md) for build and deployment details.

Three persistent volumes:

- `db_data` — PostgreSQL data
- `vault_data` — Git clone or WebDAV mirror of the vault
- `config_data` — other server configuration

## Keyboard Shortcuts

| Key | Action |
|----|------|
| `Cmd+K` | Quick Switcher (fast document navigation) |
| `Cmd+P` | Command palette (new doc, sync, theme toggle, etc.) |
| `Cmd+S` | Save while editing |

## Documentation

Documentation language policy:

- `README.md` is the default user-facing README and stays in English.
- `README.ko.md` is the Korean user-facing README.
- `llm-docs/` stays English-only for implementation and design references.
- Agent-facing docs are versioned intentionally so human contributors and LLM tools follow the same project rules.
- Third-party dependency and asset notices are tracked in [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md).

- [`AGENTS.md`](AGENTS.md) — project-wide rules (shared by Claude/Codex)
- [`CLAUDE.md`](CLAUDE.md) — pointer doc for Claude
- [`CODEX.md`](CODEX.md) — pointer doc for Codex
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) — direct dependency versions and third-party license notes
- [`llm-docs/ARCHITECTURE.md`](llm-docs/ARCHITECTURE.md) — system architecture / technical decisions
- [`llm-docs/CONVENTIONS.md`](llm-docs/CONVENTIONS.md) — code style / Git / CI
- [`llm-docs/SETTINGS.md`](llm-docs/SETTINGS.md) — admin settings UI / runtime settings
- [`llm-docs/SECURITY.md`](llm-docs/SECURITY.md) — security review / hardening priorities
- [`llm-docs/DOCKER.md`](llm-docs/DOCKER.md) — Docker build and deployment
- [`llm-docs/TESTING.md`](llm-docs/TESTING.md) — testing guide
- [`llm-docs/PROGRESS.md`](llm-docs/PROGRESS.md) — implementation progress

## Upstream Dependencies & Licenses

- Key upstream projects used directly include SvelteKit, Svelte, CodeMirror, d3, KaTeX, Marked, FastAPI, Pydantic, SQLAlchemy, Alembic, Uvicorn, HTTPX, and GitPython.
- The direct dependencies reviewed from the lockfiles are permissively licensed (`MIT`, `Apache-2.0`, `BSD-3-Clause`, `ISC`). No direct dependency reviewed in this pass used `GPL`, `LGPL`, or `AGPL`.
- Bundled font assets under [`frontend/static/fonts/`](frontend/static/fonts/) are licensed separately from the repository root license.
- See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) for exact direct dependency versions and license notes.

## License

The project source code and project-authored docs are licensed under the [GNU General Public License v3.0 only](LICENSE) (`GPL-3.0-only`).

Bundled third-party font assets under [`frontend/static/fonts/`](frontend/static/fonts/) are not relicensed under the repository root `GPL-3.0-only` notice and remain under their upstream terms. See [`frontend/static/fonts/README.md`](frontend/static/fonts/README.md).
