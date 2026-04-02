# Progress

프로젝트 구현 진행 상황 추적.

**상태 컨벤션**:
- `[ ]` TODO
- `[-]` WIP — 작업자 이니셜 표기 (예: `[-] @KW`)
- `[x]` Done

동시 작업 시 WIP 항목에 담당자를 명시하여 충돌 방지.

---

## Phase 1: 프로젝트 기반 구조

- [x] CLAUDE.md / docs 정리
- [x] DB 스키마 — `backend/app/db/init.sql`
- [x] docker-compose.yml + docker-compose.dev.yml
- [x] Dockerfile.frontend (multi-stage: deps→build→prod)
- [x] Dockerfile.backend (base→dev/prod)
- [x] .env.example
- [x] .pre-commit-config.yaml
- [x] .gitignore

## Phase 2: Backend 핵심

- [x] FastAPI 프로젝트 초기화 — main.py, config.py, pyproject.toml
- [x] Auth (login/refresh/JWT)
- [x] DB 모델 (SQLAlchemy ORM)
- [ ] Alembic 마이그레이션 설정
- [x] Wiki CRUD API — doc 조회/저장/삭제/생성
- [x] Git 동기화 (pull/push) — git_ops.py, sync.py
- [x] 충돌 감지/3-way merge — conflict.py
- [x] 검색 API (FTS+trigram) — search.py
- [x] 첨부파일 서빙/업로드
- [x] 파일 트리 API
- [x] 백링크/태그/그래프 API
- [x] 전체/증분 인덱싱
- [x] 단위 테스트 (17 passed) — auth, conflict, vault, health

## Phase 3: Frontend 핵심

- [x] SvelteKit 프로젝트 초기화 (adapter-node, vite proxy)
- [x] 로그인 페이지
- [x] 레이아웃 (사이드바+메인+우측패널)
- [x] 파일 트리 컴포넌트
- [x] Markdown 렌더러 — wikilink/tag 플러그인 (marked)
- [x] 문서 뷰어
- [-] CodeMirror 편집기 — 기본 textarea 편집기 구현, CodeMirror는 Phase 4
- [x] 검색 (Quick Switcher, ⌘K)
- [x] 백링크 패널
- [x] 모바일 반응형
- [x] 다크/라이트 테마 (Catppuccin 색상)

## Phase 4: 고급 기능

- [ ] 그래프 뷰 (d3)
- [ ] 플러그인 호환 (Dataview 등)
- [ ] 커맨드 팔레트
- [ ] nginx + HTTPS
