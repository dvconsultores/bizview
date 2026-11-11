# Run report — 063 cross-filter

## Outcome

Implemented click-to-filter across bars, slices, legend entries, ranking rows, table dimension
cells and asset cards, with multi-select, chips, URL state, author switches and an
"except own dimension" view so the source chart keeps every value.

## Verification

| Command | Result |
|---------|--------|
| `cd backend && uv run pytest -q tests/test_guide.py tests/test_guide_api.py tests/test_reports_params.py` | passed |
| `cd frontend && npx tsc -b` | passed |
| `cd frontend && npx vitest run` | 808 passed |
| `cd frontend && npm run build` | passed |
| `cd frontend && npx playwright test tests/e2e/report-params.spec.ts` (cross-filter cases) | passed |
| `python3 scripts/check_docs_parity.py` | 91 pairs checked |
| `make starter-template` | regenerated |

## Notes

- `cross_filter: false` and `cross_filter: ignore` are covered by unit tests; the e2e workspace
  fixture declares a single dimension (`product`), so the AND/multi-dimension path and the
  author switches are unit-covered rather than e2e.
- Pre-existing, unrelated failures observed while working (unchanged by this feature):
  `frontend/tests/e2e/flows.spec.ts` ("Ventas" / "Ventas (layout)" switch), the
  `test_i18n_core.py` source-label mismatch, and `test_report_render_errors.py` expecting
  `PreviewVersion`.
