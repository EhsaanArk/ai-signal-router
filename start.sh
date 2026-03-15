#!/bin/sh
set -e

echo "Running Alembic migrations..."
if alembic upgrade head 2>&1; then
    echo "Migrations applied successfully."
else
    echo "Migration failed — stamping current DB at head and retrying..."
    alembic stamp head
    alembic upgrade head
    echo "Migrations applied after stamping."
fi

echo "Starting uvicorn..."
exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}"
