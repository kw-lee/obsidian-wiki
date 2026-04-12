# 테스트 가이드

## 개요

| 영역 | 프레임워크 | 실행 환경 |
|------|-----------|----------|
| Backend | pytest + pytest-asyncio | SQLite (로컬) / PostgreSQL (Docker) |
| Frontend | Vitest + jsdom | jsdom |
| Integration | docker-compose.test.yml | PostgreSQL + Redis (Docker) |

## 빠른 실행

```bash
# 전체 테스트 (Docker — PostgreSQL + Redis 포함)
make test

# 로컬 실행 (빠름, SQLite 사용)
make test-backend-local
make test-frontend-local
```

## Backend 테스트

### 구조

```
backend/tests/
├── conftest.py         # 공통 fixtures (client, auth, vault)
├── test_health.py      # 헬스체크 엔드포인트
├── test_auth.py        # 인증 (로그인, JWT, 리프레시)
├── test_conflict.py    # 3-way merge 충돌 감지
├── test_vault.py       # 파일시스템 (읽기/쓰기/삭제/트리)
├── test_indexer.py     # 인덱서 (위키링크/태그 추출)
├── test_wiki.py        # Wiki CRUD API
├── test_search.py      # 검색 API
├── test_sync.py        # Git 동기화 API
├── test_tags.py        # 태그/그래프 API
└── test_attachments.py # 첨부파일 업로드/다운로드
```

### 로컬 실행

```bash
cd backend
source .venv/bin/activate
python -m pytest -v --tb=short
```

### Docker 실행

```bash
make test-backend
```

Docker 실행 시 실제 PostgreSQL + Redis를 사용하므로 `tsvector`, `pg_trgm` 등 PostgreSQL 고유 기능 테스트 가능.

### Fixtures (conftest.py)

| Fixture | 범위 | 설명 |
|---------|------|------|
| `setup_vault` | function (autouse) | 임시 vault 디렉토리 생성/정리 |
| `auth_headers` | function | JWT 인증 헤더 |
| `client` | function | ASGI 테스트 클라이언트 (httpx) |

### 테스트 카테고리

#### Unit 테스트 (외부 의존성 없음)

- `test_auth.py`: 비밀번호 검증, JWT 생성/디코딩
- `test_conflict.py`: 3-way merge 로직
- `test_vault.py`: 파일 I/O, 트리 빌드, 경로 순회 방지
- `test_indexer.py`: 위키링크 추출, 태그 추출

#### API 테스트 (ASGI 클라이언트)

- `test_health.py`: `GET /health`
- `test_wiki.py`: CRUD 엔드포인트, 인증 검증
- `test_search.py`: 검색 파라미터 검증
- `test_sync.py`: 동기화 상태 조회
- `test_tags.py`: 태그/그래프 조회
- `test_attachments.py`: 파일 업로드/다운로드, 경로 보안

### 주의사항

- **로컬 테스트는 SQLite** 사용 — PostgreSQL 고유 기능 (`tsvector`, `pg_trgm`, `ARRAY`, `JSONB`)은 로컬에서 일부 실패할 수 있음
- **Docker 테스트는 PostgreSQL** 사용 — 모든 기능 정상 동작
- 검색 테스트(`test_search.py`)는 로컬에서 500 에러 허용 (SQLite 비호환)

## Frontend 테스트

### 구조

```
frontend/src/
├── tests/
│   └── setup.ts              # Vitest 설정 (jest-dom matchers)
├── lib/
│   ├── types.test.ts          # TypeScript 타입 계약 검증
│   └── api/
│       ├── client.test.ts     # API 클라이언트 (fetch mock, 인증, 에러 핸들링)
│       └── wiki.test.ts       # Wiki API 함수 (엔드포인트 매핑)
```

### 로컬 실행

```bash
cd frontend
npx vitest run          # 1회 실행
npx vitest              # watch 모드
```

### Docker 실행

```bash
make test-frontend
```

### 테스트 카테고리

#### API Client (`client.test.ts`)

- 인증 헤더 자동 추가
- 쿼리 파라미터 전달
- 204 응답 처리
- 에러 응답 처리
- 401 시 자동 토큰 리프레시

#### Wiki API (`wiki.test.ts`)

- 모든 API 함수가 올바른 엔드포인트 호출
- HTTP 메서드 검증 (GET/POST/PUT/DELETE)
- 요청 본문 직렬화 검증

#### Type Contracts (`types.test.ts`)

- TypeScript 인터페이스 계약 검증
- 중첩 구조 (TreeNode) 테스트
- 런타임 형태 검증

### Vitest 설정

```typescript
// vite.config.ts
test: {
    include: ['src/**/*.test.ts'],
    environment: 'jsdom',
    globals: true,
    setupFiles: ['src/tests/setup.ts']
}
```

## Docker 통합 테스트

### 실행

```bash
# 전체 (backend + frontend)
make test

# 개별
make test-backend
make test-frontend

# 테스트 후 정리
make test-clean
```

### 동작 방식

`docker-compose.test.yml`이 다음을 수행:

1. **test-db**: PostgreSQL 16 시작 (tmpfs — 디스크 미사용, 테스트 후 자동 삭제)
2. **test-redis**: Redis 7 시작 (비영속)
3. **backend-test**: DB/Redis 준비 대기 → `pytest` 실행
4. **frontend-test**: `vitest run` 실행

`--abort-on-container-exit` 플래그로 테스트 완료 시 자동 종료.

## CI 연동

### GitHub Actions 예시

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

## 테스트 작성 가이드

### Backend 새 테스트 추가

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

### Frontend 새 테스트 추가

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

## 커버리지

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
