# Tasks — BI-ready sources

**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [research.md](./research.md) ·
[data-model.md](./data-model.md)

Five phases, one commit per phase, each leaving the tree green and every existing direct report
rendering. Nothing in Phase 1 changes behaviour until Phase 2 reads the declaration.

## Phase 0: the constitution says so first

- [X] T001 Amend `.specify/memory/constitution.md` to **3.2.0** (MINOR): principle II gains the
  BI-ready exception with its guardrails (read-only proof, scope, timeout, row cap, concurrency,
  cache); Constraints gains the declaration's limits; a Sync Impact Report records what changed,
  that 048's brief numbered it 2.1.0 (stale — 046 already moved it to 3.1.0) and that no principle
  was dropped. **No code in this commit.**

## Phase 1: the declaration and its proof

- [X] T002 Migration `0044_bi_ready_sources`: `data_source.bi_ready` JSONB default `{}`, the
  `source_bi_ready_changed` audit kind, and the backfill from `direct_reports = true` (research R10)
- [X] T003 `backend/app/sources/service.py`: read and validate the declaration (bounds, the
  deny-list is never overridable), the "is this source BI-ready" question the rest asks
- [X] T004 `backend/app/sources/bi_ready.py`: the empirical read-only proof (a rolled-back
  `CREATE TEMP TABLE` must fail, `SELECT 1` must succeed), the daily re-check on the worker, the
  audit and the notification when it changes
- [X] T005 `PATCH /api/sources/{id}` accepts the declaration for PostgreSQL only, refuses a writable
  credential naming why, audits the change; `GET` returns it with `verified_at`
- [X] T006 `backend/tests/test_bi_ready_declaration.py`: bounds, non-PostgreSQL refusal, the
  deny-list refused inside `schemas`, the proof passing and failing, the backfill of a 019 source

## Phase 2: the scope holds, and the short table form works

- [X] T007 `engine/direct.py`: `permitted(source, schema, object)` reading the declaration; called
  before a connection is opened, and by the validator through the sources API
- [X] T008 `cli/bizview_cli/` report schema and `report_layout`: `direct.tables` accepts
  `alias: schema.object` and `alias: {table, columns}`, `allow_personal`, `materialize`; the
  problems name file and path
- [X] T009 `engine/direct.py`: the short form resolves its columns from `describe`'s structure, and a
  column that is not there is a validation problem, not a 500
- [X] T010 `backend/tests/test_bi_ready_scope.py`: an object outside the scope refused at validation
  **and** at execution; the short form renders the same numbers as the long form; `source: bi` and a
  019 report unchanged; a personal-data column refused and then allowed by a recorded decision
- [X] T011 `pytest backend/tests/test_direct*.py` (all of 019's suite) green with the declaration
  absent, present, and narrowed

## Phase 3: the person responsible can see it

- [X] T012 `backend/app/api/sources.py`: health over `direct_read_log` (24 h: count, p50/p95,
  failures by outcome, cache share) and the declaration in the source payload
- [X] T013 `frontend/src/pages/sources/`: the "Lista para BI" section — toggle, schema and object
  pickers from `describe`, the limits, the timezone, the proof badge with its date, the health tiles
- [X] T014 i18n `es.ts`/`en.ts` for every new label; `no-literals.test.ts` and `audit-labels.test.ts`
  green; `frontend/tests/unit/bi-ready-source.test.tsx`

## Phase 4: a heavy warehouse once a day

- [X] T015 Migration `0045_direct_snapshot` and the model: the payload the engine already produces,
  keyed by report, day and selection
- [X] T016 The worker's daily job: run each `materialize: daily` direct report once, store the
  payload, keep the last 30 days, record the outcome
- [X] T017 The engine reads the snapshot for such a report and labels it ("datos de ayer"), falling
  back to live when there is none; the PDF and share links use the same path
- [X] T018 Tests: the snapshot is written once, read by the dashboard, aged out, and a failing run
  leaves yesterday's in place

## Phase 5: document what ships

- [ ] T019 `describe` marks the source BI-ready and lists only the allowed objects; `PROMPT.md` and
  `docs/AUTHORING.md` explain the short table form, when an integration is the better answer, and the
  limits; `docs/INSTALL.md` records that the `DIRECT_*` variables are now defaults
- [ ] T020 The guide topic `fuentes-lista-para-bi` in both languages plus its `index.yaml` entry and
  the counts the drift tests keep; `CHANGELOG.md` under *Unreleased*
- [ ] T021 The gates and the suites; `evidence.md`

## Dependencies

- T001 before anything: the exception to principle II is what makes the rest legal.
- T002/T003 before T005, T007 and T012 — everything reads the declaration.
- T007/T008 before T009 and T010.
- T015 before T016 before T017.
- T012/T013 last in their phase: they read what Phase 1 and 2 produce.

## Deliberately out

- The 043 WS-B zip (`structure.md`/`structure.json`): unbuilt there, and `describe` already carries
  the facts (research R7).
- Row-level access per user, cross-source joins, and any `ds_*` involvement.
