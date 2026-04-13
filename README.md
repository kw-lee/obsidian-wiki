# Obsidian Web Wiki

개인 [Obsidian](https://obsidian.md) vault를 웹 브라우저에서 읽고 편집할 수 있게 해주는 셀프호스트 위키입니다. 데스크톱에서는 기존 Obsidian 앱을 그대로 쓰고, 모바일/외부에서는 웹으로 같은 vault에 접근합니다.

## 이게 뭔가요

- **단일 사용자** 셀프호스트 위키. 집 서버나 VPS 에 Docker 로 띄워서 씁니다.
- **Git 기반 양방향 동기화**: Obsidian ↔ 원격 Git 리포 ↔ 서버. 충돌은 3-way merge 로 자동 처리하고 실패 시 diff 를 돌려줍니다.
- **Obsidian 호환**: `[[wikilink]]`, `![[embed]]`, `#tag`, YAML frontmatter, callout, Mermaid, KaTeX, checkbox 지원.
- **검색**: PostgreSQL `tsvector` + `pg_trgm` 하이브리드 (한/영).
- **편집**: CodeMirror 6 기반 마크다운 에디터 (구문 강조, ⌘S 저장).
- **부가 기능**: 백링크 패널, 그래프 뷰 (d3-force), 커맨드 팔레트 (⌘P), Quick Switcher (⌘K), 다크/라이트 테마 (Catppuccin).

## 기술 스택

- **Frontend**: SvelteKit 5 (runes) · TypeScript · CodeMirror 6 · d3
- **Backend**: Python 3.12 · FastAPI (async) · SQLAlchemy 2.0 · pydantic v2
- **DB / Cache**: PostgreSQL 16 · Redis 7
- **Auth**: JWT (access 15분 / refresh 7일) + bcrypt
- **Deploy**: Docker Compose

아키텍처와 데이터 흐름은 [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) 에 정리되어 있습니다.

## 빠른 시작

### 필요한 것

- Docker + Docker Compose
- Vault 를 담을 Git 원격 리포지토리 (예: private GitHub repo)
- SSH 키 (서버가 vault 리포에 pull/push 할 수 있어야 함)

### 1. 환경 변수 설정

```bash
cp .env.example .env
```

`.env` 편집:

```ini
POSTGRES_PASSWORD=...               # 아무 강한 값
JWT_SECRET=$(openssl rand -hex 32)  # 반드시 교체
INIT_ADMIN_USERNAME=admin           # 최초 관리자 계정 (최초 로그인 후 강제 변경됨)
INIT_ADMIN_PASSWORD=changeme
GIT_REMOTE_URL=git@github.com:you/vault.git
GIT_BRANCH=main
```

### 2. 실행

```bash
make up        # 프로덕션: 백그라운드 기동
make dev       # 개발 모드: 핫리로드 + 포그라운드 로그
make logs      # 로그 확인
make down      # 정지
```

브라우저에서 **`http://localhost:${WEB_PORT}`** (기본 80) 접속 → `INIT_ADMIN_*` 로 로그인

> `BACKEND_PORT` / `FRONTEND_PORT` 는 nginx 를 거치지 않는 직접 접근용(디버그). 실제 사용 진입점은 `WEB_PORT` 입니다. → **강제 credential 변경 페이지** (`/auth/setup`) 에서 새 username/password 지정 → 메인 화면으로 이동.

### 3. DB 마이그레이션 (스키마 변경 시)

```bash
make migrate                          # 최신으로 업그레이드
make migrate-generate msg="add xyz"   # 새 리비전 생성 (autogenerate)
```

## 개발

```bash
make dev                 # 전체 스택 핫리로드 실행
make shell-backend       # 백엔드 컨테이너 셸
make shell-frontend      # 프론트 컨테이너 셸
make shell-db            # psql
make lint                # ruff + prettier + svelte-check
make lint-fix            # 자동 포맷/수정
```

## 테스트

모든 테스트는 Docker 환경에서 실행합니다 (PostgreSQL + Redis 컨테이너 포함).

```bash
make test              # backend + frontend 전체
make test-backend      # backend 만 (pytest)
make test-frontend     # frontend 만 (vitest)
make test-clean        # 테스트 컨테이너/볼륨 정리
```

자세한 내용은 [`docs/TESTING.md`](docs/TESTING.md) 참고.

## 배포

nginx reverse proxy + HTTPS 템플릿 포함. Docker 빌드/배포 가이드는 [`docs/DOCKER.md`](docs/DOCKER.md) 참고.

퍼시스턴트 볼륨 3개:
- `db_data` — PostgreSQL 데이터
- `vault_data` — Git 클론된 vault
- `config_data` — 기타 서버 설정

## 주요 단축키

| 키 | 동작 |
|----|------|
| `⌘K` | Quick Switcher (파일 빠른 이동) |
| `⌘P` | 커맨드 팔레트 (새 문서, Git sync, 테마 전환 등) |
| `⌘S` | 편집 중 문서 저장 |

## 문서

- [`CLAUDE.md`](CLAUDE.md) — 프로젝트 전반 규칙 (AI/기여자용)
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 시스템 아키텍처 / 기술 결정
- [`docs/CONVENTIONS.md`](docs/CONVENTIONS.md) — 코드 스타일 / Git / CI
- [`docs/DOCKER.md`](docs/DOCKER.md) — Docker 빌드·배포
- [`docs/TESTING.md`](docs/TESTING.md) — 테스트 가이드
- [`docs/PROGRESS.md`](docs/PROGRESS.md) — 구현 진행 상황

## 라이선스

개인 프로젝트. 별도 명시 전까지 All rights reserved.
