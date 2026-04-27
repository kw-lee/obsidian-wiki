FROM python:3.12-slim AS base

RUN apt-get update && \
    apt-get install -y --no-install-recommends git openssh-client && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY . .
RUN chmod +x /app/docker/entrypoint.sh

ENTRYPOINT ["/app/docker/entrypoint.sh"]

# ── Development ───────────────────────────────────────
FROM base AS dev
RUN pip install --no-cache-dir \
    "pytest>=8,<9" \
    "pytest-asyncio>=0.24,<1" \
    "aiosqlite>=0.20,<1" \
    "ruff>=0.8,<1"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── Production ────────────────────────────────────────
FROM base AS prod
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
