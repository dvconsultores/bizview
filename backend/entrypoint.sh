#!/bin/sh
# With arguments: run that command (e.g. `python -m app.cli reset-superuser-password`).
# Without: migrate the app schema, ensure the super user exists, then serve.
set -e
if [ "$#" -gt 0 ]; then
  exec "$@"
fi
if ! out=$(alembic upgrade head 2>&1); then
  printf '%s\n' "$out" >&2
  case "$out" in
    *"Can't locate revision"*)
      echo "bizview: this image is OLDER than the database." >&2
      echo "bizview: the database was migrated by a newer release, so this version of the app cannot" >&2
      echo "bizview: start. Fix it by running the matching (newer) images, e.g. pull the tag that" >&2
      echo "bizview: migrated it, or restore a database backup taken before that upgrade." >&2
      echo "bizview: never run 'alembic upgrade' from a workstation against an installation's database." >&2
      ;;
  esac
  exit 1
fi
python -m app.cli bootstrap
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-2}" \
  --proxy-headers --forwarded-allow-ips='*' --no-server-header
