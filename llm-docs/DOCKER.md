# Docker Build & Deployment Guide

## Prerequisites

- Docker 24+ and Docker Compose v2
- Git (with SSH key configured — used for vault sync)

## Quick Start

```bash
# 1. Create a deployment directory
mkdir -p obsidian-wiki && cd obsidian-wiki

# 2. Download the self-contained deploy bundle
wget https://raw.githubusercontent.com/kw-lee/obsidian-wiki/main/deploy/.env.example -O .env
wget https://raw.githubusercontent.com/kw-lee/obsidian-wiki/main/deploy/docker-compose.yml -O docker-compose.yml
wget https://raw.githubusercontent.com/kw-lee/obsidian-wiki/main/deploy/nginx.conf -O nginx.conf
wget https://raw.githubusercontent.com/kw-lee/obsidian-wiki/main/deploy/init.sql -O init.sql

# 3. Edit .env: passwords, JWT_SECRET, CORS_ALLOWED_ORIGINS, etc.

# 4. Run
docker compose pull
docker compose up -d
docker compose exec backend alembic upgrade head
```

Open `http://localhost` in a browser.

## Deployment Modes

### 1. Prebuilt app images from GHCR

Use GHCR when you do not want to build `backend` and `frontend` on the server. This is the recommended production path.

This repository ships:

- `.github/workflows/publish-ghcr.yml` — builds and pushes `backend` / `frontend` to `ghcr.io`
- `deploy/docker-compose.yml` — self-contained deploy compose file
- `deploy/nginx.conf` — nginx config for the deploy bundle
- `deploy/init.sql` — Postgres bootstrap SQL for the deploy bundle
- `deploy/.env.example` — production-oriented environment template

Recommended image names:

```text
ghcr.io/kw-lee/obsidian-wiki-backend:latest
ghcr.io/kw-lee/obsidian-wiki-frontend:latest
```

Add these to `.env` on the server:

```ini
BACKEND_IMAGE=ghcr.io/kw-lee/obsidian-wiki-backend:latest
FRONTEND_IMAGE=ghcr.io/kw-lee/obsidian-wiki-frontend:latest
```

Then deploy with:

```bash
docker compose pull
docker compose up -d
docker compose exec backend alembic upgrade head
```

If you use Git sync, also copy the SSH key material mounted by the compose file:

```bash
mkdir -p config/ssh
cp ~/.ssh/id_ed25519 config/ssh/
cp ~/.ssh/known_hosts config/ssh/
```

### 2. Source build on the server

Use the default compose file when the server can clone the repository and build images locally.

```bash
git clone https://github.com/<owner>/obsidian-wiki.git
cd obsidian-wiki
cp .env.example .env
docker compose build
docker compose up -d
docker compose exec backend alembic upgrade head
```

## Architecture

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

## Compose Profiles

| File                      | Purpose                                 |
| ------------------------- | --------------------------------------- |
| `docker-compose.yml`      | Production (default)                    |
| `docker-compose.dev.yml`  | Dev override (hot reload, source mount) |
| `docker-compose.test.yml` | Test (ephemeral DB, auto-exit)          |

## Makefile Commands

### Build & Run

```bash
make build           # Build images
make build-no-cache  # Build without cache
make up              # Run production (background)
make dev             # Run dev mode (foreground, hot reload)
make down            # Stop
make restart         # Restart
make status          # Show container status
```

### Logs

```bash
make logs            # All services
make logs-backend    # Backend only
make logs-frontend   # Frontend only
```

### Tests

```bash
make test              # Full test suite (Docker)
make test-backend      # Backend only (Docker)
make test-frontend     # Frontend only (Docker)
make test-backend-local  # Local backend tests
make test-frontend-local # Local frontend tests
make test-clean        # Remove test containers
```

### Database

```bash
make migrate              # Apply Alembic migrations
make migrate-generate msg="add column"  # Generate a migration
make shell-db             # psql shell
```

### Shell Access

```bash
make shell-backend   # bash into backend container
make shell-frontend  # sh into frontend container
```

### Cleanup

```bash
make clean   # Remove all containers + volumes
make prune   # Docker system prune
```

## Environment Variables (.env)

