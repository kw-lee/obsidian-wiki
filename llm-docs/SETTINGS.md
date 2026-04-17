# Settings Page Design (Settings / Admin Dashboard)

Web-based settings and administration page for the single-user self-hosted wiki. Values currently in `.env` that are reasonable to change at runtime — and operational state that should live in the DB — are managed through this web UI.

- **Route**: `/settings` (tabbed)
- **Access control**: login required. If `must_change_credentials=true`, redirect to `/auth/setup` (existing policy)
- **API prefix**: `/api/settings/*`

---

## 1. Design Principles

1. **`.env` is bootstrap-only**. Only values required to boot the server (`JWT_SECRET`, `DATABASE_URL`, `REDIS_URL`, `INIT_ADMIN_*`, `WEB_PORT`) live in `.env`.
2. **Runtime-mutable values live in the DB**. Git sync interval / remote URL, account info, default theme, etc. are stored in the DB so changes apply without restart.
3. **Mask sensitive data**. SSH keys and password hashes are redacted in responses (`****`) and accepted write-only.
4. **Minimal audit logging**. Full audit logging is overkill for a single user. Record only important changes (credential changes, sync config changes) in a simple `settings_audit` table with timestamp + action.
5. **Immediate effect**. In-memory cached settings on the backend (e.g. sync scheduler interval) trigger a scheduler restart/reload on change.

---

## 2. Page Structure

```
/settings
 ├─ Profile        — account (username, password change)
 ├─ Sync           — backend selection (git | webdav | none) + backend-specific config, manual pull/push, status
 ├─ Vault          — vault path (read-only), disk usage, rebuild-index button
 ├─ Appearance     — default theme (dark/light/system)
 └─ System         — version, health, log tail (optional)
```

Initial scope: **Profile** and **Sync** (with both git and webdav backends). The rest are deferred.

---

## 3. Feature Details

### 3.1 Profile (Account Management)

| Field | UI | Notes |
|-------|----|-------|
| Current username | read-only | |
| New username | input | optional |
| Current password | input (password) | required |
| New password | input (password) | leave blank to skip |
| Confirm new password | input (password) | must match |

**Endpoints**
- `GET  /api/settings/profile` → `{ username, must_change_credentials, created_at, updated_at }`
- `PUT  /api/settings/profile` → body `{ current_password, new_username?, new_password? }` → 200 + new tokens (applied without re-login)

**Validation**
- Wrong `current_password` → `401`.
- `new_password` shorter than minimum (e.g. 4 chars) → `400`.
- Empty `new_username` or one that collides with another account → `409`.
- On new password set: bcrypt rehash, update `updated_at`.
- On success: invalidate the current refresh token and issue a new token pair (force session refresh).

> Keep `/api/auth/change-credentials` exclusive to initial setup (`must_change=true`). Regular changes go through `/api/settings/profile`. Both share the same internal helper.

### 3.2 Sync

Migrate `GIT_REMOTE_URL`, `GIT_BRANCH`, `GIT_SYNC_INTERVAL_SECONDS` from `.env` to the DB, and add WebDAV as an alternative sync backend. The user picks **one** active backend at a time.

**Model** (new `app_settings` table — single-row)

```sql
CREATE TABLE app_settings (
    id                     SMALLINT PRIMARY KEY DEFAULT 1,

    -- Common
    sync_backend           TEXT NOT NULL DEFAULT 'git'
                           CHECK (sync_backend IN ('git', 'webdav', 'none')),
    sync_interval_seconds  INTEGER NOT NULL DEFAULT 300,
    sync_auto_enabled      BOOLEAN NOT NULL DEFAULT TRUE,

    -- Git backend
    git_remote_url         TEXT NOT NULL DEFAULT '',
    git_branch             TEXT NOT NULL DEFAULT 'main',

    -- WebDAV backend
    webdav_url             TEXT NOT NULL DEFAULT '',
    webdav_username        TEXT NOT NULL DEFAULT '',
    webdav_password_enc    TEXT NOT NULL DEFAULT '',  -- encrypted with JWT_SECRET-derived key
    webdav_remote_root     TEXT NOT NULL DEFAULT '/',
    webdav_verify_tls      BOOLEAN NOT NULL DEFAULT TRUE,

    -- Misc
    default_theme          TEXT NOT NULL DEFAULT 'system',
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT single_row CHECK (id = 1)
);
```

Bootstrap: seed via `INSERT ... ON CONFLICT DO NOTHING` in the migration. If the DB is empty on first boot, copy existing `.env` values (one-shot migration).

#### 3.2.a Backend selector (top of tab)
- Radio / segmented control: **Git** · **WebDAV** · **None (disable sync)**
- Switching the active backend shows a warning: "This does not migrate existing data. Point your Obsidian client at the same remote."

#### 3.2.b Git backend form (visible when `sync_backend='git'`)
- Remote URL: text input (e.g. `git@github.com:user/vault.git`)
- Branch: text input (default `main`)
- SSH key status: whether `/root/.ssh/id_*` exists (show path / fingerprint only, never the key itself)

#### 3.2.c WebDAV backend form (visible when `sync_backend='webdav'`)
- Server URL: text input (e.g. `https://cloud.example.com/remote.php/dav/files/me/`)
- Username: text input
- Password / app token: password input (write-only; response redacts as `****` once set)
- Remote root: text input (default `/`; allows scoping to a vault subfolder)
- Verify TLS: toggle (default on; disable only for self-signed + trusted LAN)
- "Test connection" button → performs `PROPFIND` on remote root, reports 200 / auth failure / TLS error

