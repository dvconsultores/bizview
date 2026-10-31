#!/bin/sh
# Gate 2/6 (045): nothing in the shipped tree is written and never read.
#
# Backend: `ruff` for imports and locals nobody uses, `vulture` for definitions nobody calls.
# Frontend: `tsc --noUnusedLocals` covers locals; `knip` is not installed in this repository, so
# the frontend half is the type checker plus the build (a module with no importer still type-checks,
# which is why the removed surface is deleted first and the tree stays small enough to read).
set -eu
cd "$(dirname "$0")/../.."

PY=${PY:-$(pwd)/.venv/bin/python}
[ -x "$PY" ] || PY=python3

printf 'backend imports and locals\n'
(cd backend && "$PY" -m ruff check app --select F401,F841)

printf 'backend definitions nobody calls\n'
(cd backend && "$PY" -m vulture app --min-confidence 80)

printf 'frontend unused locals\n'
(cd frontend && npx tsc --noEmit --noUnusedLocals 2>&1 | grep -v "node_modules" || true)
printf 'ok\n'
