# Implementation Plan: BI-ready sources

**Feature**: [spec.md](./spec.md) · **Branch**: `main` · **Created**: 2026-11-01
**Decisions**: [research.md](./research.md) · **Entities**: [data-model.md](./data-model.md)

## Technical context

| Concern | Reality today (verified) |
|---|---|
| Language / runtime | Python 3.13 backend (FastAPI, SQLAlchemy 2, Alembic), TypeScript frontend (React, vitest), the `bizview` CLI |
| Where the declaration lives | `data_source.settings` (JSONB) already carries per-source configuration; `data_source.direct_reports` is the 019 boolean |
| Direct execution | `backend/app/engine/direct.py` — its own connection, `SET LOCAL statement_timeout`, deny-list, per-source semaphore, `direct_read_log` |
| Result cache | `report_cache` keyed with a bucket from `cache_seconds` |
| Structure | `GET /api/sources/{name}/describe` and `/api/sources/bi/describe` (JSON, never row values), consumed by `bizview describe` |
| Worker | `backend/app/worker.py` with scheduled jobs (integrations, image cache, rollups) |
| Tests | `pytest` per module against a real PostgreSQL schema; `vitest` for the frontend; gates in `scripts/gates/` |

## Constitution check

| Principle | How this plan honours it |
|---|---|
| I. Mobile-first, dashboard first | No new screen beyond a section on the source page; the dashboard renders as it does today |
| II. The backend does not query origins per request | **Amendment 3.2.0**: a source declared BI-ready is an optimized model *by declaration* — read-only, scoped, timed, capped, cached. Transactional origins stay behind integrations |
| IV. Folders | No new folder: the declaration is a column, the scope is data, the code lives in `engine/direct.py` and the sources API |
| VIII. AI is optional and private | Structure reads stay structure-only; the pack never carries values; a personal-data column needs a recorded decision |
| IX. Declarative, validated | Nothing new is authored in the product: a report declares `direct:` and the validator is the only door |

No `[GATE]` failures. The amendment is written **before** any code (Phase 0).

## Phasing

| Phase | What it delivers | Why first |
|---|---|---|
| 0 | Constitution 3.2.0, with a Sync Impact Report | The feature is only legal once II says so (same pattern as 046) |
| 1 | The declaration: `bi_ready` on the source, the save-time read-only proof, the audit kinds, the migration | Nothing can be read until the contract exists |
| 2 | Scope enforcement: validator + engine both consult it; `direct.tables` accepts `alias: schema.object` with columns from the structure | The value: an author writes no column list and cannot escape the scope |
| 3 | The source page: the "Lista para BI" section, the proven-read-only badge, the last-24h health from `direct_read_log` | The declaration must be visible and watchable |
| 4 | `materialize: daily` for direct reports | The only genuinely new engine path; last because it is optional for every report |
| 5 | Pack and docs: `describe` marks the source; `PROMPT.md`, `docs/AUTHORING.md`, `docs/INSTALL.md`, the guide topic | Document what ships |

## What this plan will *not* build (and why it says so)

- **The 043 WS-B "Descargar estructura" pack** (`sources/<name>/structure.md` + `structure.json`
  in a zip) was specified in 043 and never implemented: there is no `structure.md` in the code and
  no download endpoint. `describe` returns the same facts as JSON. This plan therefore **marks the
  `describe` payload** as BI-ready and scoped (FR-011's substance) and leaves the zip download to
  043 WS-B, rather than growing this feature a second front door.
- **Row-level security per user** and **cross-source joins**: out of scope in the spec, and the plan
  keeps them out.
- **A second set of limits**: the environment constants stay as the defaults a source overrides
  (research R4).

## Risks

| Risk | Mitigation |
|---|---|
| The scope check and the engine disagree, so something is readable that the validator refused | One function answers "may this object be read?", called by the validator **and** by the engine before connecting (research R2) |
| A customer's read-only proof passes a role that can still write through a `SECURITY DEFINER` function | The proof is empirical (a refused write in a rolled-back transaction) and repeated daily; the docs say the role must not own tables |
| `materialize: daily` turns into an ETL by accident | It stores the report's figures (the payload the engine already produces), never rows: the same boundary the cache has |
| 019 reports break | The old `direct.tables` shape and `source: bi` are kept and tested (FR-005, SC-006) |
