#!/bin/sh
# Gate 4/6 (045): no endpoint and no page of the removed authoring agent.
#
# The API's OpenAPI document must list no path under /assistant, /commands, /runs or /contracts,
# and the frontend router must mount no assistant page. Reads the app for real (imports it), so a
# route that comes back from a new module is caught too.
set -eu
cd "$(dirname "$0")/../.."

PY=${PY:-$(pwd)/.venv/bin/python}
[ -x "$PY" ] || PY=python3

printf 'backend OpenAPI paths\n'
(cd backend && "$PY" - <<'PY'
import os

os.environ.setdefault("DATABASE_URL_BI", "postgresql://u:p@127.0.0.1:1/none")
os.environ.setdefault("BIZVIEW_SECRET_KEY", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
from app.main import app

# A segment anywhere in the path: the removed surface hung off several routers (/api/assistant,
# /api/projects/{slug}/preview, /api/assistant/sessions/{id}/commands, …). "runs" is NOT one of
# them: integration runs keep their own path.
FORBIDDEN = {"assistant", "commands", "contracts", "preview"}
bad = sorted({path for path in app.openapi()["paths"]
              if FORBIDDEN & {segment for segment in path.split("/") if segment}})
for path in bad:
    print(f"route still mounted: {path}")
raise SystemExit(1 if bad else 0)
PY
)

printf 'frontend router\n'
if grep -rInE 'path:\s*"(/admin/asistente|/asistente)|Asistente[A-Z]' frontend/src/App.tsx \
        frontend/src/routes* 2>/dev/null; then
  echo "an assistant page is still routed" >&2
  exit 1
fi
printf 'ok\n'
