# Obsidian Web Wiki

[English README](README.en.md)

개인 [Obsidian](https://obsidian.md) vault를 웹 브라우저에서 읽고 편집할 수 있게 해주는 셀프호스트 위키입니다. 데스크톱에서는 기존 Obsidian 앱을 그대로 쓰고, 모바일/외부에서는 웹으로 같은 vault에 접근합니다.

## 이게 뭔가요

- **단일 사용자** 셀프호스트 위키. 집 서버나 VPS 에 Docker 로 띄워서 씁니다.
- **선택형 양방향 동기화**: Obsidian ↔ 원격 Git 또는 WebDAV ↔ 서버. 텍스트 충돌은 3-way merge 를 시도하고, 실패하면 diff 와 함께 충돌 상태를 보여줍니다.
- **Git 친화적인 웹 저장**: 웹 편집은 vault 와 검색 인덱스를 바로 갱신하고, Git backend 는 저장마다 commit 하지 않고 sync 시점에 변경분을 체크포인트 commit 으로 묶습니다.
- **저장 충돌 대응**: 웹 편집 중 다른 변경이 먼저 저장되면 현재 draft 를 유지한 채 충돌 diff 모달을 띄우고, 최신 버전 다시 불러오기 또는 계속 편집을 선택할 수 있습니다.
- **Obsidian 호환**: `[[wikilink]]`, `![[embed]]`, `#tag`, YAML frontmatter, callout, Mermaid, KaTeX, checkbox, heading/block target 을 지원합니다.
- **플러그인/포맷 호환**: Tasks 집계(`/tasks`), Dataview 정적 `LIST/TABLE`, Templater 안전 서브셋, Excalidraw 읽기 전용 미리보기를 지원합니다.
- **탐색과 파일 보기**: 전용 `/wiki/...` 문서 경로, 내부 링크/임베드 해석, 미해결 링크의 새 문서 생성 CTA, 이미지/PDF/오디오/비디오/기타 첨부 뷰어를 제공합니다.
- **작업공간 UX**: CodeMirror 6 편집기, 선택형 split preview, 백링크/앞링크/목차 패널, 그래프 뷰, 글로벌 sync indicator, 커맨드 팔레트(⌘P), Quick Switcher(⌘K)를 갖춘 Obsidian 스타일 레이아웃입니다.
- **파일 관리**: 탐색기 툴바(새 문서/폴더, 정렬, 펼치기/접기, 현재 문서 reveal), 데스크톱/모바일 독립 스크롤, 드래그 앤 드롭 이동, 이동 시 위키링크 재작성 옵션을 지원합니다.
- **관리 UI**: 첫 로그인 후 강제 credential 변경, `/settings/profile|sync|vault|appearance|system` 관리 화면, 서버 기본 테마 프리셋, 한국어/영어 UI 전환을 제공합니다.
- **검색**: PostgreSQL `tsvector` + `pg_trgm` 하이브리드 검색(한/영)과 그래프/링크 패널/명령 팔레트가 같은 문서 라우팅 모델을 공유합니다.

## 기술 스택

- **Frontend**: SvelteKit 5 (runes) · TypeScript · CodeMirror 6 · d3
- **Backend**: Python 3.12 · FastAPI (async) · SQLAlchemy 2.0 · pydantic v2
- **DB / Cache**: PostgreSQL 16 · Redis 7
- **Auth**: JWT (access 15분 / refresh 7일) + bcrypt
- **세션 보안**: access token 은 session storage, refresh token 은 `httpOnly` 쿠키로 처리
- **Sync**: Git 또는 WebDAV
- **Deploy**: Docker Compose

아키텍처와 데이터 흐름은 [`llm-docs/ARCHITECTURE.md`](llm-docs/ARCHITECTURE.md) 에 정리되어 있습니다.

## 빠른 시작

### 필요한 것

- Docker + Docker Compose
- Vault 를 담을 원격 저장소
- Git backend 사용 시 원격 Git 리포지토리 (예: private GitHub repo)와 SSH 키
- WebDAV backend 사용 시 WebDAV URL / 계정 정보

### 저장소 범위

- 이 저장소는 public 으로 공개 가능한 범위를 유지하는 것을 전제로 합니다. 애플리케이션 소스, 배포 파일, 프로젝트 문서는 여기에 둡니다.
- 실제 vault 내용, `.env`, SSH 키, 런타임 볼륨 데이터는 Git 에 올리지 말고 비공개로 유지하세요.
- [`frontend/static/fonts/`](frontend/static/fonts/) 아래의 번들 폰트는 제3자 자산이며, 루트 라이선스와 별도로 upstream 라이선스 조건을 따릅니다.

### 1. 배포 파일 받기

```bash
mkdir -p obsidian-wiki && cd obsidian-wiki
wget https://raw.githubusercontent.com/kw-lee/obsidian-wiki/main/deploy/.env.example -O .env
wget https://raw.githubusercontent.com/kw-lee/obsidian-wiki/main/deploy/docker-compose.yml -O docker-compose.yml
wget https://raw.githubusercontent.com/kw-lee/obsidian-wiki/main/deploy/nginx.conf -O nginx.conf
wget https://raw.githubusercontent.com/kw-lee/obsidian-wiki/main/deploy/init.sql -O init.sql
mkdir -p config/ssh
```

### 2. 환경 변수 설정

`.env` 편집:

```ini
APP_ENV=production
POSTGRES_PASSWORD=...                         # 8자 이상 강한 값
JWT_SECRET=$(openssl rand -hex 32)            # 32자 이상, 반드시 교체
INIT_ADMIN_USERNAME=admin                     # 최초 관리자 계정 (최초 로그인 후 강제 변경됨)
INIT_ADMIN_PASSWORD=...                       # 12자 이상 강한 값
CORS_ALLOWED_ORIGINS=https://wiki.example.com # 쉼표로 여러 origin 지정 가능
```

동기화 설정은 첫 로그인 후 **`/settings/sync`** 에서 관리합니다. 여기서 Git / WebDAV / 비활성화 중 하나를 고르고, 연결 테스트와 수동 pull/push, sync 상태 확인까지 할 수 있습니다. 필요하면 `.env` 에 `GIT_REMOTE_URL`, `GIT_BRANCH`, `GIT_SYNC_INTERVAL_SECONDS` 를 임시로 넣어 첫 `app_settings` 레코드의 Git 초기값만 시드할 수 있습니다. 서버 기본 테마와 언어 관련 기본 동작은 **`/settings/appearance`** 에서, 상태 확인과 인덱스 재생성은 **`/settings/vault`** / **`/settings/system`** 에서 관리합니다.

### 2. GHCR 이미지 지정

`.env` 에 앱 이미지 태그를 추가:

```ini
BACKEND_IMAGE=ghcr.io/kw-lee/obsidian-wiki-backend:latest
FRONTEND_IMAGE=ghcr.io/kw-lee/obsidian-wiki-frontend:latest
```

GHCR 이미지는 공개되어 있으므로 별도 로그인 없이 바로 pull 할 수 있습니다.

Git backend 를 쓸 계획이면 SSH 키도 같이 넣어두세요.

```bash
cp ~/.ssh/id_ed25519 config/ssh/
cp ~/.ssh/known_hosts config/ssh/
```

### 3. 실행

```bash
docker compose pull
docker compose up -d
docker compose exec backend alembic upgrade head
```

브라우저에서 **`http://localhost:${WEB_PORT}`** (기본 80) 접속 → `INIT_ADMIN_*` 로 로그인

> `BACKEND_PORT` / `FRONTEND_PORT` 는 nginx 를 거치지 않는 직접 접근용(디버그)입니다. 실제 사용 진입점은 `WEB_PORT` 입니다. 로그인 후에는 **강제 credential 변경 페이지** (`/auth/setup`) 에서 새 username/password 를 지정하고, 필요하면 **설정 페이지** (`/settings/profile`, `/settings/sync`, `/settings/appearance`, `/settings/system`) 에서 계정/동기화/기본 테마/서버 상태를 확인하고 조정합니다.

### 4. 소스 빌드 방식이 필요할 때

서버에서 직접 빌드하고 싶다면 기존 compose 흐름도 그대로 쓸 수 있습니다.

```bash
make build
make up
make migrate
```

### 5. DB 마이그레이션 (스키마 변경 시)

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

자세한 내용은 [`llm-docs/TESTING.md`](llm-docs/TESTING.md) 참고.

## 배포

nginx reverse proxy + HTTPS 템플릿 포함. Docker 빌드/배포 가이드는 [`llm-docs/DOCKER.md`](llm-docs/DOCKER.md) 참고.

기본 배포 경로는 GitHub Container Registry (`ghcr.io`) 기반입니다. 이 저장소에는 [`.github/workflows/publish-ghcr.yml`](.github/workflows/publish-ghcr.yml) 워크플로와 [`deploy/`](deploy/) 배포 파일셋이 포함되어 있어, GitHub Actions 가 `backend` / `frontend` 이미지를 GHCR 로 푸시하고 서버는 `wget` 으로 배포 파일만 내려받아 바로 실행할 수 있습니다.

```bash
wget https://raw.githubusercontent.com/kw-lee/obsidian-wiki/main/deploy/docker-compose.yml -O docker-compose.yml
docker compose up -d
```

실행 전에 `.env` 에 `BACKEND_IMAGE`, `FRONTEND_IMAGE` 를 원하는 GHCR 태그로 넣어두면, 서버는 소스 체크아웃 없이 앱 이미지를 직접 pull 합니다. 서버 빌드가 필요하면 저장소를 clone 한 뒤 루트 `docker-compose.yml` 기반 흐름으로 돌아갈 수 있습니다.

퍼시스턴트 볼륨 3개:

- `db_data` — PostgreSQL 데이터
- `vault_data` — Git 클론 또는 WebDAV 미러 vault
- `config_data` — 기타 서버 설정

## 주요 단축키

| 키   | 동작                                            |
| ---- | ----------------------------------------------- |
| `⌘K` | Quick Switcher (파일 빠른 이동)                 |
| `⌘P` | 커맨드 팔레트 (새 문서, Git sync, 테마 전환 등) |
| `⌘S` | 편집 중 문서 저장                               |

## 문서

문서 언어 정책:

- `README.md` 는 기본 사용자 안내 문서이며 한국어로 유지합니다.
- `README.en.md` 는 영어 사용자 안내 문서입니다.
- `llm-docs/` 는 구현/설계 참조 문서이므로 영어만 사용합니다.
- Agent 대상 문서는 사람과 LLM 도구가 같은 규칙을 따르도록 의도적으로 버전 관리합니다.
- 서드파티 의존성과 자산의 고지 사항은 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) 에 정리합니다.

