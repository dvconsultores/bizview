---
description: "Task list for feature 013 — Integration controls"
---

# Tasks: Integration controls

**Roles**: DeepSeek writes code; Claude audits/converges. Migration and auth/audit wiring are
security/data-sensitive: Claude reviews them line by line.

## Phase 1: Foundational

- [X] T001 Migration backend/alembic/versions/0008_integration_control.py (down_revision = current head) per plan.md "Data"; models in backend/app/models.py; upgrade/downgrade test in backend/tests/test_migrations.py
- [X] T002 backend/app/engine/schedule.py (new): parse/validate cron (min interval 5 min), preset → Spanish words, window check (overnight), effective schedules for a version + controls; unit tests backend/tests/test_schedule.py

## Phase 2: User Story 1 — Pause/resume (P1) 🎯

- [X] T003 [US1] backend/app/worker.py: controls-aware `schedules`, fingerprint reload each loop, pause/window check at fire time (manual requests unaffected); tests with the worker's existing test pattern
- [X] T004 [US1] backend/app/api/workspace.py (integrations routes): `GET /api/integrations` control fields + next_run; `PUT /api/integrations/{id}/control` (super user, validation, audit before/after); tests (403 admin, 422 cases, audit row, pause → GET shows Pausada, next_run null)

## Phase 3: User Story 2 — Stop (P1)

- [X] T005 [US2] backend/app/engine/runner.py (+ extract.py where the block/batch loops are): cooperative stop check ≤ every 2 s → rollback, status `stopped`, message "detenida por <nombre>"; `POST …/runs/{run_id}/stop` (202/409, audit); tests: stop during a slow fake origin run ends < 30 s with data unchanged

## Phase 4: User Story 3 — Frequency and window (P2)

- [X] T006 [US3] frontend/src/api/types.ts, frontend/src/i18n/es.ts, frontend/src/pages/admin/Integrations.tsx: state pill, frequency words, window, next run, actions; "Cambiar frecuencia" `View` form (presets, custom, window, full rebuild, restore spec); unit tests for the preset/words mapping

## Phase 5: Polish

- [X] T007 E2E frontend/tests/e2e/integration-controls.spec.ts: pause → state Pausada and next run "—"; resume; change frequency to every 15 min → shown; invalid custom → error; restore spec; (stop covered by backend test)
- [X] T008 CHANGELOG.md; backend tests for the touched modules + frontend suites; `/speckit-converge`

---

## Phase 6: Convergence

- [X] T009 Resolve stale `running` runs left by a crashed worker: sweep orphaned `running` rows at worker start (mark `failed`, reason "el trabajador se reinició") and make the stop endpoint finish a run that no worker holds (advisory lock not held → mark `stopped` at once); tests, per FR-005 / US2/AC1 (partial)
- [X] T010 frontend/src/pages/admin/Integrations.tsx: after "Ejecutar ahora", poll briefly (e.g. every 2 s up to 30 s) until the run appears, so "Ejecutando"/"Detener" show without "Actualizar", per FR-007 (partial)
- [X] T011 Integrations.tsx: show "Pausada" together with "Ejecutando" when a paused integration has a run in progress, per FR-007 / US1/AC3 (partial)
- [X] T012 backend/app/engine/schedule.py `describe` and frontend/src/lib/schedule.ts mirror: return no words when a step does not divide its unit evenly (minutes: 60 % n, hours: 24 % n), with tests ("0 */15 * * *", "*/25"), per FR-006 (contradicts)
- [X] T013 UI: when an allowed-hours window excludes the full-rebuild time, show a warning on the card and in the frequency view ("La recarga completa de las 03:00 queda fuera del horario permitido y no se ejecutará"); update the window hint text, per US3/AC3/AC5 (partial)
- [X] T014 Test: apply a version without the integration → control kept but not listed; re-apply with it → control effective again, per spec Edge Cases (missing)
- [X] T015 API: validate `schedule`/`full_rebuild_cron` length ≤ 100 → 422 (no DB IntegrityError 500); test, per FR-006 / US3/AC2 (contradicts)
- [X] T016 API: reject time-zone offsets on `window_start`/`window_end` (422) — windows are installation-time-zone wall times; test, per spec Edge Case "Time zone" (contradicts)
- [X] T017 Regression test that the advisory lock is released after the orphan sweep and the orphan stop (lock_free helper in backend/tests/test_integration_stop.py), per FR-005 (missing test)
