# Obsidian Web Wiki

개인 Obsidian vault를 웹으로 서빙하는 셀프호스트 위키. 단일 사용자. 데스크톱=Obsidian 앱, 모바일=웹 브라우저.

## Tech Stack

- **Frontend**: SvelteKit 5 (runes, SSR+SPA), TypeScript strict, CodeMirror 6
- **Backend**: Python 3.12+ FastAPI (async), pydantic v2, SQLAlchemy 2.0 async
- **DB**: PostgreSQL 16 (JSONB, FTS `tsvector` + `pg_trgm`), Redis 7 (캐시/락)
- **Auth**: JWT (access 15분 / refresh 7일) + bcrypt, 단일 사용자
- **Sync**: Git 또는 WebDAV 양방향 (Obsidian ↔ Remote ↔ Server)
- **Deploy**: Docker Compose (PV: db_data, vault_data, config_data)

## Architecture

```
Obsidian ◄─git / WebDAV─► Remote ◄─git / WebDAV─► Server(Docker)
Browser ◄─https─► SvelteKit:3000 → FastAPI:8000 → Postgres:5432 / Redis:6379
                                      └─► Vault PV (git repo or WebDAV mirror)
```

## Core Rules

### Obsidian 호환 파싱
`[[wikilink]]`, `![[embed]]`, `#tag`, YAML frontmatter, callout(`>[!type]`), Mermaid, KaTeX, checkbox

### 동기화 & 충돌
- 서버 주기적 sync pull/push (설정에 따라 Git 또는 WebDAV, 기본 5분) → 변경 시 DB 인덱스 갱신
- 웹 편집 저장: base_commit vs HEAD 비교 → 불일치 시 3-way merge → 실패 시 409+diff
- `.obsidian/` 읽기 전용 (웹에서 수정 불가, 리모트 변경은 theirs 전략)

### 검색
PostgreSQL `tsvector` + `pg_trgm` 하이브리드. 한글/영어. Redis 캐시(TTL 5분).

### 첨부파일
vault 내 상대 경로 유지 → `/api/attachments/{path}`. 업로드 시 vault에 저장+git commit.

## API Endpoints

```
POST   /api/auth/login|refresh|change-credentials
GET    /api/wiki/tree|doc/{path}|backlinks/{path}
PUT    /api/wiki/doc/{path}          # conflict check 포함
DELETE /api/wiki/doc/{path}
POST   /api/wiki/doc
GET    /api/search?q=...
POST   /api/sync/pull|push
GET    /api/sync/status
GET|POST /api/attachments/{path}|upload
GET    /api/tags|graph
```

## Agent Scopes

| Agent | 범위 | 핵심 도구/패턴 |
|-------|------|---------------|
| frontend | `frontend/` | SvelteKit 5 runes, unified+remark+rehype, CodeMirror 6, d3, Vitest |
| backend | `backend/` | FastAPI async, SQLAlchemy 2.0, gitpython, aiofiles, pytest-asyncio |
| database | `backend/app/db/` | Alembic, pg_trgm, tsvector, GIN index |
| sync | `sync.py`, `git_ops.py`, `conflict.py` | git fetch/pull/push/rebase, 3-way merge, Redis lock |
| docker | Docker*, compose, nginx, .env | multi-stage build, PV 3개, healthcheck |

## Coding Conventions

- Python: `ruff format` + `ruff check`, type hints 필수
- TypeScript: strict mode, prettier + prettier-plugin-svelte
- 커밋: conventional commits (`feat:`, `fix:`, `docs:` ...)
- 문서 동기화: 기능을 구현하거나 UX/설정/배포/보안 동작을 바꾸면 같은 변경 안에서 `README.md`, `README.en.md`, `llm-docs/PROGRESS.md`, 그리고 영향받는 `llm-docs/*.md` 를 함께 갱신
- 에러: FastAPI HTTPException, 프론트 toast
- 환경변수: `.env` → `config.py` (pydantic-settings)

## Non-Functional

- macOS 개발, Docker 프로덕션
- 문서 뷰 <200ms, 검색 <500ms, vault ~10,000 파일

## Reference

- `llm-docs/ARCHITECTURE.md` - 시스템 아키텍처, 데이터 흐름, 기술 결정사항
- `llm-docs/CONVENTIONS.md` - 코드 스타일, Git hooks, CI, 배포 컨벤션
- `llm-docs/SETTINGS.md` - 관리자 설정 화면과 런타임 설정
- `llm-docs/SECURITY.md` - 보안 점검과 하드닝 우선순위
- `llm-docs/PROGRESS.md` - 구현 진행 상황 추적
