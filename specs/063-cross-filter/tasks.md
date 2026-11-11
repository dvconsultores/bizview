# Tasks: Cross-filter from any chart, slice or ranking row

**Feature**: `063-cross-filter` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

## Phase 1 — Engine

- [x] T001 `backend/app/engine/report.py`: accept a filter on any declared dimension; unknown id → 422 `unknown_filter`
- [x] T002 Add `_filter_expr` and use it in `_where`; dimensions may declare `key`
- [x] T003 Expose ranking `filter` and table `__key_<dimension>` values for `key:` dimensions
- [x] T004 `cross_views()`: `source_views[dimension][view id]` and `ignore_views[view id]`
- [x] T005 `backend/app/api/reports.py`: include the cross views in the cached data payload

## Phase 2 — Frontend state and marks

- [x] T006 `frontend/src/lib/reportQuery.ts`: parse/serialize filters on any declared dimension
- [x] T007 `ReportView.tsx`: one `CrossFilterState` (toggle/additive/remove) and pass it to views and the maximized card
- [x] T008 `ReportViews.tsx` + `LayoutRenderer.tsx`: resolve `source_views`/`ignore_views`, honour `cross_filter: false|ignore`
- [x] T009 `BarChart.tsx`: clickable vertical/horizontal bars, highlight, dim, keyboard, hint
- [x] T010 `PieChart.tsx`: clickable slices and legend entries, `otros` inert
- [x] T011 `RankingTable.tsx`: clickable rows with `aria-pressed` and a 32 px target
- [x] T012 `DataTable.tsx`: clickable dimension cells
- [x] T013 `AssetGrid.tsx`: clickable cards when the title column is a declared dimension
- [x] T014 `FilterChips.tsx`: chips for every applied filter; multi-select count; remove all
- [x] T015 `es.ts` / `en.ts`: hint, count and remove-all labels

## Phase 3 — Authoring and docs

- [x] T016 `cli/bizview_cli/schemas/report.schema.json`: `interactions.cross_filter`, component `cross_filter`, dimension `key`
- [x] T017 `cli/bizview_cli/validate.py`: validate the `key` expression
- [x] T018 `docs/AUTHORING.md`, `docs/es/AUTHORING.md`, `docs/RENDERING.md`, `docs/es/RENDERING.md`
- [x] T019 Starter pack PROMPT (ES/EN) and regenerated `bizview-starter-template.zip`
- [x] T020 Guide topic `filtrar-haciendo-clic` (ES/EN) + `index.yaml`
- [x] T021 CHANGELOG under Unreleased

## Phase 4 — Tests and gates

- [x] T022 Engine: any declared dimension, unknown id 422, `key` filter, source/ignore payload
- [x] T023 Frontend unit: query round-trip, chips, mark keyboard/aria
- [x] T024 E2E: click a `producto` bar, chip, URL, KPIs, source chart; Ctrl-click; second dimension; switches
- [x] T025 Gates: targeted `pytest`, `npx vitest run`, `tsc -b`, `npm run build`, `make starter-template`
