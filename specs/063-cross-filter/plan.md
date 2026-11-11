# Implementation Plan: Cross-filter from any chart, slice or ranking row

**Branch**: `063-cross-filter` | **Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md)

## Summary

A click becomes an ordinary report filter: the frontend toggles `filter.<dimension>=<value>` in the
URL, the engine accepts any declared dimension, and every view reloads with it. The engine also
returns the owning view computed without its own active dimension (`source_views`) so the source
chart keeps all its marks, and a no-cross-filter copy (`ignore_views`) for components declared
`ignore`. No new query shape, cache key or export path: a cross-filter is an ordinary filter.

## Technical Context

- Backend: Python 3.13, FastAPI, SQLAlchemy, SQLGlot; `backend/app/engine/report.py`.
- Frontend: React 19, TypeScript, Tailwind; `pages/ReportView.tsx`,
  `components/report/{LayoutRenderer,ReportViews,RankingTable,DataTable,charts/*}`.
- Authoring: `cli/bizview_cli/schemas/report.schema.json`, `validate.py`, `docs/`, starter pack.
- Storage: none; `report_cache` keeps the existing payload key (selection hash + data version).
- Constitution: no change. Declarative layouts keep the YAML as the only author control; the
  switches are booleans/enums, never code.

## Design

1. **Selection** — `filter.<id>` accepts any key of `definition.dimensions`; an unknown id raises
   `ReportError` 422 `unknown_filter`. `filters:` remains the sheet catalogue only.
2. **Key** — a dimension may carry `key`; `_where` uses `_filter_expr` (`key` or `sql`). Ranking and
   table payloads carry the key (`filter`, `__key_<dim>`) so a click filters by id and shows the
   label.
3. **Source/ignore views** — `cross_views()` computes, per active filter dimension, the views that
   use it with the other filters; and, when a cross-filter is present, the views with only sheet
   filters. The payload carries them as `source_views` / `ignore_views`.
4. **Frontend state** — `ReportView` owns one `CrossFilterState` (`toggle`), passed through
   `ReportViews`/`LayoutRenderer` to marks. URL serialization always includes every applied filter.
5. **Marks** — `BarChart`, `PieChart`, `RankingTable`, `DataTable`, `AssetGrid` expose
   `role=button`, `aria-pressed`, keyboard activation and a ≥32 px target; selected marks stay
   highlighted, other marks dim. Trend, totals and “otros” stay inert.
6. **Chips** — `FilterChips` builds from every applied filter; a multi-select collapses to one chip.
7. **Author switches** — report `interactions.cross_filter`, component `cross_filter:
   false|ignore`, enforced by the JSON schema and the validator.

## Phases

- Phase 1: engine selection/key/source views (P1).
- Phase 2: frontend marks, state, URL, chips, maximized card (P1/P2).
- Phase 3: schema, validator, docs, starter, help (P3).
- Phase 4: tests and gates.

## Decisions recorded in the spec

- `ignore` treats dimensions outside `filters:` as cross-filters, because the URL does not tag the
  origin of a filter; sheet-listed dimensions stay sheet-controllable.
- `key` is optional and backward compatible.
- No new query shape or cache table.
