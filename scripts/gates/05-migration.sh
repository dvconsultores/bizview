#!/bin/sh
# Gate 5/6 (045): a seeded database upgrades, nothing applied is lost, the tables are gone.
#
# What it proves, against DATABASE_URL_BI (a database you may throw away):
#   1. upgrade to the revision before 0041 and seed two applied conversations, one whose spec
#      folder is not in its project and one whose project already has it;
#   2. `alembic upgrade head`: the rescue copies the missing documents and verifies their hashes;
#   3. every applied spec folder exists afterwards, byte for byte;
#   4. the seven assistant tables and the revision's assistant columns are gone;
#   5. a second `upgrade head` is a no-op and still leaves the files in place (idempotent).
#
# Downgrade is NOT exercised: it recreates empty tables and cannot restore rows. Recovery is the
# backup taken before the upgrade (docs/INSTALL.md, «Copias de seguridad»).
set -eu
cd "$(dirname "$0")/../.."

if [ -z "${DATABASE_URL_BI:-}" ]; then
  echo "DATABASE_URL_BI is not set: this gate needs a disposable database" >&2
  exit 2
fi

PY=${PY:-$(pwd)/.venv/bin/python}
[ -x "$PY" ] || PY=python3
export PROJECTS_DIR=$(mktemp -d)
export DB_SCHEMA=${DB_SCHEMA:-app_test_gate045}   # a throwaway test schema, never the installation's own
trap 'rm -rf "$PROJECTS_DIR"' EXIT

cd backend
"$PY" - "$PROJECTS_DIR" <<'PY'
import json
import os
import pathlib
import subprocess
import sys

from sqlalchemy import create_engine, text

projects = pathlib.Path(os.environ["PROJECTS_DIR"])
schema = os.environ.get("DB_SCHEMA", "public")
engine = create_engine(os.environ["DATABASE_URL_BI"])


def alembic(*args):
    subprocess.run([sys.executable, "-m", "alembic", *args], check=True)


def sql(statement, **params):
    """One statement inside the gate's own schema: never the installation's public one."""
    with engine.begin() as conn:
        conn.execute(text(f"SET LOCAL search_path TO {schema}"))
        result = conn.execute(text(statement), params)
        return result.fetchall() if result.returns_rows else []


alembic("upgrade", "0043_image_cache")

slug = "gate-045"
folder = projects / slug
(folder / "specs" / "001-ya-esta").mkdir(parents=True, exist_ok=True)
(folder / "specs" / "001-ya-esta" / "spec.md").write_text("# vieja\n", encoding="utf-8")

sql("DELETE FROM project WHERE slug = :s", s=slug)
pid = sql("INSERT INTO project (slug, name, origin) VALUES (:s, 'Gate 045', 'app') "
          "RETURNING id", s=slug)[0][0]
draft_missing = {"files": {"specs/002-rescatada/spec.md": "# rescatada\n",
                           "specs/002-rescatada/plan.md": "# plan\n",
                           "integrations/x/integration.yaml": "id: x\n"}}
draft_present = {"files": {"specs/001-ya-esta/spec.md": "# nueva\n"}}
uid = sql("SELECT id FROM app_user ORDER BY id LIMIT 1")
if not uid:
    uid = sql("INSERT INTO app_user (email, full_name, role, password_hash) "
              "VALUES ('gate045@example.com', 'Gate', 'admin', 'x') RETURNING id")
uid = uid[0][0]
# An `applied` conversation has to name the version it was applied as (ck_applied_has_version).
version = sql("SELECT id FROM workspace_version ORDER BY id DESC LIMIT 1")
if version:
    version_id = version[0][0]
else:                     # a fresh schema has no applied version yet: the session needs one
    version_id = sql("INSERT INTO workspace_version (state, applied_at, checksum, lock, artifacts,"
                     " specs) VALUES ('previous', now(), 'gate', '{}'::jsonb, '{}'::jsonb,"
                     " '{}'::jsonb) RETURNING id")[0][0]
for status, draft in (("applied", draft_missing), ("open", draft_present)):
    sql("INSERT INTO assistant_session (title, status, project_id, created_by, applied_version_id,"
        " draft) VALUES ('g', :st, :p, :u, :v, CAST(:d AS jsonb))",
        st=status, p=pid, u=uid, v=version_id, d=json.dumps(draft))

alembic("upgrade", "head")

errors = []
for rel, expected in (("specs/002-rescatada/spec.md", "# rescatada\n"),
                      ("specs/002-rescatada/plan.md", "# plan\n")):
    target = folder / rel
    if not target.exists():
        errors.append(f"missing after upgrade: {rel}")
    elif target.read_text(encoding="utf-8") != expected:
        errors.append(f"changed content: {rel}")
# The project's own copy is the one that survives; the draft never overwrites it.
if (folder / "specs/001-ya-esta/spec.md").read_text(encoding="utf-8") != "# vieja\n":
    errors.append("the project's own file was overwritten by an older draft")
# Not a spec document: never copied.
if (folder / "integrations/x/integration.yaml").exists():
    errors.append("a non-spec document was copied")

gone = sql("SELECT to_regclass(t) FROM unnest(ARRAY['assistant_session','assistant_message',"
           "'assistant_attachment','assistant_preview_request','assistant_command_run',"
           "'assistant_auto_run','assistant_run_profile']) AS t")
for (name,) in gone:
    if name is not None:
        errors.append(f"table still there: {name}")
columns = sql("SELECT column_name FROM information_schema.columns WHERE table_schema = :s "
              "AND table_name = 'project_file_revision' "
              "AND column_name IN ('session_id','command_run_id')", s=schema)
if columns:
    errors.append(f"assistant columns still there: {columns}")
if sql("SELECT 1 FROM information_schema.columns WHERE table_schema = :s "
       "AND table_name = 'project' AND column_name = 'preview'", s=schema):
    errors.append("project.preview still there")

alembic("upgrade", "head")   # idempotent: a second run must not disturb the rescue
if not (folder / "specs" / "002-rescatada" / "spec.md").exists():
    errors.append("the rescue disappeared on the second run")

sql("DELETE FROM project WHERE slug = :s", s=slug)
for error in errors:
    print(error)
raise SystemExit(1 if errors else 0)
PY
printf 'ok\n'
