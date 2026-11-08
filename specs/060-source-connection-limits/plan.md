# Implementation Plan: Survive "too many clients" on an origin database

**Branch**: `060-source-connection-limits` | **Date**: 2026-11-07 | **Spec**:
[spec.md](./spec.md)

**Input**: Feature specification from `/specs/060-source-connection-limits/spec.md`

## Summary

Turn a connection-slot refusal from an origin (`SQLSTATE 53300` and its siblings) from a red run
failure into a pending condition the product waits out and explains. Three parts, in the order they
matter:

1. **Classify and retry** in the engine (`backend/app/engine/extract.py` raises a new `SourceBusy`,
   the runner retries the origin read with jittered exponential backoff) and end an exhausted run in
   a new amber state `skipped_busy` that touches no dataset and no freshness.
2. **Be a polite client**: one ceiling of simultaneous origin sessions per source
   (`settings.max_connections`, default 1 for PostgreSQL and 2 for Supabase), shared by runs,
   `describe`, structure generation and direct reads; one connection per run reused across its
   datasets; a 10 s connect timeout; `idle_in_transaction_session_timeout` /
   `idle_session_timeout` where the server understands them; `application_name` carrying the
   integration id.
3. **Say what to do**: a help topic in both languages, an INSTALL section, an amber badge with the
   attempts and a «Qué hacer» link, the origin's own `max_connections` / client count in the test
   connection, and a one-per-streak notification.

## Technical Context

**Language/Version**: Python 3.13 (backend, `backend/.venv`), TypeScript/React 19 + Tailwind 3.4
(frontend), PostgreSQL for the product schema (Alembic).

**Primary Dependencies**: FastAPI, SQLAlchemy 2 + psycopg 3 (`psycopg` binary), apscheduler,
polars; React Router, lucide-react, vitest, Playwright, axe-core.

**Storage**: product schema `public` (Alembic, next revision `0055_source_connection_limits`);
origin PostgreSQL read through psycopg with a read-only session; BI pool for staging/load.

**Testing**: `pytest` (`backend/tests`, the `applied` fixture builds a schema — minutes per test),
`vitest` (`frontend/tests/unit`), Playwright (`frontend/tests/e2e`), gates
(`scripts/gates/all.sh`), docs parity (`scripts/check_docs_parity.py`).

**Target Platform**: Linux server (worker + API in one compose stack), mobile-first web client.

**Project Type**: web service + worker + SPA (existing layout, no new project).

**Performance Goals**: a busy origin is retried without holding the worker's other slots; no source
ever exceeds its declared simultaneous sessions; a run's extraction keeps its current throughput
(one connection, streamed COPY).

**Constraints**: constitution II (origin is read-only and never harmed) and V (fixed stack: no new
dependency); no new setting may require configuration to be safe; every message in Spanish and
English; `.env.example` and `docs/INSTALL.md` documented; no host, port or credential in any stored
message.

**Scale/Scope**: one worker process (4 threads) + one API process per installation; origins with
`max_connections` in the tens; integrations hourly; run history already stored per integration.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle / constraint | How this feature satisfies it |
|---|---|
| I. Mobile-First | The new badge, the attempts line and the source field use the existing 44 px / 12 px compact scale; the help topic is text. |
| II. Backend as ETL, Direct Reads by Exception | The ceiling is a *second*, smaller bound than `MAX_PARALLEL`; direct reads keep their declaration, and this feature only narrows their concurrency, never widens their scope. The read-only session is untouched. |
| III. Source of Truth Is External | No write to the origin; the only new statements on it are `SHOW`/`pg_settings`-style reads inside the existing read-only session, and `SET` of session timeouts (session-local, not `ALTER`). |
| IV. Separated Concerns by Folder | New engine module `backend/app/engine/source_slots.py`; classification stays in `extract.py`; the runner and `describe` consume both; no new folder. |
| V. Fixed Technology Stack | No new dependency: psycopg exposes SQLSTATE and the psycopg_pool is already there. |
| VI/IX | Unchanged: no data model of the origin, no project-file format change. |
| Constraints: product schema versioned with Alembic | New revision `0055_source_connection_limits` (run status CHECK + `integration_run.busy` + audit kind). |
| Constraints: worker idempotent and restartable | A `skipped_busy` run writes nothing to datasets; permits and locks are released in `finally`; a restart mid-wait leaves a `running` row that the next run already marks interrupted. |
| Constraints: every user-visible text in ES and EN | `app/i18n/{es,en}.py` keys for messages, `frontend/src/i18n/{es,en}.ts` for the UI, plus the help topic pair and `docs/es/INSTALL.md`. |