| Variable               | Description                  | Default                |
| ---------------------- | ---------------------------- | ---------------------- |
| `POSTGRES_USER`        | DB user                      | `obsidian`             |
| `POSTGRES_PASSWORD`    | DB password                  | `changeme`             |
| `POSTGRES_DB`          | DB name                      | `obsidian_wiki`        |
| `DATABASE_URL`         | SQLAlchemy connection string | (auto-generated)       |
| `REDIS_URL`            | Redis connection             | `redis://redis:6379/0` |
| `JWT_SECRET`           | JWT signing key              | (must change)          |
| `INIT_ADMIN_USERNAME`  | Initial admin username       | `admin`                |
| `INIT_ADMIN_PASSWORD`  | Initial admin password       | (must change)          |
| `APP_ENV`              | Runtime environment          | `development`          |
| `CORS_ALLOWED_ORIGINS` | Allowed browser origins      | (empty)                |
| `APP_TIMEZONE`         | App / container timezone     | `Asia/Seoul`           |
| `VAULT_LOCAL_PATH`     | Vault path inside container  | `/data/vault`          |
| `WEB_PORT`             | Host port (nginx entrypoint) | `80`                   |
| `BACKEND_PORT`         | Host port (backend)          | `8000`                 |
| `FRONTEND_PORT`        | Host port (frontend)         | `3000`                 |
| `BACKEND_IMAGE`        | Optional GHCR backend image  | (unset)                |
| `FRONTEND_IMAGE`       | Optional GHCR frontend image | (unset)                |

### Generate Password Hash

```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PASSWORD', bcrypt.gensalt()).decode())"
```

### Generate JWT Secret

```bash
openssl rand -hex 32
```

## Dev Mode

```bash
make dev
```

- Backend: `--reload` (auto-restart on source change)
- Frontend: Vite HMR (port 24678)
- Source directories are bind-mounted into the containers

## Production Deployment

### 1. Configure Environment

```bash
cp .env.example .env
# Change every secret (JWT_SECRET, INIT_ADMIN_PASSWORD, POSTGRES_PASSWORD)
```

### 2. HTTPS Setup (optional)

Uncomment the HTTPS section in `nginx/nginx.conf`, then:

```bash
# Issue a Let's Encrypt certificate
docker run --rm -v ./certbot/conf:/etc/letsencrypt \
  -v ./certbot/www:/var/www/certbot \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  -d your-domain.com

# Uncomment the certbot volume mounts in docker-compose.yml
```

### 3. Deploy

```bash
make build
make up
make migrate  # DB migrations
```

For GHCR-based deployment, replace the build step with:

```bash
docker compose pull
docker compose up -d
docker compose exec backend alembic upgrade head
```

### 4. Verify

```bash
make status
curl http://localhost/health  # {"status": "ok"}
```

## Docker Image Details

### GHCR publishing

The GitHub Actions workflow publishes two application images:

- `ghcr.io/kw-lee/obsidian-wiki-backend`
- `ghcr.io/kw-lee/obsidian-wiki-frontend`

Publishing triggers:

- push to `main`
- Git tag matching `v*`
- manual `workflow_dispatch`

Generated tags include:

- branch name
- git tag
- commit SHA
- `latest` on the default branch

### Backend (Python 3.12-slim)

- Multi-stage: `base` → `dev` / `prod`
- `dev`: uvicorn `--reload`
- `prod`: uvicorn `--workers 2`
- Includes Git and SSH client (for vault sync)

### Frontend (Node 20-alpine)

- Multi-stage: `deps` → `dev` / `build` → `prod`
- `dev`: Vite dev server + HMR
- `prod`: SvelteKit Node adapter (`node build`)

### Nginx (alpine)

- Reverse proxy: `/api/*` → backend, `/*` → frontend
- WebSocket upgrade supported
- Client upload limit: 50MB

## Volumes

| Volume        | Purpose                   | Needs Backup     |
| ------------- | ------------------------- | ---------------- |
| `db_data`     | PostgreSQL data           | Yes              |
| `vault_data`  | Obsidian vault (git repo) | Yes (git remote) |
| `config_data` | App configuration         | Yes              |

### Volume Backup

```bash
# DB backup
docker compose exec db pg_dump -U obsidian obsidian_wiki > backup.sql

# DB restore
cat backup.sql | docker compose exec -T db psql -U obsidian obsidian_wiki
```

## Troubleshooting

### Containers Fail to Start

```bash
make logs           # Check logs
make status         # Check status
docker compose exec db pg_isready -U obsidian  # DB healthcheck
docker compose exec redis redis-cli ping       # Redis healthcheck
```

### Git Sync Failures

```bash
make shell-backend
cd /data/vault
git remote -v       # Check remote
git status          # Check state
ssh -T git@github.com  # Test SSH connectivity
```

### Reset the DB

```bash
make clean          # Remove volumes
make up             # Restart (re-runs init.sql)
```
