#!/bin/sh
# Gate 7/8 (046): one version, one truth.
#
# `VERSION` at the repository root is the only place a human edits the number. Every other copy has
# to equal it, and a reachable backend has to report it. Fails listing what disagrees.
#
# The copies: the backend package, the frontend package, the CLI package and the CLI's own
# `__version__` (the CLI installs standalone, so it cannot read this file at runtime).
set -eu
cd "$(dirname "$0")/../.."

PY=${PY:-$(pwd)/.venv/bin/python}
[ -x "$PY" ] || PY=python3

[ -s VERSION ] || { echo "VERSION is missing or empty" >&2; exit 1; }
want=$(tr -d '[:space:]' < VERSION)

fail=0
report() {   # path, found
  printf '  %-38s %s\n' "$1" "$2"
  if [ "$2" != "$want" ]; then
    echo "    ↑ disagrees with VERSION ($want)" >&2
    fail=1
  fi
}

printf 'VERSION is %s\n' "$want"
report "VERSION" "$want"
report "backend/pyproject.toml" \
  "$(sed -n 's/^version = "\(.*\)"$/\1/p' backend/pyproject.toml | head -1)"
report "frontend/package.json" "$(sed -n 's/^  "version": "\(.*\)",$/\1/p' frontend/package.json)"
report "cli/pyproject.toml" \
  "$(sed -n 's/^version = "\(.*\)"$/\1/p' cli/pyproject.toml | head -1)"
report "cli/bizview_cli/__init__.py" \
  "$(sed -n 's/^__version__ = "\(.*\)"$/\1/p' cli/bizview_cli/__init__.py)"

# The running product, when there is one to ask. Without a backend the file half above is all there
# is, and saying so is better than pretending the check covered it.
url=${BIZVIEW_HEALTH_URL:-http://127.0.0.1:8081/api/health}
if command -v curl >/dev/null 2>&1 && curl -fsS --max-time 3 "$url" >/tmp/bizview-health.json 2>/dev/null
then
  running=$("$PY" - <<'PY'
import json
try:
    print(json.load(open("/tmp/bizview-health.json")).get("version") or "")
except Exception:
    print("")
PY
)
  report "/api/health ($url)" "$running"
  rm -f /tmp/bizview-health.json
else
  printf '  %-38s %s\n' "/api/health" "skipped (no backend at $url)"
fi

[ "$fail" = 0 ] || { echo "the version copies disagree (046)" >&2; exit 1; }
printf 'ok\n'
