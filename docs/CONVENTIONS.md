# Conventions

## 코드 스타일

### Python (Backend)
- `ruff format` + `ruff check` (lint+format 통합)
- type hints 필수 (모든 함수 시그니처)
- async 우선, 파일 I/O는 `aiofiles`
- pydantic v2 모델로 요청/응답 스키마
- SQLAlchemy 2.0 스타일 (mapped_column, async session)
- 에러: `FastAPI HTTPException`

### TypeScript (Frontend)
- strict mode
- prettier + prettier-plugin-svelte
- SvelteKit 5 runes (`$state`, `$derived`, `$effect`)
- 에러: toast 알림

### 환경변수
- `.env` 파일 기반, `.env.example`에 템플릿
- `backend/app/config.py`에서 pydantic-settings로 관리
- 필수: `DB_PASS`, `JWT_SECRET`, `GIT_REMOTE_URL`, `GIT_BRANCH`
- 선택: 포트(3000/8000/5432/6379), `GIT_SYNC_INTERVAL_SECONDS`(기본 300), `VAULT_LOCAL_PATH`(dev)

---

## Git

### 브랜치 & 커밋 관리
- Phase 단위 또는 의미 있는 기능 단위로 커밋
- 커밋 전 `ruff check`/`svelte-check` 등 린트 통과 확인
- `docs/PROGRESS.md`에 완료 항목 반영 후 함께 커밋

### 커밋 메시지
Conventional commits: `feat|fix|docs|style|refactor|test|chore|build|ci|perf`
```
feat(wiki): add wikilink parser
fix(sync): handle index.lock stale file
```

### Git Hooks (pre-commit)
`.pre-commit-config.yaml`:
- Python: ruff (--fix) + ruff-format
- Frontend: svelte-check (--threshold error) + prettier
- commit-msg: conventional commits 형식 강제

### .gitignore 권장 (vault)
`.obsidian/workspace.json`, `workspace-mobile.json`, `appearance.json`, `hotkeys.json`, `.DS_Store`

---

## Docker

- **Frontend**: multi-stage (deps → dev → build → production). dev target은 compose.dev.yml
- **Backend**: python:3.12-slim, git+openssh-client. uvicorn workers=2 (prod)
- **DB**: postgres:16-alpine, `init.sql`로 pg_trgm/unaccent 활성화
- **Redis**: 7-alpine, maxmemory 256mb, allkeys-lru, persistence 불필요
- **dev 오버라이드**: Vite HMR(24678), 소스 bind mount, vault/config 로컬 bind
- 모든 서비스 healthcheck. backend는 db healthy 의존

---

## CI 검증

```bash
# Backend
ruff check . && ruff format --check . && pytest -x

# Frontend
npx svelte-check --threshold error && npx prettier --check 'src/**/*.{svelte,ts,js}' && npm test
```

---

## 초기 설정

1. `.env.example` → `.env`, `JWT_SECRET` 자동생성 (`openssl rand -hex 32`)
2. 관리자 비밀번호 bcrypt 해시 → `ADMIN_PASSWORD_HASH`
3. SSH 키 (`config/ssh/id_ed25519`) → GitHub Deploy Key (write access)
4. Vault git clone → `docker compose up -d`

---

## 배포 체크리스트

- [ ] `.env` changeme 값 교체, JWT_SECRET 32바이트+
- [ ] SSH 공개키 → GitHub Deploy Key (write access)
- [ ] `docker compose up -d` → 전 서비스 healthy
- [ ] `docker compose exec backend python -m app.cli reindex` 초기 인덱싱
- [ ] 로그인/뷰/편집/동기화 E2E 테스트
- [ ] HTTPS: nginx reverse proxy + Let's Encrypt
