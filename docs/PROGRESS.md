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
- [x] CodeMirror 편집기 — CodeMirror 6 (마크다운 구문 강조, 줄 번호, Catppuccin 테마, ⌘S 저장)
- [x] 검색 (Quick Switcher, ⌘K)
- [x] 백링크 패널
- [x] 모바일 반응형
- [x] 다크/라이트 테마 (Catppuccin 색상)

## Phase 4: 고급 기능

- [x] 그래프 뷰 (d3-force, 줌/드래그, 노드 클릭 네비게이션)
- [ ] 플러그인 호환 (Dataview 등) — 추후
- [x] 커맨드 팔레트 (⌘P) — 새 문서, 검색, 그래프, Git sync, 테마 전환
- [x] nginx reverse proxy + HTTPS 템플릿
- [x] Alembic async 마이그레이션 설정

## Phase 5: Docker 빌드/배포 & 테스트

- [x] `.dockerignore` — backend, frontend 빌드 컨텍스트 최적화
- [x] `docker-compose.test.yml` — PostgreSQL+Redis 포함 테스트 환경
- [x] `Makefile` — build, up, dev, test, lint, migrate, shell, clean 커맨드
- [x] Backend 테스트 확장 — wiki, search, sync, tags, attachments, indexer (6개 추가)
- [x] Frontend Vitest 설정 — jsdom, setup, test scripts
- [x] Frontend 테스트 — API client, wiki API, type contracts (3개 추가)
- [x] `docs/DOCKER.md` — Docker 빌드/배포 가이드
- [x] `docs/TESTING.md` — 테스트 가이드 (backend, frontend, Docker 통합)

## Phase 6: 인증 개선 (Docker env 초기 계정 + 강제 변경)

### Backend
- [x] `users` 테이블 추가 (SQLAlchemy ORM 모델)
- [x] `config.py`: `INIT_ADMIN_USERNAME` / `INIT_ADMIN_PASSWORD` 환경변수 추가 (기존 `admin_username`, `admin_password_hash` 제거)
- [x] 서버 startup 이벤트: DB에 유저 미존재 시 env 초기 계정 생성 (bcrypt 해싱, `must_change_credentials=true`)
- [x] `auth.py` 리팩터: env 비교 → DB 조회 방식으로 변경
- [x] 로그인 응답에 `must_change_credentials` 상태 포함 (JWT 클레임 + 응답 필드)
- [x] `POST /api/auth/change-credentials` 엔드포인트 — username/password 변경 + 플래그 해제 + 새 토큰 발급
- [x] `must_change=true` 토큰으로는 credential 변경 외 API 접근 차단 (`get_current_user` 디펜던시)
- [x] `.env.example` 업데이트
- [x] 테스트: 초기 계정 생성, 강제 변경 플로우, 변경 후 정상 접근 (10 passed)

### Frontend
- [x] 강제 credential 변경 페이지 (`/auth/setup`)
- [x] 로그인 후 `must_change` 감지 시 강제 리다이렉트 (다른 라우트 접근 차단)
- [x] 변경 완료 후 새 토큰으로 메인 페이지 이동

## Phase 7: 설정 페이지 (Admin Dashboard)

설계: [`docs/SETTINGS.md`](SETTINGS.md) 참고. `.env` 에서 운영 중 변경되는 값을 DB 로 이전하고 웹 UI 에서 관리.

### Phase 7-1: MVP (Profile + Git Sync)

#### Backend
- [ ] `AppSettings` 모델 추가 (single-row, `CHECK(id=1)`)
- [ ] Alembic 마이그레이션 — 테이블 생성 + `.env` 값 seed (`GIT_REMOTE_URL`/`GIT_BRANCH`/`GIT_SYNC_INTERVAL_SECONDS`)
- [ ] `init.sql` 동기화
- [ ] `services/settings.py` — DB 런타임 설정 로더 (캐시 + invalidate)
- [ ] `config.py` 정리 — 부트스트랩 값만 유지, git 관련 제거
- [ ] `GET/PUT /api/settings/profile` — username/password 변경 + 새 토큰 발급
- [ ] `GET/PUT /api/settings/git` — git sync 설정 조회/변경
- [ ] `services/git_scheduler.py` — asyncio.Task 래퍼, 설정 변경 시 cancel+restart
- [ ] 테스트 — profile 변경/검증, git 설정 저장, 스케줄러 리로드

#### Frontend
- [ ] `/settings` 레이아웃 + 탭 네비 (`+layout.svelte`)
- [ ] `/settings/profile` 페이지 — 현재 pw 확인 + 새 username/pw 변경
- [ ] `/settings/git` 페이지 — remote URL/branch/interval/auto-sync 토글, 수동 pull/push, 상태 카드
- [ ] `lib/api/settings.ts` — API 래퍼
- [ ] 커맨드 팔레트(⌘P)에 "Open Settings" 항목 추가
- [ ] `mustChangeCredentials` 가드 적용

#### 정리
- [ ] `.env.example` / `.env` 에서 git 관련 변수 제거 + 주석 안내
- [ ] `README.md` / `docs/ARCHITECTURE.md` 에 설정 페이지 언급

### Phase 7-2: 후속

- [ ] Vault 탭 — 디스크/문서/태그 통계, 인덱스 재빌드 버튼
- [ ] Appearance 탭 — 서버 기본 테마
- [ ] System 탭 — 버전, uptime, DB/Redis ping, vault git status
- [ ] (옵션) 로그 tail 뷰어
