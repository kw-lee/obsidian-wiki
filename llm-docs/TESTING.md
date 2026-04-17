# Testing Guide

## Overview

| Area | Framework | Runtime |
|------|-----------|---------|
| Backend | pytest + pytest-asyncio | SQLite (local) / PostgreSQL (Docker) |
| Frontend | Vitest + jsdom | jsdom |
| Integration | docker-compose.test.yml | PostgreSQL + Redis (Docker) |

## Quick Run

```bash
# Full suite (Docker — includes PostgreSQL + Redis)
make test

# Local run (fast, uses SQLite)
make test-backend-local
make test-frontend-local
```

## Backend Tests

### Layout

```
backend/tests/
├── conftest.py         # Shared fixtures (client, auth, vault)
├── test_health.py      # Healthcheck endpoint
├── test_auth.py        # Auth (login, JWT, refresh)
├── test_conflict.py    # 3-way merge conflict detection
├── test_vault.py       # Filesystem (read/write/delete/tree)
├── test_indexer.py     # Indexer (wikilink/tag extraction)
├── test_wiki.py        # Wiki CRUD API
├── test_search.py      # Search API
├── test_sync.py        # Git sync API
├── test_tags.py        # Tag/graph API
└── test_attachments.py # Attachment upload/download
```

### Local Run

```bash
cd backend
source .venv/bin/activate
python -m pytest -v --tb=short
```

### Docker Run

```bash
make test-backend
```

Running under Docker uses real PostgreSQL + Redis, so PostgreSQL-specific features such as `tsvector` and `pg_trgm` can be exercised.

### Fixtures (conftest.py)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `setup_vault` | function (autouse) | Create/clean up a temporary vault directory |
| `auth_headers` | function | JWT auth headers |
| `client` | function | ASGI test client (httpx) |

### Categories

#### Unit tests (no external dependencies)

- `test_auth.py`: password verification, JWT encode/decode
- `test_conflict.py`: 3-way merge logic
- `test_vault.py`: file I/O, tree building, path traversal prevention
- `test_indexer.py`: wikilink and tag extraction

#### API tests (ASGI client)

- `test_health.py`: `GET /health`
- `test_wiki.py`: CRUD endpoints, auth enforcement
- `test_search.py`: query parameter validation
- `test_sync.py`: sync status queries
- `test_tags.py`: tag/graph queries
- `test_attachments.py`: file upload/download, path safety

### Notes

- **Local tests use SQLite** — PostgreSQL-specific features (`tsvector`, `pg_trgm`, `ARRAY`, `JSONB`) may fail locally
- **Docker tests use PostgreSQL** — everything works
- Search tests (`test_search.py`) tolerate 500 errors locally (SQLite incompatibility)

## Frontend Tests

### Layout

```
frontend/src/
├── tests/
│   └── setup.ts              # Vitest setup (jest-dom matchers)
├── lib/
│   ├── types.test.ts          # TypeScript type contracts
│   └── api/
│       ├── client.test.ts     # API client (fetch mock, auth, error handling)
│       └── wiki.test.ts       # Wiki API functions (endpoint mapping)
```

### Local Run

```bash
cd frontend
npx vitest run          # Single run
npx vitest              # Watch mode
```

### Docker Run

```bash
make test-frontend
```

### Categories

#### API Client (`client.test.ts`)

- Automatic auth header injection
- Query parameter serialization
- 204 response handling
- Error response handling
- Automatic token refresh on 401

#### Wiki API (`wiki.test.ts`)

- Every API function calls the correct endpoint
- HTTP method verification (GET/POST/PUT/DELETE)
- Request body serialization

#### Type Contracts (`types.test.ts`)

- TypeScript interface contracts
- Nested structures (TreeNode)
- Runtime shape checks

### Vitest Configuration

```typescript
// vite.config.ts
test: {
    include: ['src/**/*.test.ts'],
    environment: 'jsdom',
    globals: true,
    setupFiles: ['src/tests/setup.ts']
}
```

## Docker Integration Tests

### Run

```bash
# Full (backend + frontend)
make test

# Individual
make test-backend
make test-frontend

# Cleanup after run
make test-clean
```

### Behavior

`docker-compose.test.yml` performs:

1. **test-db**: start PostgreSQL 16 (tmpfs — no disk, auto-removed after tests)
2. **test-redis**: start Redis 7 (non-persistent)
3. **backend-test**: wait for DB/Redis → run `pytest`
4. **frontend-test**: run `vitest run`

The `--abort-on-container-exit` flag shuts everything down once tests complete.

## CI Integration

### GitHub Actions Example

```yaml
name: Test
on: [push, pull_request]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make test-backend

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: make test-frontend
```

## Writing New Tests

### Backend

```python
# backend/tests/test_my_feature.py
import pytest

@pytest.mark.asyncio
async def test_my_endpoint(client, auth_headers, setup_vault):
    resp = await client.get("/api/my-endpoint", headers=auth_headers)
    assert resp.status_code == 200

def test_my_unit():
    result = my_function("input")
    assert result == "expected"
```

### Frontend

```typescript
// frontend/src/lib/my-module.test.ts
import { describe, it, expect } from 'vitest';
import { myFunction } from './my-module';

describe('myFunction', () => {
    it('returns expected result', () => {
        expect(myFunction('input')).toBe('expected');
    });
});
```

## Coverage

### Backend

```bash
cd backend
pip install pytest-cov
python -m pytest --cov=app --cov-report=html
open htmlcov/index.html
```

### Frontend

```bash
cd frontend
npx vitest run --coverage
```
