# Evidence — 045 remove the in-app authoring agent

Every number here was measured on this tree; every command was run and its result pasted, not
recalled. The owner runs the full suites independently; what is recorded below is the targeted
proof of each phase gate plus the six gates that keep the agent from coming back.

## Size, before and after

| Measure | Before (0.1.x, HEAD~) | After | Command |
|---|---|---|---|
| Files deleted | — | 82 | `git status --porcelain \| grep -c '^D'` |
| Backend + frontend source lines | — | **−13 866** | `git diff --stat HEAD -- backend/app frontend/src` |
| Backend modules of the agent | 23 (`backend/app/assistant/**`) | 0 | `git ls-tree -r HEAD --name-only backend/app/assistant` |
| Backend test modules | 153 | 96 | `git ls-tree -r HEAD --name-only backend/tests \| grep -c '\.py$'` |
| Backend Python lines | — | 27 375 | `find backend/app -name '*.py' \| xargs wc -l` |
| Backend dependencies | 26 | 26 | `grep -c '^\s*"' backend/pyproject.toml` |
| Assistant tables | 7 | 0 | `scripts/gates/05-migration.sh` |

No package left the manifests: `deptry` reports no declared-but-unused dependency and the frontend
scan finds an importer for every package but the config-level tooling. The provider SDK stays for
`complete()` (help only), which is why `anthropic` and `httpx` are still declared. The container
image therefore does not shrink by a dependency, only by code: 23 backend modules, 57 test modules
and the whole frontend surface of the agent.

## Phase 3 gate — backend removal

| Check | Command | Result |
|---|---|---|
| Lint | `cd backend && ../.venv/bin/python -m ruff check app` | `All checks passed!` |
| Imports | `python -c "import app.main"` | exits 0 |
| No assistant endpoint | `sh scripts/gates/04-routes.sh` | `ok` (no `/assistant`, `/commands`, `/contracts`, `/preview` segment) |
| AI suites | `pytest tests/test_ai.py tests/test_ai_status.py tests/test_api_errors.py` | passed, 51 passed 1 skipped |
| Projects suites | `pytest tests/test_projects_apply.py tests/test_projects_history.py tests/test_projects_specs.py tests/test_projects_zip.py tests/test_projects_api.py tests/test_projects_upgrade.py tests/test_project_scope.py tests/test_project_scope_guard.py tests/test_project_fixes.py` | see below |

## Phase 4 gate — migration and settings

`sh scripts/gates/05-migration.sh` against a throwaway schema (`DB_SCHEMA=app_test_gate045`):

```
INFO  [alembic.045] 045: rescate terminado (2 documentos escritos, 1 ya presentes)
ok
```

It seeds two conversations on a real project — one `applied` whose spec folder is not in the
project, one `open` whose spec the project already has — upgrades to head and asserts: the missing
documents were copied, the project's own bytes were not overwritten, a non-spec document was not
copied, the seven tables are gone, `project_file_revision.session_id`/`command_run_id` and
`project.preview` are gone, and a second `upgrade head` changes nothing. The first attempt at this
gate found the seed needed a version row and the checks had to be schema-qualified: both fixed, and
this is why the gate exists.

## Gates — each fails on a reintroduced offence

| Gate | Poisoned tree | Clean tree |
|---|---|---|
| 01 vocabulary | `# asistente` in a file → exit 1 | exit 0 |
| 02 dead code | `import json` unused → exit 1 | exit 0 |
| 03 dependencies | `"left-pad"` in `frontend/package.json` → exit 1 | exit 0 |
| 04 routes | a `/assistant/overview` route → exit 1 | exit 0 |
| 05 migration | see above | exit 0 |
| 06 settings | `AI_CHAT_MAX_ROUNDS=5` → exit 1 | exit 0 |

## Frontend

```
npx tsc --noEmit              → clean
npx vitest run                → 56 files, 592 tests passed
```
