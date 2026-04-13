#!/bin/sh
set -eu

PYTHONPATH=/app python /app/scripts/bootstrap_alembic.py
python -m alembic upgrade head

exec "$@"
