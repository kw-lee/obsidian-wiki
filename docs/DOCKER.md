# Docker 빌드 & 배포 가이드

## 사전 요구사항

- Docker 24+ & Docker Compose v2
- Git (SSH 키 설정 — vault 동기화용)

## 빠른 시작

```bash
# 1. 환경 변수 설정
cp .env.example .env
# .env 파일을 열어 비밀번호, JWT_SECRET, GIT_REMOTE_URL 등 수정

# 2. SSH 키 설정 (Git 동기화용)
mkdir -p config/ssh
cp ~/.ssh/id_ed25519 config/ssh/
cp ~/.ssh/known_hosts config/ssh/

# 3. 빌드 & 실행
make build
make up
```

브라우저에서 `http://localhost` 접속.

## 아키텍처

```
┌─────────────────────────────────────────────┐
│  nginx:80/443                               │
│  ├─ /api/*  → backend:8000                  │
│  └─ /*      → frontend:3000                 │
├─────────────────────────────────────────────┤
│  frontend:3000  (SvelteKit, Node 20)        │
│  backend:8000   (FastAPI, Python 3.12)      │
├─────────────────────────────────────────────┤
│  postgres:5432  │  redis:6379               │
│  PV: db_data    │  (in-memory, no persist)  │
└─────────────────────────────────────────────┘
  PV: vault_data (git repo), config_data
```

## Compose 프로파일

| 파일 | 용도 |
|------|------|
| `docker-compose.yml` | 프로덕션 (기본) |
| `docker-compose.dev.yml` | 개발 오버라이드 (hot reload, 소스 마운트) |
| `docker-compose.test.yml` | 테스트 (임시 DB, 자동 종료) |

## Makefile 커맨드

### 빌드 & 실행

```bash
make build           # 이미지 빌드
make build-no-cache  # 캐시 없이 빌드
make up              # 프로덕션 실행 (백그라운드)
make dev             # 개발 모드 실행 (포그라운드, hot reload)
make down            # 중지
make restart         # 재시작
make status          # 컨테이너 상태 확인
```

### 로그

```bash
make logs            # 전체 로그
make logs-backend    # 백엔드만
make logs-frontend   # 프론트엔드만
```

### 테스트

```bash
make test              # 전체 테스트 (Docker)
make test-backend      # 백엔드만 (Docker)
make test-frontend     # 프론트엔드만 (Docker)
make test-backend-local  # 로컬 백엔드 테스트
make test-frontend-local # 로컬 프론트엔드 테스트
make test-clean        # 테스트 컨테이너 정리
```

### 데이터베이스

```bash
make migrate              # Alembic 마이그레이션 적용
make migrate-generate msg="add column"  # 마이그레이션 생성
make shell-db             # psql 접속
```

### 셸 접속

```bash
make shell-backend   # 백엔드 컨테이너 bash
make shell-frontend  # 프론트엔드 컨테이너 sh
```

### 정리

```bash
make clean   # 모든 컨테이너+볼륨 삭제
make prune   # Docker 시스템 정리
```

## 환경 변수 (.env)

| 변수 | 설명 | 기본값 |
|------|------|--------|
| `POSTGRES_USER` | DB 사용자 | `obsidian` |
| `POSTGRES_PASSWORD` | DB 비밀번호 | `changeme` |
| `POSTGRES_DB` | DB 이름 | `obsidian_wiki` |
| `DATABASE_URL` | SQLAlchemy 연결 문자열 | (자동 생성) |
| `REDIS_URL` | Redis 연결 | `redis://redis:6379/0` |
| `JWT_SECRET` | JWT 서명 키 | (필수 변경) |
| `ADMIN_USERNAME` | 관리자 ID | `admin` |
| `ADMIN_PASSWORD_HASH` | bcrypt 해시 | (필수 변경) |
| `GIT_REMOTE_URL` | Vault Git 리모트 | (필수 설정) |
| `GIT_BRANCH` | Git 브랜치 | `main` |
| `GIT_SYNC_INTERVAL_SECONDS` | 동기화 주기 (초) | `300` |
| `VAULT_LOCAL_PATH` | 컨테이너 내 vault 경로 | `/data/vault` |
| `BACKEND_PORT` | 호스트 포트 (백엔드) | `8000` |
| `FRONTEND_PORT` | 호스트 포트 (프론트엔드) | `3000` |

### 비밀번호 해시 생성

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PASSWORD', bcrypt.gensalt()).decode())"
```

### JWT Secret 생성

```bash
openssl rand -hex 32
```

## 개발 모드

```bash
make dev
```

- 백엔드: `--reload` (소스 변경 시 자동 재시작)
- 프론트엔드: Vite HMR (포트 24678)
- 소스 디렉토리가 컨테이너에 마운트됨

## 프로덕션 배포

### 1. 환경 설정

```bash
cp .env.example .env
# 모든 비밀값 수정 (JWT_SECRET, ADMIN_PASSWORD_HASH, POSTGRES_PASSWORD)
```

### 2. HTTPS 설정 (선택)

`nginx/nginx.conf`에서 HTTPS 섹션 주석 해제 후:

```bash
# Let's Encrypt 인증서 발급
docker run --rm -v ./certbot/conf:/etc/letsencrypt \
  -v ./certbot/www:/var/www/certbot \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  -d your-domain.com

# docker-compose.yml에서 certbot 볼륨 마운트 주석 해제
```

### 3. 배포

```bash
make build
make up
make migrate  # DB 마이그레이션
```

### 4. 상태 확인

```bash
make status
curl http://localhost/health  # {"status": "ok"}
```

## Docker 이미지 상세

### Backend (Python 3.12-slim)

- Multi-stage: `base` → `dev` / `prod`
- `dev`: uvicorn `--reload`
- `prod`: uvicorn `--workers 2`
- Git, SSH client 포함 (vault 동기화용)

### Frontend (Node 20-alpine)

- Multi-stage: `deps` → `dev` / `build` → `prod`
- `dev`: Vite dev server + HMR
- `prod`: SvelteKit Node adapter (`node build`)

### Nginx (alpine)

- 리버스 프록시: `/api/*` → backend, `/*` → frontend
- WebSocket 업그레이드 지원
- 클라이언트 업로드 50MB

## 볼륨

| 볼륨 | 용도 | 백업 필요 |
|------|------|-----------|
| `db_data` | PostgreSQL 데이터 | O |
| `vault_data` | Obsidian vault (git repo) | O (git remote) |
| `config_data` | 앱 설정 | O |

### 볼륨 백업

```bash
# DB 백업
docker compose exec db pg_dump -U obsidian obsidian_wiki > backup.sql

# DB 복원
cat backup.sql | docker compose exec -T db psql -U obsidian obsidian_wiki
```

## 트러블슈팅

### 컨테이너가 시작되지 않을 때

```bash
make logs           # 로그 확인
make status         # 상태 확인
docker compose exec db pg_isready -U obsidian  # DB 헬스체크
docker compose exec redis redis-cli ping       # Redis 헬스체크
```

### Git 동기화 실패

```bash
make shell-backend
cd /data/vault
git remote -v       # 리모트 확인
git status          # 상태 확인
ssh -T git@github.com  # SSH 연결 테스트
```

### DB 초기화

```bash
make clean          # 볼륨 삭제
make up             # 재시작 (init.sql 재실행)
```
