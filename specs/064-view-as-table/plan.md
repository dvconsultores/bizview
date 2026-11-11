# Implementation Plan: See the data behind any card as a table

**Branch**: `064-view-as-table` | **Date**: 2026-11-11 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/064-view-as-table/spec.md`

## Summary

Every data card gets a **Ver como tabla** action that opens a dialog with the rows the card already
has in memory, formatted as the chart is. The work is mostly frontend: one pure model turns any
payload view into columns and rows, one dialog renders it with search/sort/copy/CSV, and the report
page owns `?tabla=<id>` so the state is shareable. The only backend change is the existing data
route's `full=1`, which lifts the ranking/table `limit` for **Ver todas las filas** (max 1,000) and
reports whether a view was truncated.

## Technical Context

**Language/Version**: TypeScript 5.x + React 19 (frontend), Python 3.12 + FastAPI/SQLAlchemy
(backend).

**Primary Dependencies**: react-router `useSearchParams`, lucide-react icons, existing `formatValue`,
`localized`, `downloadCsv`/`toCsv`, Vitest + Testing Library, Playwright.

**Storage**: no new table; the backend cache stores the `full=1` payload under its own key.

**Testing**: `npx vitest run`, `npx tsc -b`, `npm run build`, targeted `uv run pytest`, Playwright.

**Target Platform**: the existing SPA and API; desktop and 360 px phones, light and dark.

**Constraints**: no new request for the normal dialog; no XLSX format exists; no new modal pattern
(`no-modals.test.ts` allows only `CardDialog`).

**Scale/Scope**: 12 card kinds, two entry surfaces (card + maximized dialog), one report URL key.

## Constitution Check

- Declarative authoring only: `data_table` is an optional switch, no new SQL or layout shape.
- The payload stays the source of truth: the table reuses it, it never recomputes a metric.
- Accessibility is part of the contract: table semantics, focus trap, 44 px targets, axe.
- No change to the constitution is required.

## Project Structure

```text
specs/064-view-as-table/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
└── tasks.md

backend/app/api/reports.py          # full=1 and cache key
backend/app/engine/report.py        # limit override + truncated flags
backend/tests/test_reports_params.py

frontend/src/api/types.ts           # interactions.data_table, component flag, truncated
frontend/src/lib/dataTable.ts       # view → columns/rows model
frontend/src/components/report/CardDataTable.tsx
frontend/src/components/report/CardDialog.tsx       # Gráfico | Tabla toggle
frontend/src/components/report/CardMenu.tsx         # Ver como tabla item
frontend/src/components/report/LayoutRenderer.tsx   # icon, menu, dblclick/T
frontend/src/components/report/ReportViews.tsx      # default cards
frontend/src/pages/ReportView.tsx                   # ?tabla=, full fetch
frontend/src/pages/SharedDashboard.tsx              # read-only table
frontend/src/i18n/es.ts / en.ts

cli/bizview_cli/schemas/report.schema.json
cli/bizview_cli/validate.py
docs/AUTHORING.md / docs/es/AUTHORING.md
docs/RENDERING.md / docs/es/RENDERING.md
pack/bizview-starter-pack/{es,en}/PROMPT.md
backend/app/guide/{es,en}/ver-datos-grafico.md
CHANGELOG.md
```

## Phase 0 — Research decisions

- The payload view is the only source; `viewCsvTable` is extended conceptually by a new
  `viewDataTable` that understands every `ReportView` shape (kpis, trend, ranking, table).
- The card id is the routing key: layout components use their `id`, default cards use
  `view-<n>` (056).
- The table dialog reuses `CardDialog` so there is one modal and one focus trap.
- Share links have no export flag; hide copy/CSV when `report.pdf` is false and keep the table.

## Phase 1 — Data model and contract

- `DataTableColumn { id, label, kind, format?, align }`
- `DataTableRow { id, cells: (string|number|null)[], dimension?, value?, selected? }`
- `DataTableModel { title, columns, rows, truncated }`
- `GET /api/reports/{id}/data?full=1` returns the same payload with ranking/table views up to 1,000
  rows and `truncated` on those views; the cache key gains `:full`.

## Phase 2 — Implementation

1. Backend `full` + `truncated` + tests.
2. `dataTable.ts` model + unit tests.
3. `CardDataTable` with search, sort, copy, CSV, pagination, row cross-filter.
4. `CardMenu` item, card icon, double-click and `T` in `LayoutRenderer`/`ReportViews`.
5. `CardDialog` toggle; `ReportView` `?tabla=` + full fetch; `SharedDashboard` read-only table.
6. Schema/validator/docs/help/starter/CHANGELOG; regenerate template zip.
7. Unit + e2e verification.

## Complexity Tracking

No constitution violations. The only deliberate duplication is a table renderer next to
`DataTable`/`RankingTable`; it serves a dialog with search/sort/copy, a different contract from the
dashboard's table card.