- [`AGENTS.md`](AGENTS.md) — 프로젝트 전반 규칙 (Claude/Codex 공통)
- [`CLAUDE.md`](CLAUDE.md) — Claude용 포인터 문서
- [`CODEX.md`](CODEX.md) — Codex용 포인터 문서
- [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) — 직접 의존성 버전과 서드파티 라이선스 메모
- [`llm-docs/ARCHITECTURE.md`](llm-docs/ARCHITECTURE.md) — 시스템 아키텍처 / 기술 결정
- [`llm-docs/CONVENTIONS.md`](llm-docs/CONVENTIONS.md) — 코드 스타일 / Git / CI
- [`llm-docs/SETTINGS.md`](llm-docs/SETTINGS.md) — 관리자 설정 화면 / 런타임 설정
- [`llm-docs/SECURITY.md`](llm-docs/SECURITY.md) — 보안 점검 / 하드닝 우선순위
- [`llm-docs/DOCKER.md`](llm-docs/DOCKER.md) — Docker 빌드·배포
- [`llm-docs/TESTING.md`](llm-docs/TESTING.md) — 테스트 가이드
- [`llm-docs/PROGRESS.md`](llm-docs/PROGRESS.md) — 구현 진행 상황

## Upstream 의존성과 라이선스

- 직접 사용하는 주요 upstream 프로젝트로는 SvelteKit, Svelte, CodeMirror, d3, KaTeX, Marked, FastAPI, Pydantic, SQLAlchemy, Alembic, Uvicorn, HTTPX, GitPython 등이 있습니다.
- 락파일 기준으로 확인한 직접 의존성은 모두 `MIT`, `Apache-2.0`, `BSD-3-Clause`, `ISC` 같은 permissive 라이선스에 속합니다. 이번 직접 의존성 점검 범위에서는 `GPL`, `LGPL`, `AGPL` 계열은 발견되지 않았습니다.
- [`frontend/static/fonts/`](frontend/static/fonts/) 아래의 번들 폰트 자산은 저장소 루트 라이선스와 별도의 조건을 따릅니다.
- 정확한 직접 의존성 버전과 라이선스 메모는 [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) 를 참고하세요.

## 면책 고지

본 프로그램은 전체 또는 일부가 대규모 언어 모델(LLM)의 도움을 받아 작성되었습니다. 이 소프트웨어의 사용, 수정, 배포, 운영 과정에서 발생할 수 있는 버그, 오동작, 보안 문제, 데이터 손실 및 기타 모든 문제에 대해 저자와 기여자는 책임을 지지 않습니다. 코드를 검토하고 동작을 검증하며, 자신의 환경에 안전하고 적합한지 판단할 책임은 전적으로 사용자에게 있습니다.

## 라이선스

프로젝트 소스코드와 프로젝트 작성 문서는 [MIT License](LICENSE) (`MIT`) 로 배포합니다.

[`frontend/static/fonts/`](frontend/static/fonts/) 아래의 번들 폰트 자산은 저장소 루트 `MIT` 고지로 재라이선스되지 않으며, 각 upstream 라이선스 조건을 그대로 따릅니다. 자세한 내용은 [`frontend/static/fonts/README.md`](frontend/static/fonts/README.md) 를 참고하세요.
