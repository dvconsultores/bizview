# Run report — 053-parameters-sheet

**Request**: the owner's brief of 2026-11-04 (*Parámetros moves into the same right sheet as
Filtros*), run as specify → clarify → plan → tasks → analyze → implement → converge → verify.

**Feature**: `specs/053-parameters-sheet/` · **Branch**: `main` (no branch created, per the
repository rules)

## Stages

| # | Stage | Result |
| --- | --- | --- |
| 1 | specify | [spec.md](./spec.md) — 5 user stories, FR-001…FR-014, SC-001…SC-005, 4 decisions |
| 2 | clarify | 5 decisions added (flush on close, footer controls, chip overflow, clearing the stored mode, refresh stays device-local) |
| 3 | plan | [plan.md](./plan.md) — frontend-only, constitution check, file-by-file structure |
| 4 | research | [research.md](./research.md) — what exists, tab semantics, URL contract, flush, swatches, strings to prune |
| 5 | quickstart | [quickstart.md](./quickstart.md) — the automated gates and the eight manual checks |
| 6 | tasks | [tasks.md](./tasks.md) — 27 tasks, all implemented and ticked |
| 7 | analyze | 2 decisions (no dead `variant` prop; one caption for the pair of downloads) |
| 8 | implement | 1 deleted component pair, 3 new source files, 6 test files, docs and guide |
| 9 | converge | 2 decisions (no visual-snapshot baseline; e2e not run here) |
| 10 | verify | see below |

## What changed

- `ReportSheet`: optional header tab strip (`role="tablist"`/`tab`/`tabpanel`, `aria-controls`,
  ArrowLeft/ArrowRight/Home/End, one tab stop), heading kept for assistive technology, still a
  `region`.
- `ReportParamsPanel` (new): Período, Comparar con, Frecuencia de actualización, Paleta, Tema del
  reporte — one per row, the last only when the report declares a theme.
- `ParamsForm`: stacked layout only, pending draft flushed when the panel closes; the non-live footer
  survives for a layout's `filters` component.
- `PaletteSelect`: swatch row of the selected theme (`themeStyle` + `bg-chart-N`), no compact variant.
- `ParameterChips` (new) + `ReportMetaLine`: chips for period, comparison, palette and theme.
- `lib/reportView.ts` (new): `theme`/`mode` URL contract, `togglePanel`.
- `ReportView` / `SharedDashboard`: one sheet, two openers, PDF/CSV in `⋯` with the caption,
  `Limpiar`/`Listo` in the sheet footer.
- Deleted: `ParamBar.tsx`, `ExportSection.tsx`, and their strings (**Generar reporte**, the format
  radio, **EXPORTAR**).
- Docs: help topic *Parámetros y filtros del reporte* (es/en) + index entry, the filters and export
  topics updated to the two tabs, `specs/030` convergence note, CHANGELOG (Changed + Removed).

## Verification

| Check | Command | Result |
| --- | --- | --- |
| Types | `npx tsc -b` | clean |
| Unit suite | `npx vitest run` | 66 files, **698 passed** (new: `params-sheet.test.tsx`, `parameter-chips.test.tsx`; updated: `report-sheet`, `report-header`, `report-export`, `params-form`, `guide-drift`) |
| Build | `npm run build` | ✓ built |
| Design gates | `vitest run no-literals, no-modals, i18n-parity, no-raw-colors` | 18 passed |
| Removal gate | `grep -rn "param-bar\|ParamBar\|Generar reporte\|exportSection" src tests` | no matches |
| Guide | `pytest tests/test_guide.py tests/test_guide_api.py` | 12 passed (topic count 52 → 53) |
| Playwright | `tests/e2e/report-params.spec.ts`, `appearance`, `autorefresh` | updated (sheet tab instead of `param-bar`, ⋯ downloads, the reload journey, four widths × two themes); **not executed** — the suite boots a backend that rebuilds a throwaway schema over the external database (minutes), and no visual-snapshot baseline exists in this repository |

## Decisions recorded in the spec

11 entries under *Decisiones tomadas (modo autónomo)* — the two from `specify` that the plan must not
reopen, five from `clarify`, two from `analyze` and two from `converge`.

## Pending for the human

- Review the Parámetros tab on a real report at 375 px and at 1280 px (the layout is a column of five
  rows now, and the swatch row is new): the numbers behind it and the chips after **Listo**.
- Nothing needs applying from this side: the feature is frontend-only and the report definitions,
  data and engines are untouched.
