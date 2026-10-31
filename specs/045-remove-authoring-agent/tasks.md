# Tasks — 045 remove the in-app authoring agent

**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [inventory.md](./inventory.md)

Delete by inventory. Every phase leaves the tree runnable: `ruff` clean, `import app.main`, suites
green.

## Phase 1: Inventory (commit 1)

- [ ] T001 Write `specs/045-remove-authoring-agent/inventory.md` enumerating every file, route, table, setting, string key, test and dependency to remove, with the reason, and commit it before deleting anything

## Phase 2: Frontend removal (commit 2)

- [ ] T002 Delete `frontend/src/components/assistant/` (9 files), `frontend/src/pages/admin/AssistantSession.tsx` and `frontend/src/pages/admin/RunProfiles.tsx`
- [ ] T003 Remove the assistant routes from `frontend/src/App.tsx` and the matching entries from `frontend/src/routeAccess.ts`; keep `/admin/ia` and `Ayuda`
- [ ] T004 Remove the AI card and the "IA funcionando" pill from `frontend/src/pages/admin/AdminHome.tsx` and `frontend/src/pages/admin/adminTiles.ts`, and set the grid to 3/2/1
- [ ] T005 Remove the assistant navigation item and the header sparkle from `frontend/src/components/AppShell.tsx`
- [ ] T006 Strip the assistant strings from `frontend/src/i18n/es.ts` and `frontend/src/i18n/en.ts` and the assistant types from `frontend/src/api/types.ts`
- [ ] T007 Remove the narrative component and its call site (`Narrative.tsx`, `ReportView.tsx`)
- [ ] T008 Delete the assistant frontend suites (14) and the browser specs (`assistant*.spec.ts`, `commands.spec.ts`); keep the report, sharing, projects and layout specs
- [ ] T009 `tsc --noEmit` and `vitest run` green with the agent gone from the screens

## Phase 3: Backend removal (commit 3)

- [ ] T010 Delete `backend/app/api/assistant.py` and unregister it in `backend/app/main.py`
- [ ] T011 Delete `backend/app/assistant/` (23 files) and every import of it
- [ ] T012 Delete `backend/app/engine/narrative.py` and `POST /api/reports/{id}/narrative`, keeping the `ai_narrative` schema key as deprecated-ignored
- [ ] T013 Slim `backend/app/ai/` to provider selection plus `complete()`; drop tool calling, rounds, vision and the stage budgets
- [ ] T014 Drop the assistant hooks from `backend/app/api/projects.py`, `backend/app/api/security.py` and `backend/app/worker.py`
- [ ] T015 Remove the assistant models from `backend/app/models.py`
- [ ] T016 `ruff check` clean and `python -c "import app.main"` succeeds

## Phase 4: Migration and settings (commit 4)

- [ ] T017 Write the rescue step: copy every applied conversation's spec documents into its project through `fs.apply_ops`, skipping what is already there, and log what it rescues
- [ ] T018 Write migration `0044_drop_authoring_agent`: rescue, then drop the seven tables, their constraints and the `app_user.attachments_notice_at` column; `downgrade` recreates the empty tables
- [ ] T019 Remove the chat settings from `backend/app/config.py`, its cross-field validator and the assistant lines in `.env.example`; keep `AI_PROVIDER` documented as help-only
- [ ] T020 `pytest tests/test_migrations.py` green, and a second `upgrade head` on a seeded database changes nothing

## Phase 5: Tests, fixtures, dependencies, gates (commit 5)

- [ ] T021 Delete the 43 backend suites of the inventory; keep the report, project, share, worker and 044 suites
- [ ] T022 Decide `FakeProvider`: keep it only if the help tests need it, otherwise delete it with the fixtures it served
- [ ] T023 Measure the four numbers of the plan and record them in the PR body
- [ ] T024 Remove the packages the dependency gate reports unused, backend and frontend
- [ ] T025 Add `scripts/gate-vocabulary.sh`, `scripts/gate-dead-code.sh`, `scripts/gate-dependencies.sh`, `scripts/gate-routes.sh`, `scripts/gate-migration.sh` and one entry point that runs them
- [ ] T026 Prove each gate fails on a deliberately reintroduced offence and passes on the tree

## Phase 6: Docs, specs, constitution, CHANGELOG (commit 6)

- [ ] T027 Remove the in-app assistant section from `docs/VIBE-REPORTING.md` and the Asistente rows from `README.md` and `README.es.md`
- [ ] T028 Remove the help topics that describe the assistant; keep the page and its search working
- [ ] T029 Move `specs/014, 015, 017, 021, 024, 028, 029, 035, 036, 039, 040` to `specs/_deprecated/<id>/` with a one-line `DEPRECATED.md` each
- [ ] T030 Amend the constitution to 2.0.0: principle IX redefined, the folder list without `backend/app/assistant/`
- [ ] T031 `CHANGELOG.md` 0.2.0 **Removed**, every removed feature by spec number

## Dependencies

Phase 2 and Phase 3 touch disjoint trees and may run in either order; Phase 4 depends on 3 (the
models are gone), Phase 5 on 4 (the gates must see the final tree), Phase 6 on 5.
