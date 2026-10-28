# Tasks: `/speckit-all` hardening (040)

Commit 1 — Step 0: the `IntegrityError` is a state conflict, never "error inesperado".

- [ ] T001 `runs.create` frees the active-run slot before the insert (flush order) and reports the
      constraint name in `command_active`.
- [ ] T002 `app.errors`/`service`: map an `IntegrityError` raised in the loop to
      `ApiError(409, "loop_state_conflict")` carrying `constraint`, and to the stop reason
      `blocked:loop_state_conflict:<constraint>`.
- [ ] T003 Regression test: a turn that raises `IntegrityError` ends with that code, keeps the
      pipeline cursor and writes the report.

Commit 2 — A + B: the state machine, `--only` and honest fixes.

- [ ] T004 `pipeline.next_stage()`: converge → implement (round+1) → converge (max 2), then verify;
      verify → implement → verify (max 3); verify with unchecked tasks → implement.
- [ ] T005 `_plan_position` reads `next_stage`; the chip carries `· ronda N`.
- [ ] T006 `--only T025,T026` on `/speckit-implement` (parse, carry, guard, refuse unknown ids).
- [ ] T007 Remove `validate.fix_tasks`; add the honest action text and the
      "Implementar tareas pendientes" suggestion (`/speckit-implement <spec> --only …`).
- [ ] T008 Fix registry: enumerate the deterministic fixes; a test forbids status/checkbox edits.
- [ ] T009 `tasks_ticks` needs the task's artifact to exist and the task to be in `--only`;
      another command writing a tick is refused with `tasks_tick_needs_implement`.
- [ ] T010 Tests: state machine fixtures (converge-gap, caps, verify-unchecked), fix registry,
      `--only`, tick guard.

Commit 3 — C: bounded compression and stage context.

- [ ] T011 One compression per run with the `(session_id, run_id, compression_n)` key; a second
      only when the first freed ≥ 20 %; otherwise `blocked:context_exhausted`.
- [ ] T012 `✔ <stage> — …` summary written when a stage run ends.
- [ ] T013 Stage-scoped history inside a plan (current stage + previous summary line).
- [ ] T014 Tests: idempotent compression, the exhausted path keeps the cursor, scoping drops old
      tool results.

Commit 4 — D: tool groups and budgets.

- [ ] T015 `TOOL_GROUPS` per stage/command; `offered_tool_specs` returns ≤ 25.
- [ ] T016 `ai_stage_token_budget` → `blocked:stage_budget`, state saved.
- [ ] T017 `tokens_per_stage` in `run-report.md`; tool count and prompt size logged at INFO per
      round and shown in "Detalles técnicos".
- [ ] T018 Tests: transport spy asserts the group and the cap; the ceiling stops the stage.

Commit 5 — E: the two data defects.

- [ ] T019 `check_request` before `fields` (implement prompt + guard) and the error lists the
      actual keys.
- [ ] T020 `timestamp_unit` in the integration schema, inferred from the sample, validated at
      preview (1990–2100) with the deterministic `timestamp_unit_mismatch` fix.
- [ ] T021 Tests: missing field names the keys; wrong unit detected and fixed; preview passes on
      the recorded CoinMarketCap responses.
- [ ] T022 End-to-end on the recorded fixture: two specs, 0 compressions, 0 `IntegrityError`,
      under 1.5 M tokens.

Commit 6 — Docs.

- [ ] T023 Guide topics (033): "rondas de convergencia y verificación" and "Implementar tareas
      pendientes"; `es.ts`/`en.ts`.
- [ ] T024 CHANGELOG under Unreleased; `specs/040/quickstart.md`.