**Gate result: PASS.** No violation needs justification.

## Project Structure

### Documentation (this feature)

```text
specs/060-source-connection-limits/
├── plan.md              # this file
├── research.md          # Phase 0: decisions R1–R8
├── data-model.md        # Phase 1: run state, busy record, source ceiling
├── quickstart.md        # Phase 1: how to prove it end to end
├── checklists/requirements.md
├── contracts/api.md     # Phase 1: shapes the UI consumes
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
backend/
├── app/engine/source_slots.py      # NEW: per-source ceiling (local semaphore + cross-process slot)
├── app/engine/extract.py           # SourceBusy classification, session options, one connection
├── app/engine/runner.py            # retry loop, reuse the connection, skipped_busy, hints
├── app/engine/busy.py              # NEW: streak, notification throttle, quietest hour
├── app/sources/describe.py         # takes a permit; counts for the test connection
├── app/sources/connectors/postgresql.py  # test(): max_connections + clients
├── app/sources/schemas.py          # `max_connections` field (PG, Supabase)
├── app/config.py                   # SOURCE_CONNECT_RETRIES / SOURCE_CONNECT_BACKOFF_S
├── app/models.py                   # RUN_STATUSES + `skipped_busy`, integration_run.busy
├── app/api/workspace.py            # run_json carries the busy record + the hint
├── app/alembic/versions/0055_source_connection_limits.py
├── app/i18n/{es,en}.py             # run.busy.*, sources.*.max_connections*
├── app/guide/{es,en}/la-fuente-no-admite-mas-conexiones.md + index.yaml
└── tests/test_source_busy.py, test_source_slots.py, test_run_skipped_busy.py

frontend/src/
├── pages/admin/Integrations.tsx    # amber badge, attempts, «Qué hacer», quiet-hour hint
├── pages/admin/SourceForm.tsx      # max_connections field + the two test-connection counts
├── api/types.ts                    # IntegrationRun.busy, integration busy_hint
└── i18n/{es,en}.ts

docs/
├── INSTALL.md + docs/es/INSTALL.md # the four remedies
└── CHANGELOG.md                    # Unreleased
```

**Structure Decision**: everything stays where it is today — the classification in the single origin
connection funnel (`extract._pg_connect`), a new small engine module for the ceiling, the retry in the
runner that already owns run state, and the notification beside the runner. No new package, no new
service, no schema of the origin touched.

## Phase 0 — research

See [research.md](./research.md): R1 classification, R2 where the retry lives, R3 the ceiling across
threads and processes, R4 one connection per run, R5 session options, R6 the `skipped_busy` state and
its record, R7 the notification channel and throttle, R8 the quietest-hour hint.

## Phase 1 — design

- [data-model.md](./data-model.md) — the run state, the `busy` record, the source ceiling value and
  the streak; migration `0055`.
- [contracts/api.md](./contracts/api.md) — `GET /api/integrations`, the run shape, the source types
  and the test-connection result.
- [quickstart.md](./quickstart.md) — the seven checks a reviewer runs.

## Post-design Constitution Check

Re-checked after Phase 1: unchanged, PASS. Two notes recorded because they are the sort of thing a
reviewer will ask:

- The cross-process ceiling is enforced with an advisory lock **on the product's own database**, on
  the connection the runner already holds for the integration lock — no extra connection to the
  origin and none to the product. With more than one API replica the ceiling is per replica for
  describe/direct reads; documented in `docs/INSTALL.md` rather than pretended away.
- `SET` of `idle_*_timeout` is session-local. It is issued inside the read-only session and tolerated
  when the server does not know the setting (older than 14), so the constitution's "read-only"
  clause holds: nothing in the origin changes.
