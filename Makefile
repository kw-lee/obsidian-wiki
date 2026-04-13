.PHONY: build up down dev logs test test-backend test-frontend clean lint migrate shell-backend shell-frontend restart status rebuild rebuild-dev

# ── Build ────────────────────────────────────────────
build:
	docker compose down 
	docker compose build
	docker compose up -d

build-no-cache:
	docker compose down
	docker compose build --no-cache
	docker compose up -d

# 볼륨/컨테이너 모두 제거하고 no-cache 로 재빌드 후 기동 (완전 초기화)
rebuild:
	docker compose down -v --remove-orphans
	docker compose build --no-cache
	docker compose up -d

rebuild-dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml down -v --remove-orphans
	docker compose -f docker-compose.yml -f docker-compose.dev.yml build --no-cache
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

# ── Run ──────────────────────────────────────────────
up:
	docker compose up -d

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

down:
	docker compose down

restart:
	docker compose restart

status:
	docker compose ps

logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-frontend:
	docker compose logs -f frontend

# ── Test ─────────────────────────────────────────────
test:
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit

test-backend:
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit backend-test

test-frontend:
	docker compose -f docker-compose.test.yml up --build --abort-on-container-exit frontend-test

test-backend-local:
	cd backend && python -m pytest -v --tb=short

test-frontend-local:
	cd frontend && npx vitest run

test-clean:
	docker compose -f docker-compose.test.yml down -v --remove-orphans

# ── Lint ─────────────────────────────────────────────
lint:
	cd backend && ruff check . && ruff format --check .
	cd frontend && npx prettier --check "src/**/*.{ts,svelte}" && npx svelte-check

lint-fix:
	cd backend && ruff check --fix . && ruff format .
	cd frontend && npx prettier --write "src/**/*.{ts,svelte}"

# ── Database ─────────────────────────────────────────
migrate:
	docker compose exec backend alembic upgrade head

migrate-generate:
	docker compose exec backend alembic revision --autogenerate -m "$(msg)"

# ── Shell ────────────────────────────────────────────
shell-backend:
	docker compose exec backend bash

shell-frontend:
	docker compose exec frontend sh

shell-db:
	docker compose exec db psql -U $${POSTGRES_USER:-obsidian} -d $${POSTGRES_DB:-obsidian_wiki}

# ── Clean ────────────────────────────────────────────
clean:
	docker compose down -v --remove-orphans
	docker compose -f docker-compose.test.yml down -v --remove-orphans

prune:
	docker system prune -f
	docker volume prune -f
