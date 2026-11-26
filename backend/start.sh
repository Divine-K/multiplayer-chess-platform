#!/bin/sh
# Production entry point: bring the schema up to date, then serve.
set -eu

alembic upgrade head

# One process only: live game connections are held in memory (see docs/WEBSOCKET_PROTOCOL.md).
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
