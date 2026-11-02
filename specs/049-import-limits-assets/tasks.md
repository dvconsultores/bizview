---

description: "Task list — 049 import limits and assets"
---

# Tasks: Import limits that account for project images, and import as the only way in

**Input**: Design documents from `/specs/049-import-limits-assets/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: included — the specification's `## Tests` section names the fixtures and the parity checks,
and the release gate in the input requires them.

**Organization**: by user story, so each is independently implementable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: `US1`…`US4`, mapping to [spec.md](./spec.md)

---

## Phase 1: Setup

**Purpose**: reproduce the defect before changing anything, so the fix is proven against it.

- [ ] T001 Add a failing regression test in `backend/tests/test_projects_zip.py` that imports a fixture zip with 483 images under `assets/coins/` and 40 artifacts, asserting today's behaviour (`422 project_too_large`); keep it, flip the assertion in T014
- [ ] T002 [P] Create the fixture builder `backend/tests/fixtures/projects/make_logo_project.py` that writes a valid minimal project plus N generated PNGs under `assets/coins/` into a zip in memory (reused by backend and CLI tests)
- [ ] T003 [P] Record the baseline: run `cd backend && ../.venv/bin/python -m pytest tests/test_projects_zip.py tests/test_projects_fs.py -q` and note the counts in the PR body

---

## Phase 2: Foundational (blocking — every user story reads it)

**Purpose**: one classification, one tally, one set of numbers (R1, R2, R3, R9).

**⚠️ CRITICAL**: nothing in Phase 3+ can be written before this phase lands.

