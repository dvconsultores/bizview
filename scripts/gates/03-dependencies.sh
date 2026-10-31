#!/bin/sh
# Gate 3/6 (045): nothing installed that nothing imports, nothing imported that is not declared.
#
# Backend: `deptry` DEP001 (imported but undeclared) and DEP002 (declared but unused). DEP003
# ("imported through a transitive dependency": yaml, sqlglot, starlette, httpcore) is pre-existing
# and stays out of this gate; making it pass is a separate change with its own risk.
# Frontend: every runtime and dev dependency must be imported somewhere in `src/` or `tests/`,
# except the ones a config file names instead of a module.
set -eu
cd "$(dirname "$0")/../.."

PY=${PY:-$(pwd)/.venv/bin/python}
[ -x "$PY" ] || PY=python3

# Packages a config entrypoint uses without importing: the ASGI server, the type packages,
# the Vite plugin and the CSS pipeline.
TOOLING="uvicorn|@types/react|@types/react-dom|@vitejs/plugin-react|autoprefixer|jsdom|postcss|tailwindcss|vite"

printf 'backend: declared and used\n'
(cd backend && "$PY" -m deptry . --ignore DEP003 --json-output /tmp/deptry.json >/dev/null 2>&1 || true)
"$PY" - <<'PY'
import json
import re
import sys

try:
    report = json.load(open("/tmp/deptry.json"))
except FileNotFoundError:
    print("deptry produced no report", file=sys.stderr)
    raise SystemExit(1)
allow = re.compile(r"^(uvicorn)$")
bad = [f"{item['module']}: {item['error']['code']} {item['error']['message']}"
       for item in report if not allow.match(str(item.get("module")))]
for line in bad:
    print(line)
raise SystemExit(1 if bad else 0)
PY

printf 'frontend: declared and used\n'
cd frontend
"$PY" - <<'PY'
import json
import pathlib
import re
import sys

TOOLING = {"@types/react", "@types/react-dom", "@vitejs/plugin-react", "autoprefixer", "jsdom",
           "postcss", "tailwindcss", "vite"}
manifest = json.loads(pathlib.Path("package.json").read_text())
declared = list(manifest.get("dependencies", {})) + list(manifest.get("devDependencies", {}))
sources = [p for folder in ("src", "tests")
           for p in pathlib.Path(folder).rglob("*") if p.suffix in (".ts", ".tsx", ".css", ".mjs")]
text = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in sources)
missing = []
for dep in declared:
    if dep in TOOLING:
        continue
    pattern = rf"""(from\s+["']{re.escape(dep)}(/|["'])|require\(\s*["']{re.escape(dep)}|@import\s+["']{re.escape(dep)})"""
    if not re.search(pattern, text):
        missing.append(dep)
for dep in missing:
    print(f"declared but never imported: {dep}")
raise SystemExit(1 if missing else 0)
PY