#### 3.2.d Common (always visible)
- Auto-sync: toggle (on/off)
- Interval: number input (seconds, minimum 60)
- Manual triggers: `Pull` / `Push` buttons (reuse `/api/sync/pull|push`; semantics dispatch to the active backend)
- Status card: last sync time, current HEAD SHA (git) or manifest revision (webdav), ahead/behind summary, conflict count

**Endpoints**
- `GET  /api/settings/sync` → current config + status (secrets redacted)
- `PUT  /api/settings/sync` → save config + reload scheduler; accepts only the fields relevant to the selected backend
- `POST /api/settings/sync/test` → validate credentials against the configured backend without persisting
- Existing `POST /api/sync/pull|push`, `GET /api/sync/status` remain but dispatch by active backend

**Scheduler Integration**
- The backend `sync scheduler` reads DB values at startup; on config change, an in-process event (`asyncio.Event`) cancels and restarts it with the newly selected backend.
- If interval=0, `sync_auto_enabled=false`, or `sync_backend='none'`, auto-sync is disabled (manual triggers still work unless backend=`none`).

**Secret handling for WebDAV password**
- Stored as `webdav_password_enc`, encrypted with a key derived from `JWT_SECRET` (Fernet or AES-GCM via `cryptography`).
- Never returned in responses — `GET` returns `has_webdav_password: bool` instead.
- `PUT` accepts a new password only when explicitly provided; empty string means "leave unchanged".

### 3.3 Vault (deferred)

- `/data/vault` disk usage (`du -sh` or Python aggregation)
- Document count, attachment count, tag count
- `Rebuild Index` button (triggers full reindex)

### 3.4 Appearance (deferred)

- Server default theme (used by pre-login pages, etc.). Per-user preference is already in localStorage.

### 3.5 System (deferred)

- Version (`git describe` or `pyproject.toml`), uptime, DB/Redis ping, vault git status
- Optional: tail last N log lines (needs security guardrails)

---

## 4. Backend Implementation Plan

1. **Model / Migration**
   - Add `AppSettings` in `backend/app/db/models.py`
   - Alembic revision: create table + seed row + copy `.env` values if present
   - Keep `init.sql` in sync

2. **Settings Loader Layer**
   - `backend/app/services/settings.py` — loads a singleton dict from the DB; invalidates on change
   - `config.Settings` keeps only bootstrap values; runtime values come from `services.settings`

3. **Router**
   - `backend/app/routers/settings.py` — profile / git sub-routers
   - `app.include_router(settings.router, prefix="/api/settings")`

4. **Scheduler Reload**
   - `backend/app/services/git_scheduler.py` — manages an `asyncio.Task` with a cancel+restart interface
   - Started from `main.py` lifespan

5. **Tests**
   - `test_settings_profile.py` — read / update / password error / username conflict
   - `test_settings_git.py` — save / read / validation (interval lower bound)
   - `test_git_scheduler.py` — cancel + restart on config change

---

## 5. Frontend Implementation Plan

1. **Route Scaffold**
   - `frontend/src/routes/settings/+layout.svelte` — side tab nav
   - `frontend/src/routes/settings/profile/+page.svelte`
   - `frontend/src/routes/settings/sync/+page.svelte` (backend selector + conditional git / webdav forms)

2. **API Wrapper**
   - `frontend/src/lib/api/settings.ts` — `getProfile`, `updateProfile`, `getSyncSettings`, `updateSyncSettings`, `testSyncConnection`

3. **UI**
   - Form validation via plain Svelte runes (`$state`, `$derived`)
   - Toast on save (reuse existing toast store)
   - Git tab: `Pull` / `Push` reuse the same API as the command palette

4. **Command Palette Integration**
   - `⌘P` → add "Open Settings", "Settings: Profile", "Settings: Sync"

5. **Access Guard**
   - Apply the existing `mustChangeCredentials` guard

---

## 6. Security / Validation Checklist

- [ ] Sensitive field changes require `current_password`
- [ ] Invalidate existing refresh tokens after password change (single-user system has no token table, so compare a `password_changed_at` claim instead of rotating `jwt_secret`)
- [ ] Document policy for changing Git remote URL while an existing clone is present (option: warn only on mismatch; actual vault swap happens via CLI)
- [ ] Same warning when switching `sync_backend` between git / webdav (no automatic data migration)
- [ ] Enforce interval minimum of 60 seconds
- [ ] Never include SSH key contents or WebDAV password in any response (`****` or `has_webdav_password: bool` only)
- [ ] WebDAV password encrypted at rest using a `JWT_SECRET`-derived key; rotate on `JWT_SECRET` change (document the re-entry requirement)
- [ ] CSRF: immune now since we use JWT Bearer only; revisit if we switch to cookie auth

---

## 7. Phased Rollout

**Phase 7-1** (MVP — current):
- `AppSettings` model + migration + `.env` → DB seed
- Profile endpoint / page
- Unified Sync endpoint / page with Git backend + dynamic scheduler reload

**Phase 7-1b** (WebDAV backend):
- `SyncBackend` interface + `services/webdav_ops.py` + `webdav_manifest` table
- Sync tab gains backend selector and the WebDAV form
- `/api/settings/sync/test` endpoint
- Encrypted-at-rest password storage using a `JWT_SECRET`-derived key

**Phase 7-2** (follow-up):
- Vault stats / rebuild index
- Appearance, System tabs
- Additional command palette entries

---

## 8. Final `.env` Shape

Removed from `.env`:
- `GIT_REMOTE_URL`
- `GIT_BRANCH`
- `GIT_SYNC_INTERVAL_SECONDS`

Kept (bootstrap only):
- DB / Redis connection info
- `JWT_SECRET`
- `INIT_ADMIN_*`
- `VAULT_LOCAL_PATH`
- Port variables

Add a comment in `.env.example`: "Runtime-mutable values are managed in the `/settings` web UI."
