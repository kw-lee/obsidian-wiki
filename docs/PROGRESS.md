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
- [ ] docker-compose.yml
- [ ] Dockerfile.frontend
- [ ] Dockerfile.backend
- [ ] .env.example
- [ ] .pre-commit-config.yaml

## Phase 2: Backend 핵심

- [ ] FastAPI 프로젝트 초기화 — main.py, config.py, pyproject.toml
- [ ] Auth (login/refresh/JWT)
- [ ] DB 모델 (SQLAlchemy ORM)
- [ ] Alembic 마이그레이션 설정
- [ ] Wiki CRUD API — doc 조회/저장/삭제/생성
- [ ] Git 동기화 (pull/push) — git_ops.py, sync.py
- [ ] 충돌 감지/3-way merge — conflict.py
- [ ] 검색 API (FTS+trigram) — search.py
- [ ] 첨부파일 서빙/업로드
- [ ] 파일 트리 API
- [ ] 백링크/태그/그래프 API
- [ ] 전체/증분 인덱싱

## Phase 3: Frontend 핵심

- [ ] SvelteKit 프로젝트 초기화
- [ ] 로그인 페이지
- [ ] 레이아웃 (사이드바+메인+우측)
- [ ] 파일 트리 컴포넌트
- [ ] Markdown 렌더러 — wikilink/embed/callout/tag 플러그인
- [ ] 문서 뷰어
- [ ] CodeMirror 편집기 — 자동완성, 자동저장
- [ ] 검색 (Quick Switcher)
- [ ] 백링크 패널
- [ ] 모바일 반응형
- [ ] 다크/라이트 테마

## Phase 4: 고급 기능

- [ ] 그래프 뷰 (d3)
- [ ] 플러그인 호환 (Dataview 등)
- [ ] 커맨드 팔레트
- [ ] nginx + HTTPS
