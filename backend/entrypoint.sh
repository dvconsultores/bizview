#!/bin/sh
# With arguments: run that command (e.g. `python -m app.cli reset-superuser-password`).
# Without: migrate the app schema, ensure the super user exists, then serve.
set -e
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

# A file copied into the image without permission for this user (an image built from a tree written
# with a restrictive umask) makes Alembic fail with a long traceback that hides the cause, and the API
# would fail next. Say what it is and what fixes it, before either of them starts.
if ! python -c '
import pathlib, sys

bad = []
for root in (pathlib.Path("."), pathlib.Path("/app/cli"), pathlib.Path("/app/pack")):
    if not root.exists():
        continue
    for path in root.rglob("*.py"):
        try:
            path.read_bytes()
        except OSError:
            bad.append(str(path))
if bad:
    print("bizview: this image cannot read its own code: " + bad[0], file=sys.stderr)
    print("bizview: it was built from a tree whose files were not readable by this user (umask).",
          file=sys.stderr)
    print("bizview: rebuild the backend image and recreate the container; a fresh build fixes it.",
          file=sys.stderr)
    raise SystemExit(1)
'; then
  exit 1
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
    *"Permission denied"*)
      echo "bizview: this image cannot read its own files (a build-context permission problem)." >&2
      echo "bizview: rebuild the backend image and recreate the container; a fresh build fixes it." >&2
      ;;
  esac
  exit 1
fi
python -m app.cli bootstrap
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers "${WEB_CONCURRENCY:-2}" \
  --proxy-headers --forwarded-allow-ips='*' --no-server-header
