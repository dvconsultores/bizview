# Tasks: See the data behind any card as a table

**Feature**: `064-view-as-table` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

## Phase 1 — Backend

- [x] T001 `engine.report.view_ranking` / `view_table`: `truncated` flag and a 1,000-row cap when `full`
- [x] T002 `run_views` and `cross_views` accept `full`; `api.reports._data` reads `full=1` and keys the cache with it
- [x] T003 `backend/tests/test_reports_params.py`: truncated ranking, `full=1` rows, cache separation
- [x] T004 `api/types.ts`: `interactions.data_table`, component `data_table`, ranking/table `truncated`

## Phase 2 — Table model and dialog

- [x] T005 `frontend/src/lib/dataTable.ts`: `viewDataTable()` for kpis, trend, ranking, table; component column subset/order; comparison and share columns
- [x] T006 `components/report/CardDataTable.tsx`: sticky header, zebra, frozen first column, search, sort, counter, copy TSV + toast, CSV, pagination, row cross-filter, full-rows button
- [x] T007 `CardDialog.tsx`: **Gráfico | Tabla** segmented toggle for a maximized card
- [x] T008 `CardMenu.tsx`: **Ver como tabla** item (`onViewAsTable`) for every menu that has it
- [x] T009 `LayoutRenderer.tsx`: table icon next to Ampliar, `⋯` menu for chart cards, double-click and `T`, hide when `data_table:false`
- [x] T010 `ReportViews.tsx`: table icon on default cards and menu item, same double-click/T
- [x] T011 `ReportView.tsx`: `?tabla=`, standalone table dialog, full-rows request, maximized table mode and ← →, close behaviour
- [x] T012 `SharedDashboard.tsx`: read-only table dialog, copy/CSV hidden when the report disables export

## Phase 3 — Authoring and docs

- [x] T013 `report.schema.json`: report `interactions.data_table`, component `data_table`
- [x] T014 `cli/bizview_cli/validate.py`: validate the switch
- [x] T015 `docs/AUTHORING.md` + `docs/es/` and `docs/RENDERING.md` + `docs/es/`
- [x] T016 Starter pack PROMPT (ES/EN) and regenerated `bizview-starter-template.zip`
- [x] T017 Guide topic `ver-datos-grafico` (ES/EN) + `index.yaml`
- [x] T018 `es.ts` / `en.ts`: menu, title, search, counter, copy, copied, full rows, toggle labels
- [x] T019 CHANGELOG under Unreleased

## Phase 4 — Tests and gates

- [x] T020 Model unit tests: bar/ranking/table/trend/kpi shapes, comparison columns, title never an id
- [x] T021 Component unit tests: menu item, toggle, search, sort, copy, CSV, data_table false, row click
- [x] T022 E2E: open from menu/icon/double-click/T for bar, donut, KPI, trend; `?tabla=` round-trip; full rows; phone 360 + axe
- [x] T023 Gates: targeted `pytest`, `npx tsc -b`, `npx vitest run`, `npm run build`, docs parity, starter zip
