# Tasks — 060-source-connection-limits

Feature: [spec.md](./spec.md) · Plan: [plan.md](./plan.md) · Research: [research.md](./research.md) ·
Data model: [data-model.md](./data-model.md) · Contracts: [contracts/api.md](./contracts/api.md) ·
Quickstart: [quickstart.md](./quickstart.md)

Tests are part of the work here: the incident is only really fixed if a fake origin that answers
`53300` proves it.

## Phase 1 — Setup

- [x] T001 `backend/app/config.py`: add `source_connect_retries: int = 4` (1–10) and
  `source_connect_backoff_s: int = 15` (1–600), beside the other engine settings; `.env.example`
  documents both with a one-line comment each.
- [x] T002 `backend/app/engine/source_slots.py` (new): `DEFAULTS = {"postgresql": 1, "supabase": 2,
  "rest": 4, "soap": 4}`, `limit_of(source) -> int` (settings `max_connections` when it is an int in
  1–20, else the kind's default, never raising), `semaphore(key, limit)` on one module-level registry,
  and `turn(key, limit, *, deadline=None, check=None, pg=None)` — a context manager that takes the
  local permit, optionally the cross-process slot on `pg`
  (`pg_try_advisory_lock(hashtextextended('source:' || key, 0))`, polled every 0.5 s, released in a
  `finally`), and calls `check()` between polls so a stop request interrupts the wait.

## Phase 2 — Foundational (blocks every story)

- [x] T003 `backend/app/engine/extract.py`: `BUSY_SQLSTATES`, `BUSY_WORDS` (ES/EN/FR/DE wordings plus
  the two PgBouncer ones), `class SourceBusy(ExtractError)` carrying `sqlstate` and `detail`, and
  `busy_of(error) -> SourceBusy | None`. Raised only from `_pg_connect`.
- [x] T004 `backend/app/engine/extract.py`: `_pg_connect` gains `integration: str | None = None` and
  `connect_timeout_s: int = 10`; `application_name` becomes `bizview-engine:<integration>` (or
  `bizview-engine:describe`), truncated to 63 bytes; `options` adds
  `-c idle_in_transaction_session_timeout=30000 -c idle_session_timeout=60000`, retried once without
  the idle pair when the server answers `InvalidParameterValue`/`CantChangeRuntimeParam`; a
  `psycopg.OperationalError` matching `busy_of` is raised as `SourceBusy` after redaction.
- [x] T005 `backend/app/models.py` + `backend/alembic/versions/0055_source_connection_limits.py`:
  `RUN_STATUSES` gains `"skipped_busy"`; `integration_run.busy JSONB NOT NULL DEFAULT '{}'`;
  `AUDIT_KINDS` gains `"integration_busy"`; the migration rewrites both CHECKs and adds the column
  (upgrade and downgrade).

## Phase 3 — User Story 1 (P1): a busy origin is a pause, not a failure

Goal: a run retries inside the run and ends amber `skipped_busy`, touching nothing.
Independent test: a fake origin refusing twice then accepting → success with two retries recorded;
refusing always → `skipped_busy` with data and freshness untouched.

- [x] T006 [P] [US1] `backend/tests/test_source_busy.py`: the classifier over `53300`, `53200`,
  `57P03`, `08001`, `08006`, the pooler wordings and the language variants, plus the negatives
  (unreachable, `QueryCanceled`, a data error) — no database.
- [x] T007 [US1] `backend/app/engine/busy.py` (new): `delays(attempts, base)` → the jittered
  exponential schedule (`base * 3**(n-1)`, ±20 %), and `wait(seconds, *, check, deadline)` sleeping in
  0.5 s slices so a stop or the deadline interrupts it.
- [x] T008 [US1] `backend/app/engine/runner.py`: `_run` wraps each origin read (`_extract` and the
  reconcile check) in the retry loop from T007, resetting `plan.extracted` per attempt; on exhaustion
  it raises the `SourceBusy`; the runner maps it to `_finish(db, run, "skipped_busy", M("run.busy", …))`
  with `integration_run.busy = {sqlstate, attempts, waited_s, detail}` and **no** rollback of a load
  (nothing was loaded).
- [x] T009 [US1] `backend/app/engine/runner.py`: a stop request or the run's deadline ends a backoff
  wait within a second and the run reports `stopped` / its own timeout, not `skipped_busy`
  (spec FR-003, US1/AC5).
- [x] T010 [US1] `backend/app/i18n/{es,en}.py`: `run.busy` («La fuente no admite más conexiones ahora
  ({attempts} intentos, {wait}). El origen respondió: {detail}»), `run.busy_waiting`
  («Esperando turno en la fuente») and `run.busy.attempt` singular/plural.
- [x] T011 [US1] `backend/app/engine/busy.py`: `streak(db, integration_id)` (consecutive
  `skipped_busy`, skipping `stopped`) and `notify_if_due(db, run, integration_id)` — one Telegram
  message to the super users with a `TelegramLink` when the streak reaches 3 and no
  `integration_busy` audit event exists after the streak's first run; records the audit event whether
  or not a chat was reachable.
- [x] T012 [US1] `backend/app/engine/runner.py`: call `busy.notify_if_due` after a `skipped_busy` run
  (worker context only, never inside the request path) and never let a notification failure fail the
  run.
- [x] T013 [P] [US1] `backend/tests/test_run_skipped_busy.py`: the fake origin of the quickstart —
  two refusals then success (attempts=3, waited_s ≈ the two delays); always refusing → `skipped_busy`,
  `data_version` and dataset row counts identical to before, dashboards serve the previous payload;
  three consecutive → exactly one `integration_busy` audit event; a fourth → still one; a success then
  a new streak → a second event.

## Phase 4 — User Story 2 (P1): be a small, well-behaved neighbour

Goal: one ceiling per source, one connection per run, sessions that identify themselves and let go.
Independent test: two integrations on a source with ceiling 1 never overlap; `describe` waits;
`Cancel` releases; the origin sees `bizview-engine:<id>`.

- [x] T014 [US2] `backend/app/engine/runner.py`: `run_integration` takes the source's cross-process
  slot on the connection it already holds for the integration lock (polling `pg_try_advisory_lock`
  until the run's deadline or a stop), sets the run message to `run.busy_waiting` while it waits, and
  always releases it; the local permit comes from T002.
- [x] T015 [US2] `backend/app/engine/extract.py`: `pg_copy`, `pg_rows` and `pg_all` accept
  `conn: psycopg.Connection | None = None` and `integration: str | None = None`; with `conn` they use
  it and do not close it. `runner._run` opens one connection per attempt inside the retry and passes it
  to every dataset plus the reconcile check, tracking it with `cancel.track`.
- [x] T016 [US2] `backend/app/sources/describe.py`: both `postgresql(...)` and `_write_probe(...)` run
  under `source_slots.turn(...)`; `_pg_connect` there passes `integration="describe"`.
- [x] T017 [US2] `backend/app/engine/direct.py`: `_permit` takes its permit from
  `source_slots.turn(...)` with the source's ceiling (keeping its contextvar reentrancy and the
  advisory slot of `_slot`), so a direct read queues behind a run of the same source.
- [x] T018 [P] [US2] `backend/tests/test_source_slots.py`: two tasks with `max_connections: 1` never
  overlap (timestamps); a third waits; `check` interrupted → released; exception inside → released;
  `limit_of` falls back to the default on a bad stored value; the advisory slot is taken and released
  on a real schema (the `applied` fixture).
- [x] T019 [P] [US2] `backend/tests/test_extract_session.py`: `application_name` carries the id and is
  truncated at 63 bytes; the idle options are in `options`; a server refusing them still connects
  (monkeypatched `psycopg.connect` asserting the two calls); `connect_timeout` is 10.

## Phase 5 — User Story 3 (P2): the product says what to do

- [x] T020 [US3] `backend/app/guide/es/la-fuente-no-admite-mas-conexiones.md` and
  `backend/app/guide/en/la-fuente-no-admite-mas-conexiones.md`: the four numbered remedies, the two
  queries (`SHOW max_connections`, the `pg_stat_activity` grouping), what Bizview's own ceiling and
  short-lived sessions mean, and how to tell it apart from Bizview's own database
  (`DB_POOL_SIZE`/`DB_POOL_OVERFLOW`, `docker compose logs backend`); ≤ 6 000 characters, `app:` links
  only.
- [x] T021 [US3] `backend/app/guide/index.yaml`: the topic in the «Integraciones» section, roles
  `superuser` + `admin`, both languages, related to the integrations and schedules topics.
- [x] T022 [US3] `docs/INSTALL.md` + `docs/es/INSTALL.md`: the same four remedies, the two new
  variables, the per-source ceiling and its per-replica caveat for describe/direct reads — same
  headings and code blocks in both files (the parity gate).
- [x] T023 [P] [US3] `backend/tests/test_guide.py` stays green with the new topic (count, links,
  character budget) and the parity script covers the new pair.

## Phase 6 — User Story 4 (P2): watch the ceiling

- [x] T024 [US4] `backend/app/sources/schemas.py`: `F("max_connections", "Conexiones simultáneas",
  "integer", default=1, min=1, max=20, help=…)` on `PG` and the same with `default=2` on `SUPABASE`;
  `app/i18n/{es,en}.py` gains `sources.postgresql.max_connections[.help]` and the Supabase pair.
- [x] T025 [US4] `backend/app/sources/connectors/postgresql.py`: `test()` reports
  `details.max_connections`, `details.clients` and `details.clients_visible` when `pg_settings` and
  `pg_stat_activity` are readable, `False` when not (never failing the test), and classifies a busy
  refusal with the new `busy` code (no retry inside a request).
- [x] T026 [US4] `backend/app/engine/busy.py`: `hint(db, integration_id)` → `{busy_today, quiet_hour}`
  from `integration_run.started_at` (7 days, installation time zone), `quiet_hour` only with
  `busy_today >= 3` and at least two busy hours.
- [x] T027 [US4] `backend/app/api/workspace.py`: `run_json` carries `busy`; the integration list adds
  `busy: {busy_today, quiet_hour, ceiling}` per integration (from T026 and `source_slots.limit_of`).
- [x] T028 [P] [US4] `backend/tests/test_source_test_details.py`: the counts when readable, the
  permission fallback, and the `busy` code on refusal.

## Phase 7 — Frontend

- [x] T029 [US1] `frontend/src/api/types.ts` + `frontend/src/pages/admin/Integrations.tsx`: the
  `skipped_busy` badge (amber, `AlertTriangle`), the «4 intentos, 7 min» line from `run.busy`, and a
  «Qué hacer» link to `/ayuda/la-fuente-no-admite-mas-conexiones` (help route, in-app navigation).
- [x] T030 [US4] `frontend/src/pages/admin/Integrations.tsx`: the quiet-hour hint when
  `busy.busy_today >= 3`, and the ceiling shown in the integration's source line.
- [x] T031 [US4] `frontend/src/pages/admin/SourceForm.tsx`: the two test-connection counts
  (`max_connections`, `clients`) and «sin permiso para verlo» when `clients_visible` is false.
- [x] T032 [P] [US1] `frontend/src/i18n/{es,en}.ts`: every key of [contracts/api.md](./contracts/api.md)
  §6, plus `sourceTest.*`.
- [x] T033 [P] [US1] `frontend/tests/unit/integration-busy.test.tsx`: the badge and the attempts line,
  the help link target, the quiet-hour hint only with three busy runs today, and the counts panel.

## Phase 8 — Polish

- [x] T034 `CHANGELOG.md` under *Unreleased*: **Added** (the `skipped_busy` state, the ceiling, the
  counts, the help topic), **Changed** (one connection per run, session names, the retry), and the
  incident it answers.
- [x] T035 Gates: `npx tsc --noEmit`, `npx vitest run`, `cd backend && .venv/bin/alembic heads`
  (`0055_source_connection_limits`), `sh scripts/gates/all.sh`, `python3 scripts/check_docs_parity.py`,
  and the targeted backend files from T006/T013/T018/T019/T023/T028.
- [x] T036 Constitution note: II already covers read-only origins; add the sentence the owner's brief
  asks for ("never holds a slot it does not need") as a PATCH amendment with its Sync Impact Report.

## Dependencies

- Phase 1 → Phase 2 → US1 (T006–T013) is the MVP: it alone turns the incident into an amber run.
- US2 (T014–T019) needs T002 (slots) and T004 (session options) but not US1's retry.
- US3 (T020–T023) is documentation and can run in parallel with US2 once T010 exists (shared keys).
- US4 (T024–T028) needs T002 (`limit_of`) and T007 (`busy` module); the frontend (T029–T033) needs
  T027's shapes.
- T035 last; T036 anywhere after T002.

## Parallel opportunities

- T006, T018, T019, T023, T028 are separate test files → one batch.
- T020 and T022 (help topic and INSTALL) are different files and different languages pairs.
- T032 and T033 with the rest of the frontend if the API work is done first.

## Implementation strategy

Ship US1 first and alone if time is short: an amber `skipped_busy` run with the origin's own words and
the retry record is the whole incident. US2 is the second half of the same promise (the retry only
works because the slot frees) and should ship in the same release. US3 and US4 are the operator's side.

## Implementation notes (2026-11-07)

- **T002/T015** — one connection per run is real: `pg_copy`, `pg_rows` and `pg_all` accept `conn=`
  and the runner opens the run's origin session once (with the retry) and passes it to every dataset
  plus the reconcile check. `describe` and direct reads keep their own short sessions under the same
  permit.
- **T014** — the cross-process slot is an advisory lock on the connection `run_integration` already
  holds for the integration lock, so a run holds no extra product connection. With several API
  replicas the semaphore is per replica for `describe`/direct reads; `docs/INSTALL.md` says so.
- **T017** — `direct._permit`/`_slot` take the lane from `source_slots`, and a source declared
  BI-ready keeps its declaration's `max_parallel` unless `max_connections` is set explicitly, so an
  existing direct-report installation does not become serial on upgrade.
- **T025** — a busy origin during *Probar conexión* is reported with the new `busy` code and is not
  retried: an HTTP request must answer fast.
- **T033** — the unit file is `frontend/tests/unit/integration-busy.test.tsx`; the busy line and the
  «Qué hacer» link live in `pages/admin/Integrations.tsx` (`Runs`), the hint and the ceiling in the
  integration card, the counts in `pages/admin/SourceForm.tsx`.
- **T034** — the CHANGELOG gained one *Added* pair and one *Fixed* entry under *Unreleased*.
- **T036** — constitution 3.3.0 → 3.3.1 (PATCH) with its Sync Impact Report and one new bullet in
  principle II's list of constraints.
