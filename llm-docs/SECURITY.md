# Security Review

Security review snapshot taken on 2026-04-13 before the next hardening pass.

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

## Findings

### 1. Browser tokens are stored in `localStorage`

Severity: High

Current behavior:
- access and refresh tokens are stored in `localStorage`
- any successful XSS can exfiltrate both tokens

Why this matters:
- token theft becomes a session takeover
- refresh token exposure turns short-lived access tokens into a longer-lived compromise

Recommended fix:
- move the refresh token to an `httpOnly`, `Secure`, `SameSite` cookie
- preferably keep access tokens in memory only, or also migrate to cookie-based auth
- add CSRF protection at the same time if cookie auth is introduced

### 2. Sync configuration can leak credentials back to the UI

Severity: High

Current behavior:
- `git_remote_url` is returned in sync settings responses
- if an operator pastes an HTTPS remote with embedded credentials or token, the secret is echoed back to the browser
- logs may also end up containing sync-related error details

Why this matters:
- secrets become visible in the UI, browser devtools, and possibly system log output

Recommended fix:
- redact credential-bearing URL components in API responses
- reject or normalize URLs with embedded credentials
- scrub secrets from sync/log messages before they reach the UI

### 3. WebDAV and Git remote configuration can be used as SSRF pivots

Severity: High

Current behavior:
- sync settings accept arbitrary remote endpoints
- `test`, `status`, scheduler, `pull`, and `push` paths cause the backend to connect to the configured remote
- no allowlist or private-network guard is currently applied

Why this matters:
- an attacker with authenticated access, or with stolen tokens, could make the server connect to internal services or metadata endpoints

Recommended fix:
- restrict allowed URL schemes
- reject localhost, link-local, loopback, and private IP ranges unless explicitly allowed by configuration
- consider an explicit `ALLOW_PRIVATE_SYNC_TARGETS` escape hatch for trusted self-hosted deployments

### 4. Filesystem write guards are too weak for `.obsidian/`, `.git/`, and upload paths

Severity: High

Current behavior:
- `resolve()` prevents escaping the vault root, which is good
- however, application-level policy does not currently block writes to sensitive in-vault paths
- the attachment upload endpoint trusts `folder` and `file.filename`
- wiki save/create routes do not enforce the documented `.obsidian/` read-only rule

Why this matters:
- `.obsidian/` can be modified from the web despite the architecture rule saying it is read-only
- `.git/` contents inside the vault can potentially be overwritten via upload paths
- this is both a security and integrity risk

Recommended fix:
- add a central path validator that rejects:
  - `.obsidian/` writes from web routes
  - `.git/` reads/writes
  - absolute paths
  - empty / dot-only path segments
  - suspicious upload filenames containing path separators
- return `400` instead of uncaught `500` errors for traversal attempts

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

### 7. Login flow has no brute-force protection

Severity: Medium

Current behavior:
- no rate limiting, lockout, or backoff is applied on auth endpoints

Why this matters:
- even single-user deployments benefit from basic online guessing protection

Recommended fix:
- add Redis-backed rate limiting for:
  - `/api/auth/login`
  - `/api/auth/refresh`
  - `/api/auth/change-credentials`
  - `/api/settings/profile`

### 8. Attachment upload currently lacks size/type policy

Severity: Medium

Current behavior:
- the backend reads the whole upload into memory
- there is no file size cap or explicit attachment policy

Why this matters:
- large uploads can increase memory pressure
- non-attachment writes can be abused to corrupt repository state

Recommended fix:
- stream uploads where possible
- enforce a maximum upload size
- restrict upload destinations to approved attachment directories

### 9. Some traversal/error-path tests still tolerate `500`

Severity: Low

Current behavior:
- current tests allow `500` on traversal attempts in some cases

Why this matters:
- this usually means invalid user input is not being mapped cleanly to a client error
- it also makes regression detection weaker

Recommended fix:
- tighten tests to require `400`/`404` only where appropriate
- add negative tests for `.obsidian/`, `.git/`, and encoded traversal attempts

---

## Recommended Hardening Order

1. Move refresh tokens out of `localStorage` and redesign auth transport safely.
2. Redact sync secrets and reject credential-bearing remote URLs.
3. Add SSRF guards for WebDAV and Git remotes.
4. Enforce path policy for wiki writes and attachment uploads.
5. Fail fast on insecure bootstrap configuration.
6. Tighten CORS and deployment defaults.
7. Add auth rate limiting and stronger password policy.
8. Expand security-focused automated tests.

---

## Test Coverage To Add

- auth token storage / cookie transport tests
- secret redaction tests for sync settings and system logs
- SSRF guard tests for private, loopback, and link-local sync targets
- `.obsidian/` and `.git/` write rejection tests
- upload filename and folder validation tests
- traversal tests using encoded paths and nested separators
- startup validation tests for placeholder secrets
- login rate-limit tests

---

## Deployment Guidance Before Hardening Lands

Until the code changes below are implemented:
- keep the repository private
- do not store credentials inside `git_remote_url`
- prefer SSH remotes over token-in-URL HTTPS remotes
- do not expose backend, DB, or Redis ports publicly
- use a strong `.env` and verify all placeholder values are replaced
- treat browser XSS as session compromise because tokens are currently script-readable
