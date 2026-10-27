# Implementation Plan: Report render errors (038)

**Feature**: `038-report-render-errors` · [spec.md](./spec.md) · [tasks.md](./tasks.md)

## Technical context

| | |
|---|---|
| Backend | FastAPI + SQLAlchemy; the report engine (`app/engine/report.py`) and the PDF (`app/reports/`) |
| Storage | No migration: `project.preview` (JSONB) learns the `replaced` state |
| Frontend | React 19 + Tailwind: one card component, the layout renderer, the KPI row, the workspace page |
| i18n | `app/i18n/{es,en}.py` (`render.*`), `frontend/src/i18n/{es,en}.ts` (`report.errors`) |
| Tests | pytest (fixture project `coinmarketcap`, DB), vitest (cards), e2e unchanged |

## Constitution check

- **II / VI (ETL, optimized models)** — the engine keeps reading the optimized `ds_*` models or the
  preview schemas of the running preview; the new empty-dataset probe is `SELECT EXISTS` over those
  same tables and only when a view came back empty. No origin read is added. **PASS**.
- **VIII (AI optional and private; no data in logs or errors)** — every card is built from
  identifiers and fixed reason tokens (`division_by_zero`, `invalid_value`, …); psycopg's text is
  never used because it can quote the value that broke a cast. The reference id is the same one the
  ERROR line carries. **PASS**.
- **IX (spec-driven reporting) — unchanged**: the artifact schemas, validation codes and the
  authoring flow are untouched; the feature only changes what happens *after* a valid spec renders.
  **PASS**.
- **IV (separated concerns)** — engine codes in `app/engine/render_errors.py`, PDF cards in
  `app/reports/pdf_layout.py`, the preview lifecycle in `app/assistant/preview.py` and
  `app/projects/apply.py`, the page in `frontend/src/components/report/`.
- **V (fixed stack)** — no new dependency; ReportLab and FastAPI as they are.

Verdict: **PASS**, no amendment.

## Root cause (production 2026-10-26, `coinmarketcap` v22)

`apply_project` dropped the preview schemas (`drop_for_session`) but left `project.preview` at
`succeeded`. The workspace page renders «Vista previa» from that state, so the links stayed after the
apply. Pressing one built a context whose tables are in `preview_<session>__ds_mercado_cripto`, which
no longer existed: `psycopg.errors.UndefinedTable` escaped `run_views` (the rollup fallback re-raises
when there is no rollup) and the generic handler answered 500 with a reference. Two datasets joined
on `snapshot_at` were not at fault — the same report renders once the schemas exist (regression test
below).

## Decisions

1. **`RenderError` carries the code and the ids** (`app/engine/render_errors.py`), and `card()` is the
   payload shape a view or block carries. Codes are a closed catalogue in `CODES`.
2. **Translation at the query boundary.** `aggregate()` turns `pg_errors` into codes: an undefined
   table/schema is `preview_expired` inside a preview context and `dataset_missing` otherwise; a
   division by zero or a bad value is `metric_error`; an ambiguous column is `join_failed`. Unknown
   database errors still bubble to the 500 with the reference.
3. **Views fail individually.** `_run_views` wraps each view (`_run_view`); a `kpis` view whose
   combined query failed retries metric by metric (`_kpis_one_by_one`) so the row keeps the metrics
   that work. `_view_facts` (the summary sentence, totals) never breaks a view.
4. **Empty is a state.** A view with no numbers carries `empty` with `empty_dataset`; the datasets
   actually without rows are named by probing the report's own tables, only in that case.
5. **The preview lifecycle is closed.** `apply_project` writes `replaced` with the version in the
   same transaction as the apply (a second session would wait on its own row lock);
   `preview._context` answers `preview_expired` for `replaced`/`expired`, and when the preview
   schemas are gone it also persists `expired` so the page stops offering the links.
6. **PDF blocks are isolated** in `render_layout`: an unknown type or a failing block becomes a card
   (`layout_component_unknown` / `pdf_render`) with its id, and the fixed (non-declarative) story
   prints the card of a view that carries `error`/`empty`.
7. **One reference per payload** (`render_reference`) is included in every card and in the ERROR line,
   so the «Detalles técnicos» command finds the exact log entry.

## Out of scope

- Retrying a failed data query from the screen.
- Persisting the render cards in the report cache as errors (a cached payload is only stored when it
  was built; error cards are deterministic for the same data version).
- Changing the validation codes of the CLI (`unjoined_sets`, `unknown_dataset`, … remain theirs).
