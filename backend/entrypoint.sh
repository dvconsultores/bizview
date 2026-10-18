#!/bin/sh
# With arguments: run that command (e.g. `python -m app.cli reset-superuser-password`).
# Without: migrate the app schema, ensure the super user exists, then serve.
set -e
if [ "$#" -gt 0 ]; then
  exec "$@"
fi
alembic upgrade head
python -m app.cli bootstrap
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-2}" \
  --proxy-headers --forwarded-allow-ips='*' --no-server-header