- [ ] T004 Add `budget_of(path) -> "assets" | "artifacts" | None` to `cli/bizview_cli/layout.py`, derived from the existing `PROJECT_PATTERNS` (`assets/**` → `assets`, every other allowed pattern → `artifacts`, anything else → `None`)
- [ ] T005 Add the shared defaults to `cli/bizview_cli/layout.py`: `ARTIFACTS = BudgetDefaults(max_files=400, max_kb=2048, max_mb=20)` and `ASSETS = BudgetDefaults(max_files=2000, max_kb=300, max_mb=25)`, each with the `label` the message prints
- [ ] T006 Create `cli/bizview_cli/budgets.py` with `Budget`, `Tally`, `OverLimit`, `tally(entries, budgets)`, `DISALLOWED_EXTENSIONS` and `looks_executable(data)` per [data-model.md](./data-model.md) (rules applied in the documented order: unsafe path → disallowed content → ignored → per-file size → file count → total size; artifacts before assets)
- [ ] T007 [P] Add `cli/tests/test_budgets.py`: classification of each layout pattern, a tally within limits, one per refusal (count, bytes, per-file, both over → artifacts wins), and the disallowed-content rule for a `.js` extension and for an ELF-magic `.txt`
- [ ] T008 Add the deployment defaults to `backend/app/config.py`: `project_max_files: int = 400`, `project_max_kb: int = 2048`, keep `project_max_mb: int = 20`, add `project_asset_max_files: int = 2000`, `project_asset_max_kb: int = 300`, `project_asset_max_mb: int = 25`, each `Field(..., ge=1)`
- [ ] T009 Add `ProjectLimits` to `backend/app/models.py` — singleton `id = 1`, six nullable integer columns, `updated_at`, `updated_by` FK, and the checks from [data-model.md](./data-model.md) (`> 0`, `*_max_kb <= *_max_mb * 1024`)
- [ ] T010 Create `backend/alembic/versions/0047_project_limits.py` (`down_revision = "0046_no_default_dashboards"`): create the table and insert the all-NULL row; downgrade drops it. Add `project_limits` to `APP_TABLES` in `backend/tests/test_migrations.py` and to the TRUNCATE/seed handling in `backend/tests/conftest.py` so the singleton survives the autouse `clean` fixture
- [ ] T011 Create `backend/app/projects/budgets.py`: `effective(db)` resolving the row over `Settings`, `zip_max_mb(budgets)`, `json(budgets)` (the `GET` shape), and `store(db, values, actor)` writing the row and auditing `project_limits_changed`
- [ ] T012 Add `project_limits_changed` to `AUDIT_KINDS` in `backend/app/models.py` and to the constraint in a new migration step inside `0047` (append the kind; the constraint may only grow), plus its label in `frontend/src/i18n/{es,en}.ts`
- [ ] T013 [P] Add `backend/tests/test_projects_budgets.py` covering `effective()` with a NULL row, with a partial row, and with a full row (an operator's `PROJECT_MAX_MB` is kept when the column is NULL); `zip_max_mb` is the sum; `store()` audits and rejects `max_kb > max_mb * 1024`

**Checkpoint**: the shared tally, the numbers and the storage exist; the stories can proceed.

---

## Phase 3: User Story 1 — a project with a logo set imports (P1) 🎯 MVP

**Goal**: the reported failure stops happening, and every refusal names one budget.
**Independent test**: the 483-logo fixture imports, applies and serves its images; the four over-limit fixtures are refused with their own codes.

- [ ] T014 [US1] Rework `_entries()` in `backend/app/projects/zip.py` to accumulate per budget (Tally from `cli/bizview_cli/budgets.py`), size the zip against `zip_max_mb`, count file entries per budget instead of one `MAX_ENTRIES`, and keep the ratio / declared-size / symlink / unsafe-path checks untouched
- [ ] T015 [US1] Update `import_zip()` in `backend/app/projects/zip.py` to raise `ZipRejected` with the new codes (`artifacts_over_files`, `artifacts_over_bytes`, `artifacts_file_too_large`, `assets_over_files`, `assets_over_bytes`, `assets_file_too_large`) and to add `budgets` to its return value per [contracts/import-limits-api.md](./contracts/import-limits-api.md)
- [ ] T016 [US1] Replace `check_limits` and `check_asset_limits` in `backend/app/projects/fs.py` with one budget-aware check: each op is measured against the budget its path belongs to (`fs.MAX_FILES`, `fs.MAX_FILE_BYTES` go away; `assets.MAX_KB` becomes the budget's `max_kb`)
- [ ] T017 [US1] Map the new codes to HTTP status in `backend/app/api/projects.py::import_zip` (`413` for the zip being too large, `422` for a budget refusal) and delete the pre-check that compares `len(data)` with `project_max_mb`
- [ ] T018 [P] [US1] Add the refusal messages (`projects.artifacts_over_files`, `projects.artifacts_over_bytes`, `projects.artifacts_file_too_large`, `projects.assets_over_files`, `projects.assets_over_bytes`, `projects.assets_file_too_large`, `projects.zip_disallowed`, `projects.creation_removed`, `projects.limits_*`) to `backend/app/i18n/{es,en}.py`, and retire `projects.project_too_large`
- [ ] T019 [P] [US1] Add the same keys to `cli/bizview_cli/i18n/{es,en}.py` so the CLI and the server print the same sentences
- [ ] T020 [US1] Flip T001's regression test: the 483-logo fixture imports, `budgets.assets.files == 483`, `budgets.artifacts.files` counts only artifacts, every image is on disk
- [ ] T021 [P] [US1] Add the four over-limit fixtures to `backend/tests/test_projects_budgets.py` (2 001 assets, 401 artifacts, 26 MB of assets, one 420 KB image) asserting the status, the code and that the message names **one** budget and contains no combined figure
- [ ] T022 [US1] Add `backend/tests/test_projects_apply_logos.py`: import the 483-logo project, apply it, and read `/api/reports/<id>/assets/coins/BTC.png` — 200, `image/png`, bytes equal to the fixture
- [ ] T023 [P] [US1] Assert in `backend/tests/test_projects_fs.py` that a write above the artifact budget is refused with `artifacts_*` and a write above the asset budget with `assets_*` (the two no longer share a figure)

**Checkpoint**: import works for the reported case; US1 is shippable on its own.

---

## Phase 4: User Story 2 — the author knows before uploading (P1)

**Goal**: both tallies, in the browser, before any byte is sent; the limits are editable.
**Independent test**: the reader tallies a zip built in memory; the page disables the import and names the budget over the limit; `PUT /api/projects/limits` round-trips.

- [ ] T024 [US2] Add `GET /api/projects/limits` and `PUT /api/projects/limits` to `backend/app/api/projects.py` per [contracts/import-limits-api.md](./contracts/import-limits-api.md) — super user, recent re-auth on the `PUT`, field-level `422`
- [ ] T025 [P] [US2] Add `backend/tests/test_projects_limits_api.py`: `GET` with an empty row returns the defaults; `PUT` persists and audits; `PUT` with `asset_max_kb > asset_max_mb * 1024` is a `422` naming the field; a non-superuser gets `403`; `zip_max_mb` equals the sum
- [ ] T026 [P] [US2] Create `frontend/src/lib/zipIndex.ts`: `readZipIndex(file: File): Promise<{name: string; size: number}[]>` reading the EOCD (`PK\x05\x06`, backwards scan ≤ 65 557 bytes) then the central directory (`PK\x01\x02`); Zip64 or a spanned archive returns `[]`
- [ ] T027 [P] [US2] Add `frontend/tests/unit/zip-index.test.ts`: build zips in memory (one with 483 entries, one empty, one with a truncated EOCD) and assert names and sizes; a non-zip returns `[]`
- [ ] T028 [US2] Create `frontend/src/lib/importPreflight.ts`: `tallyIndex(entries, limits)` returning per-budget `{files, bytes, over}` using the same classification prefix (`assets/`) and the limits the server published; `null` when the index could not be read
- [ ] T029 [P] [US2] Add `frontend/tests/unit/import-preflight.test.ts` for within-limit, over-files, over-bytes, and "both over → artifacts reported"
- [ ] T030 [US2] Add `limits()` and `saveLimits()` to `frontend/src/api/projects.ts` and the `ProjectLimits` type to `frontend/src/api/types.ts`
- [ ] T031 [US2] Add the pre-flight panel to `frontend/src/pages/projects/Projects.tsx`: on file choice, read the index, show both tallies against their limits, name the budget over the limit, and disable the import action while one is over; `null` index falls through to the upload
- [ ] T032 [US2] Add the limits editor to `frontend/src/pages/projects/Projects.tsx` — a collapsible "Límites de importación" card (super users only, the page already is) with six fields, "predeterminado (N)" placeholders for inherited values, save and field errors
- [ ] T033 [P] [US2] Add the copy for both to `frontend/src/i18n/{es,en}.ts` (`projects.limits.*`, `projects.preflight.*`)
- [ ] T034 [US2] Extend `frontend/tests/unit/projects-page.test.tsx`: the tallies render before upload, the import button is disabled and the reason names `assets/` when the index is over, and the limits form saves
- [ ] T035 [US2] Add the e2e case to `frontend/tests/e2e/flows.spec.ts` (or a new `import-limits.spec.ts`): choose an over-limit zip, see the counts and the disabled action, then import a valid one

**Checkpoint**: an author cannot waste an upload; the limits are theirs to raise.

---

## Phase 5: User Story 3 — a project folder with pack files still in it imports (P2)

**Goal**: harmless unknown files are listed, not fatal; executable content still fails.
**Independent test**: a zip carrying `PROMPT.md`, `REQUEST.md`, `request/`, `sources/`, `.bizview/`, `README.md`, `.DS_Store`, `__MACOSX/…` imports and lists them; a zip with `build/pack.js` is refused.

- [ ] T036 [US3] Apply the classification order from [data-model.md](./data-model.md) inside `import_zip()`: disallowed content → `ZipRejected("zip_disallowed", path)`, unknown-but-harmless → `ignored`, using `budgets.looks_executable` and `DISALLOWED_EXTENSIONS`
- [ ] T037 [US3] Report the ignored list as paths only, deduplicated and sorted, and keep the count in the `project_imported` audit detail
- [ ] T038 [P] [US3] Add `backend/tests/test_projects_zip_ignored.py`: the pack-files fixture imports with every pack path in `ignored`; `.js`, `.sh` and an ELF-magic `.txt` each fail with `zip_disallowed` and leave no project and no folder behind
- [ ] T039 [US3] Make `_ignored_files()` in `cli/bizview_cli/validate.py` use the same classifier, so a folder's ignored list and the archive's agree
- [ ] T040 [P] [US3] Add the ignored list to the CLI's human and `--json` output per [contracts/cli-import-dry-run.md](./contracts/cli-import-dry-run.md), and a `cli/tests/test_validate_budgets.py` assertion that a folder with pack files reports them

**Checkpoint**: an author zips what they have, and the import tells them what it skipped.

---

## Phase 6: User Story 4 — import is the only way in (P1)

**Goal**: no create affordance anywhere; the endpoint refuses and says why.
**Independent test**: no create button in either page state; `POST /api/projects` → 410 and no row; import, export, validate, history, apply and rollback still pass.

- [ ] T041 [US4] Remove the create button, the create form, its state and `projectsApi.create` / `projectsApi.suggestSlug` calls from `frontend/src/pages/projects/Projects.tsx`; the page becomes import-only
- [ ] T042 [US4] Make the empty state offer **Importar proyecto**: `frontend/src/pages/projects/Projects.tsx` passes an import action into `EmptyState` and `t.projects.emptyText` stops suggesting creation
- [ ] T043 [US4] Delete `create` and `suggestSlug` from `frontend/src/api/projects.ts` and the now-unused i18n keys (`projects.newProject`, `projects.create`, `projects.name`, `projects.slug`, `projects.slugHint`, `projects.cancel`) from `frontend/src/i18n/{es,en}.ts`
- [ ] T044 [US4] Make `POST /api/projects` in `backend/app/api/projects.py` answer `410` with `project_creation_removed`, keep the route declared and documented, and delete the `GET /api/projects/slug` route with its `ProjectCreate` model
- [ ] T045 [P] [US4] Add `backend/tests/test_projects_create_removed.py`: `POST /api/projects` → 410 with the documented code, `SELECT count(*) FROM project` unchanged, `GET /api/projects/slug` → 404, and an import still creates a project through the service
- [ ] T046 [US4] Update `frontend/tests/unit/projects-page.test.tsx` to assert no create affordance in either state (with projects and empty) and that the empty state's action is the import
- [ ] T047 [US4] Update the e2e flows that clicked "Nuevo proyecto" (`frontend/tests/e2e/`) to import a fixture instead, and assert the create button is absent
- [ ] T048 [P] [US4] Grep-check the removal: `grep -rn "projects.create\|newProject\|/api/projects/slug" backend frontend cli` returns only the refusal test

**Checkpoint**: the constitution's "a project enters the product only through import" is now enforced, not aspirational.

---

## Phase 7: CLI parity (FR-006)

- [ ] T049 Add `bizview import --dry-run <zip|folder> [--json]` to `cli/bizview_cli/__main__.py`, printing the two tallies, the ignored list, `importable` and the refusal reason per [contracts/cli-import-dry-run.md](./contracts/cli-import-dry-run.md); exit `0` importable, `1` refused, `2` unreadable
- [ ] T050 Implement the dry run in `cli/bizview_cli/project.py` (or a new `cli/bizview_cli/importers.py`) reading a zip's entries or a folder's tree and calling `budgets.tally` — the same function the server uses
- [ ] T051 [P] Add `cli/tests/test_import_dry_run.py`: the 483-logo zip is importable with the expected numbers; an over-limit zip exits `1` with the assets message; a folder works; `--json` shape matches the contract
- [ ] T052 [US1] Add the parity test `cli/tests/test_parity_budgets.py` asserting the CLI dry run's tallies equal what `backend/tests/test_projects_zip.py` measures for the same fixture bytes (SC-005), skipping when the backend schema is unavailable

---

## Phase 8: Polish & cross-cutting

- [ ] T053 [P] Rewrite the budget sections of `docs/IMPORT.md`: the two budgets, the ignored-file rule, the refusal messages, "only through import", and the `410` code
- [ ] T054 [P] Add the guide topic `backend/app/guide/{es,en}/importar-un-proyecto.md` with its `index.yaml` entry (section `proyectos`, roles `[superuser]`, routes `/proyectos`, no commands), and update the `proyectos` topic's summary, aliases and body to import/export only
- [ ] T055 [P] Update `pack/bizview-starter-pack/bizview-starter/PROMPT.md`: the two budgets, "zip only the project files", and the note that the pack's own files are ignored on import
- [ ] T056 [P] Amend the import Constraint bullet in `.specify/memory/constitution.md` to state the two budgets, and add the CHANGELOG entry under Unreleased (Changed + Removed)
- [ ] T057 Run `bash scripts/gates/all.sh`, `cd backend && ../.venv/bin/python -m pytest tests/test_projects_zip.py tests/test_projects_budgets.py tests/test_projects_limits_api.py tests/test_projects_create_removed.py tests/test_projects_fs.py -q`, `cd cli && ../.venv/bin/python -m pytest -q`, `cd frontend && npx tsc --noEmit && npx vitest run`
- [ ] T058 Update `specs/031-project-import/spec.md` and `specs/044-visual-components-assets/spec.md` with a one-line pointer to 049 where their limits are stated, so the older specs are not read as current

---

## Dependencies

```text
Phase 1 (T001–T003)  →  Phase 2 (T004–T013)  →  everything else
Phase 3 (US1)  →  Phase 4 (US2, needs the GET/PUT limits and the server's codes)
Phase 3 (US1)  →  Phase 5 (US3, shares the entry walk)
Phase 3 (US1)  →  Phase 6 (US4, the import must keep working while creation goes)
Phase 2 + Phase 5  →  Phase 7 (the dry run needs the tally and the ignore rules)
Phase 7  →  Phase 8
```

US2, US3, US4 and Phase 7 touch different files and can be built in parallel once Phase 3 lands.

## Parallel execution examples

```text
# after Phase 3, three people at once:
A: T024→T025 (API limits)  then T030→T031→T032→T033→T034→T035 (pre-flight UI)
B: T036→T037→T038→T039→T040 (ignored / disallowed)
C: T041→T042→T043→T044→T045→T046→T047→T048 (import-only)
```

## Implementation strategy

**MVP** = Phase 1 + Phase 2 + Phase 3 (US1): the reported production failure is fixed and every refusal
names one budget. Ship that first if anything must be deferred.

Then US4 (a product decision already made by the owner, small and self-contained), then US2 (the
pre-flight and the editable limits — the largest piece), then US3, then Phase 7 (CLI), then Phase 8.

Every phase leaves the suites green; no phase depends on a later one to be correct.
