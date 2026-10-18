# Implementation Plan: Report parameters panel

**Branch**: `012-report-params-panel` | **Date**: 2026-10-01 | **Spec**: [spec.md](./spec.md)

## Summary

Superset-style "Filtros y controles" panel (desktop, collapsible) / view (phones) with an
Customer A-style form: draft state applied with one action, URL as the applied state, multi-value
filters (backend `IN` with bound values), a context block with removable chips, and CSV export
built client-side from the loaded views. Runs after features 009/010.

## Technical Context

Python 3.12 / FastAPI (backend engine + reports API), TypeScript / React 19 / Tailwind (frontend).
No new libraries. Testing: pytest on DATABASE_URL_BI (`app_test_*`), Vitest, Playwright.

## Constitution Check

PASS: report specs unchanged (IX); values bound by psycopg, filters validated against the report's
declared list (security constraint); views not modals; tokens only; mobile-first; JSON API.

## Design

### Backend
- `engine/report.py` filter parsing: `filter.<id>` may repeat; collect a list per declared filter
  (unknown ids ignored as today); empty list = no filter; condition `dim_expr IN (%s, …)` built with
  `sql.Literal` per value; max 50 values per filter (more → 422 `too_many_values`).
- `api/reports.py`: pass `request.query_params.multi_items()` (not `dict(...)`, which drops repeats)
  to `engine.selection`/filter parsing for data, narrative, filters and PDF; cache key includes the
  sorted values.
- `GET /api/reports/{id}/filters/{dim}?q=` optional case-insensitive contains search (bound
  `ILIKE`, escaped `%`/`_`), still limit 200, response `{items, truncated: bool}`.

### Frontend
- `lib/reportQuery.ts`: parse/serialise selection ⇄ URLSearchParams (repeated `filter.<id>`), with
  backward compatibility; pure, unit-tested.
- `lib/csv.ts`: `toCsv(columns, rows)` → UTF-8 BOM, `;` separator, `\r\n`, RFC 4180 quoting, numbers
  with dot decimals unformatted, dates ISO; `downloadCsv(name, text)`.
- `components/report/ParamsForm.tsx`: sections Período (select + Desde/Hasta), Comparar con
  (segmented or read-only), Filtros (`MultiSelect` per filter), Exportar (radio PDF/CSV + "Generar
  reporte"); draft vs applied, pending count, "Aplicar filtros" / "Limpiar todo"; validation.
- `components/MultiSelect.tsx`: accessible combobox (input + listbox, `aria-multiselectable`),
  searchable (server `q` after 250 ms debounce), selected values as chips, keyboard support.
- `components/report/ParamsPanel.tsx`: desktop aside `w-80` sticky, collapsible (`localStorage`
  "bizview.reportPanel" try/catch), header "Filtros y controles" + collapse button.
- `components/report/ContextBlock.tsx`: Período, Comparado con, Datos actualizados, chips.
- `components/report/CardMenu.tsx`: "⋮" menu button on table/ranking cards → "Descargar CSV".
- `pages/ReportView.tsx`: layout `lg:grid lg:grid-cols-[20rem_1fr]` (panel + content), phones: "Filtros
  (n)" button opening a `View` with `ParamsForm`.

## Structure

backend/app/engine/report.py, backend/app/api/reports.py, backend/tests/test_reports*.py;
frontend/src/lib/{reportQuery,csv}.ts, frontend/src/components/{MultiSelect}.tsx,
frontend/src/components/report/{ParamsForm,ParamsPanel,ContextBlock,CardMenu}.tsx,
frontend/src/pages/ReportView.tsx, frontend/tests/unit/{report-query,csv,params-form}.test.ts(x),
frontend/tests/e2e/report-params.spec.ts.

## Decisions after convergence (2026-10-02)

- The context block keeps a "Descargar PDF" quick action besides the panel's Exportar section,
  because on phones the panel is a separate view; both use the same applied selection. Its label
  comes from `t.reportParams.downloadPdf` in frontend/src/i18n/es.ts (accessible name unchanged).
- "Comparar con" offers exactly the report's `compare.allowed` list.
