# Run report — 064 view as table

## Outcome

Every data card now opens its own rows as a table from the `⋯` menu, the table icon, a double-click
or `T`; `?tabla=<id>` is shareable, composes with `?ampliar=`, and the maximized dialog has a
**Gráfico | Tabla** switch. The table reuses the payload, formats like the chart, searches and sorts
across accent variants, copies TSV, downloads CSV and offers **Ver todas las filas** (`full=1`, 1,000
rows, 50 per page) when the engine says the view was cut. `data_table: false` (component) and
`interactions: {data_table: false}` (report) hide the entry points.

## Verification

| Command | Result |
|---|---|
| `cd backend && uv run pytest -q tests/test_reports_params.py tests/test_guide.py tests/test_guide_api.py tests/test_i18n_core.py` | passed |
| `cd cli && uv run pytest -q` | passed |
| `cd cli && uv run pytest -q tests/test_starter.py tests/test_authoring.py tests/test_i18n.py` | passed |
| `cd frontend && npx tsc -b` | passed |
| `cd frontend && npx vitest run` | 822 passed |
| `cd frontend && npm run build` | passed |
| `cd frontend && npx playwright test tests/e2e/data-table.spec.ts tests/e2e/layout-maximized.spec.ts --project=chromium-375` | 18 passed |
| `python3 scripts/check_docs_parity.py` | 92 pairs checked |
| `make starter-template` | regenerated (36 files) |

## Decisions

- No XLSX writer exists in the product; the button is skipped instead of inventing a format.
- Share links have no separate export flag; copy/CSV are hidden when `report.pdf` is false and the
  table remains readable.
- A component's table is its payload view resolved exactly like the card (`source_views` included);
  KPI sparklines render their series as a second small table.

## Pending for the human

- Nothing.
