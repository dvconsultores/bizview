# Quickstart — proving 049 end to end

Prerequisites: a tested PostgreSQL schema reachable through `DATABASE_URL_BI` (the backend suites create
their own `app_test_*` schema), and `.venv` at the repository root. Run backend tests from `backend/`.

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_projects_budgets.py -q
```

## 1. The reported failure now succeeds

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_projects_zip.py -q -k "483 or logos"
```

Expect: the 483-logo fixture imports; `assets/` holds every image; the response's `budgets.assets.files`
is 483 and `budgets.artifacts.files` is the project's own file count (never 483 + artifacts).

## 2. Each refusal names exactly one budget

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_projects_budgets.py -q -k "over"
```

Expect four refusals, each with its own code and a message naming `assets/` or the artifact folders —
`assets_over_files`, `assets_over_bytes`, `artifacts_over_files`, `artifacts_over_bytes` — and no message
containing both.

## 3. A project folder that still carries the pack imports

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_projects_zip.py -q -k "ignored or pack or disallowed"
```

Expect: `PROMPT.md`, `REQUEST.md`, `request/`, `sources/`, `.bizview/`, `README.md`, `.DS_Store` and
`__MACOSX/…` all appear in `ignored`, the project imports, and a zip with `build/pack.js` is refused with
`zip_disallowed`.

## 4. The CLI says the same thing

```bash
cd cli && ../.venv/bin/python -m bizview_cli import --dry-run ../backend/tests/fixtures/…
```

Expect: the two tallies, the ignored list, and `importable`. The parity test
(`cli/tests/test_import_dry_run.py`) compares it with the server's numbers for the same bytes.

## 5. Nothing creates an empty project any more

```bash
cd backend && ../.venv/bin/python -m pytest tests/test_projects_api.py -q -k "create or limits"
```

Expect: `POST /api/projects` → `410` with `project_creation_removed` and no row created;
`GET /api/projects/slug` → `404`; `PUT /api/projects/limits` round-trips and audits.

## 6. The browser refuses before uploading

```bash
cd frontend && npx vitest run tests/unit/zip-index.test.ts tests/unit/projects-page.test.tsx
```

Expect: the reader returns names and sizes for a zip built in memory; the page shows both tallies and
disables the import action when one is over, naming which.

## 7. The whole product still works

```bash
cd frontend && npx vitest run && npx tsc --noEmit
bash ../scripts/gates/all.sh
```

Expect: every suite green — in particular export, validation, history, apply and rollback, which this
feature must not disturb (FR-009, SC-007).

## Manual pass (staging or a throwaway install)

1. Administración → Proyectos → **Límites de importación**: raise *imágenes* to 3 000, save, reload — the
   number persists and the audit log has `project_limits_changed`.
2. Import a real project with a logo set: it imports, applies, and the report renders its images.
3. Choose a zip with 2 100 images: the panel marks the image tally as over, the import action is disabled,
   and the reason names `assets/`.
4. Confirm the Projects page has no "Nuevo proyecto" in any state, and that its empty state offers
   **Importar proyecto**.
