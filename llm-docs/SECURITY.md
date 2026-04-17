# Security Review

Security review snapshot taken on 2026-04-13 and updated on 2026-04-17 after the v0.0.1 hardening pass.

This document tracks:
- the current risk assessment of the codebase,
- issues that should be fixed before wider deployment or public release,
- items that were explicitly reviewed and are currently considered acceptable.

---

## Audit Summary

### No direct SQL injection found in the current code

Reviewed paths:
- `backend/app/routers/search.py`
- `backend/app/services/dataview.py`
- `backend/app/services/indexer.py`
- `backend/app/routers/wiki.py`
- `backend/app/routers/settings.py`

Current assessment:
- ORM-based queries use SQLAlchemy expressions rather than string concatenation.
- Raw SQL usage goes through bound parameters (`text(...), {"q": q, "limit": limit}`) rather than interpolating user input directly.
- The Dataview query parser is a constrained whitelist parser and does not translate user input into SQL.

Conclusion:
- No confirmed SQL injection path was found during this review.
- Future raw SQL additions should keep using bound parameters only.

### Higher-risk findings were elsewhere

The largest current risks are:
- token handling in the browser,
- sync secret exposure,
- SSRF-capable remote URL configuration,
- weak validation around filesystem write paths,
- insecure-by-default runtime/deployment settings.

---

## v0.0.1 Hardening Landed

The following release-blocking items are now implemented:

- Refresh tokens moved out of `localStorage` into an `httpOnly` auth cookie; frontend JavaScript only handles the short-lived access token.
- Credential-bearing sync URLs are rejected on write and redacted in settings/log responses.
- Git/WebDAV sync targets now reject private, loopback, link-local, and credential-bearing URLs unless explicitly allowed by config.
- Vault path policy blocks `.git/` access and `.obsidian/` web writes; attachment uploads validate folder, filename, and size.
- Production startup fails on placeholder secrets; CORS is explicit in production.
- Auth endpoints and profile credential changes are rate-limited; new passwords must meet a stronger policy.
- Security regression coverage now includes cookie transport, sync target validation, path policy, upload validation, and auth throttling.

## Findings

### 1. Browser tokens are no longer persisted in `localStorage`

Severity: Mitigated for v0.0.1

Current behavior:
- refresh tokens are set in an `httpOnly` cookie and are not readable by frontend JavaScript
- access tokens are kept in browser session storage and rotated through the refresh endpoint
- XSS impact is reduced because the long-lived refresh token is no longer script-readable

Residual risk:
- access tokens are still script-readable for the lifetime of the browser tab
- full cookie-based auth plus CSRF protection would be a further hardening step if the app broadens beyond the current single-user scope

Implemented fix:
- refresh token moved to an `httpOnly`, `Secure`-in-production, `SameSite=Lax` cookie
- frontend storage no longer uses `localStorage` for auth tokens

### 2. Sync configuration secret exposure is mitigated

Severity: High

Current behavior:
- sync settings responses redact credential-bearing URL components
- settings writes reject embedded credentials in Git/WebDAV URLs
- buffered system logs scrub URL credentials before they reach the UI

Why this matters:
- secrets become visible in the UI, browser devtools, and possibly system log output

Status:
- implemented for v0.0.1

### 3. WebDAV and Git remote SSRF pivots are guarded

Severity: High

Current behavior:
- sync target validation restricts allowed schemes and rejects localhost, loopback, link-local, and private IP ranges by default
- a trusted self-hosted deployment can opt out explicitly through `ALLOW_PRIVATE_SYNC_TARGETS`

Why this matters:
- an attacker with authenticated access, or with stolen tokens, could make the server connect to internal services or metadata endpoints

Status:
- implemented for v0.0.1

### 4. Filesystem write guards for `.obsidian/`, `.git/`, and uploads are in place

Severity: High

Current behavior:
- vault path resolution blocks `.git/` access and `.obsidian/` writes from web routes
- attachment uploads validate folder paths, filenames, and hidden targets before writing
- traversal-style input is mapped to `400`/`404` client errors rather than uncaught server failures

Why this matters:
- `.obsidian/` can be modified from the web despite the architecture rule saying it is read-only
- `.git/` contents inside the vault can potentially be overwritten via upload paths
- this is both a security and integrity risk

Status:
- implemented for v0.0.1

### 5. CORS is wide open

Severity: Medium

Current behavior:
- backend CORS allows all origins, methods, and headers

Why this matters:
- it expands the browser attack surface unnecessarily
- it is especially risky if auth later moves to cookies

Recommended fix:
- make allowed origins explicit from configuration
- keep production defaults tight

### 6. Runtime defaults are insecure if `.env` is weak or missing

Severity: Medium

Current behavior:
- the backend can boot with placeholder defaults such as `changeme`

Why this matters:
- accidental deployment with weak secrets becomes possible
- startup should fail fast instead of silently accepting insecure values

Recommended fix:
- fail startup when `JWT_SECRET`, `POSTGRES_PASSWORD`, or bootstrap credentials are missing or still set to placeholder values
- document exact minimum secret requirements

### 7. Auth endpoints now have brute-force protection

Severity: Medium

Current behavior:
- failed attempts on `/api/auth/login`, `/api/auth/refresh`, `/api/auth/change-credentials`, and `/api/settings/profile` are rate-limited
- counters use Redis when available and fall back to in-process tracking for degraded environments/tests
- successful auth clears the relevant failure counter

Why this matters:
- even single-user deployments benefit from basic online guessing protection

Status:
- implemented for v0.0.1

### 8. Attachment upload size/path policy is enforced

Severity: Medium

Current behavior:
- uploads are streamed in chunks to a temporary file
- a maximum upload size is enforced
- destination folder and filename validation rejects unsafe paths and hidden targets

Why this matters:
- large uploads can increase memory pressure
- non-attachment writes can be abused to corrupt repository state

Status:
- implemented for v0.0.1

### 9. Security regression coverage was expanded

Severity: Low

Current behavior:
- regression coverage now includes auth cookie transport, auth throttling, sync target validation/redaction, `.obsidian/` and `.git/` write rejection, and upload validation

Why this matters:
- this usually means invalid user input is not being mapped cleanly to a client error
- it also makes regression detection weaker

Residual follow-up:
- continue adding encoded traversal and broader end-to-end abuse cases as the route surface grows

---

## Remaining Follow-up

The highest-signal remaining security follow-ups after the v0.0.1 pass are:

1. Consider full cookie-based auth plus CSRF protection if the deployment model broadens beyond the current same-origin single-user setup.
2. Consider stricter attachment type policy if the instance will accept uploads from less-trusted networks.
3. Keep expanding negative/security regression tests alongside new API surface.

---

## Test Coverage Landed

- auth cookie transport and refresh flow tests
- secret redaction tests for sync settings and buffered system logs
- SSRF guard tests for private and credential-bearing sync targets
- `.obsidian/` and `.git/` write rejection tests
- upload filename, folder, and max-size validation tests
- startup validation tests for placeholder secrets
- auth/profile rate-limit tests

---

## Deployment Guidance

- keep `CORS_ALLOWED_ORIGINS` explicit in production
- prefer HTTPS in production so the refresh cookie is sent with the `Secure` flag
- do not store credentials inside `git_remote_url`; use SSH remotes or password fields instead
- do not expose backend, DB, or Redis ports publicly
- keep `ALLOW_PRIVATE_SYNC_TARGETS=false` unless you intentionally need self-hosted/private remotes
- use a strong `.env` and verify all placeholder values are replaced
