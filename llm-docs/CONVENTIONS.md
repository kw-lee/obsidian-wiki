# Conventions

## Code Style

### Python (Backend)
- `ruff format` + `ruff check` (integrated lint + format)
- Type hints required on every function signature
- Async-first; use `aiofiles` for file I/O
- pydantic v2 models for request/response schemas
- SQLAlchemy 2.0 style (`mapped_column`, async session)
- Errors: `FastAPI HTTPException`

### TypeScript (Frontend)
- strict mode
- prettier + prettier-plugin-svelte
- SvelteKit 5 runes (`$state`, `$derived`, `$effect`)
- Errors: toast notifications

### Environment Variables
- `.env` file based, with template in `.env.example`
- Managed in `backend/app/config.py` via pydantic-settings
- Required bootstrap values: `POSTGRES_PASSWORD`, `JWT_SECRET`, `INIT_ADMIN_USERNAME`, `INIT_ADMIN_PASSWORD`
- Optional bootstrap/dev values: ports (3000/8000/5432/6379), `VAULT_LOCAL_PATH`, Git seed values for the first `app_settings` row
- Runtime-mutable sync/profile/appearance settings live in the DB-backed `app_settings` row, not in `.env`

---

## Git

### Branches & Commits
- Commit per phase or per meaningful feature unit
- Verify `ruff check` / `svelte-check` / lints pass before committing
- Update `README.md` and `README.ko.md` in the same commit when a user-visible feature, setup flow, supported integration, or UX behavior changes
- Update `llm-docs/PROGRESS.md` with completed items in the same commit
- Update the relevant design/ops docs in the same commit when behavior changes their scope:
  - `llm-docs/ARCHITECTURE.md` for routing, data flow, sync, storage, or UI-shell behavior
  - `llm-docs/DOCKER.md` for deployment/runtime changes
  - `llm-docs/TESTING.md` for test workflow changes
  - `llm-docs/SETTINGS.md` / `llm-docs/SECURITY.md` when admin or security behavior changes

### Commit Messages
Conventional commits: `feat|fix|docs|style|refactor|test|chore|build|ci|perf`
```
feat(wiki): add wikilink parser
fix(sync): handle index.lock stale file
```

### Git Hooks (pre-commit)
`.pre-commit-config.yaml`:
- Python: ruff (--fix) + ruff-format
- Frontend: svelte-check (--threshold error) + prettier
- commit-msg: enforce conventional commits format

### Recommended vault `.gitignore`
`.obsidian/workspace.json`, `workspace-mobile.json`, `appearance.json`, `hotkeys.json`, `.DS_Store`

---

## Docker

- **Frontend**: multi-stage (deps → dev → build → production). The `dev` target is used by compose.dev.yml
- **Backend**: python:3.12-slim with git + openssh-client. uvicorn workers=2 (prod)
- **DB**: postgres:16-alpine; `init.sql` enables pg_trgm / unaccent
- **Redis**: 7-alpine, maxmemory 256mb, allkeys-lru, no persistence
- **Dev override**: Vite HMR (24678), source bind mount, vault/config as local bind mounts
- Every service has a healthcheck; backend depends on db being healthy

---

## CI Checks

```bash
# Backend
ruff check . && ruff format --check . && pytest -x

# Frontend
npx svelte-check --threshold error && npx prettier --check 'src/**/*.{svelte,ts,js}' && npm test
```

---

## Initial Setup

1. Copy `.env.example` → `.env`, auto-generate `JWT_SECRET` (`openssl rand -hex 32`)
2. Set `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD` (plaintext; server bcrypt-hashes on first start)
3. If using the Git backend, install an SSH key (`config/ssh/id_ed25519`) and register it as a deploy key with write access
4. Start the stack with `docker compose up -d`, then configure the runtime sync backend from `/settings/sync`
5. On first login, complete the forced username/password change screen

---

## Deployment Checklist

- [ ] Replace all `changeme` values in `.env`; `JWT_SECRET` must be 32+ bytes
- [ ] If using Git, SSH public key → GitHub Deploy Key (write access)
- [ ] `docker compose up -d` → all services healthy
- [ ] Run initial indexing: `docker compose exec backend python -m app.cli reindex`
- [ ] E2E smoke test: login / view / edit / sync
- [ ] HTTPS: nginx reverse proxy + Let's Encrypt
