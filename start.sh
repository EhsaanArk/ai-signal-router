#!/bin/sh
set -e

SERVICE_ROLE="${SERVICE_ROLE:-api}"
echo "Service role: ${SERVICE_ROLE}"

case "$SERVICE_ROLE" in
  api)
    echo "Running Alembic migrations..."
    # Check for multiple heads before attempting upgrade — multiple heads means
    # a migration conflict exists in the codebase and must be fixed in code, not
    # worked around at runtime.
    HEAD_COUNT=$(alembic heads 2>&1 | grep -c "(head)" || true)
    if [ "$HEAD_COUNT" -gt 1 ]; then
        echo "ERROR: Alembic detected multiple migration heads (${HEAD_COUNT}). This is a code conflict that must be resolved before deploying. Aborting startup."
        exit 1
    fi
    if alembic upgrade head 2>&1; then
        echo "Migrations applied successfully."
    else
        echo "Migration failed — stamping current DB at head and retrying..."
        alembic stamp head
        alembic upgrade head
        echo "Migrations applied after stamping."
    fi

    echo "Starting API server..."
    exec uvicorn src.main:app --host 0.0.0.0 --port "${PORT:-8000}"
    ;;

  listener)
    echo "Starting Telegram listener..."
    exec python -m src.adapters.telegram.listener
    ;;

  *)
    echo "Unknown SERVICE_ROLE: ${SERVICE_ROLE}. Must be 'api' or 'listener'."
    exit 1
    ;;
esac
