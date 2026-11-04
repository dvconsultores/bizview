# Phase 0 — Research: Parámetros into the same sheet as Filtros

**Feature**: 053-parameters-sheet · **Date**: 2026-11-04

## What exists today

| Piece | Path | State |
| --- | --- | --- |
| Sheet shell | `src/components/report/ReportSheet.tsx` | landmark `region`, focus cycle, Esc, outside-click on desktop, bottom sheet ≤70 vh on phones; **one title, no tabs** |
| Filters panel | `ParamsForm` (`section="filters"`, `live`) inside `ReportSheet` | live 250 ms debounce, `Limpiar todo` in its own footer |
| Parameters card | `ParamBar.tsx` → `ParamsForm variant="bar"` + `AutoRefreshControl compact` + `PaletteSelect compact` + `ExportSection` | **the reported defect**: inline card, fields in one row, export block inside |
| Export block | `ExportSection.tsx` | PDF/CSV radio + `Generar reporte`, only reachable from the parameters card |
| Actions row | `ReportActions.tsx` | Filtros + Parámetros visible, everything else in the `⋯` menu (PDF already there); no caption support |
| Chips | `FilterChips.tsx` (via `ReportMetaLine`) | filter values only; "+N más" opens Filtros |
| Palette | `PaletteSelect.tsx` | preview for the view, `Copy` snippet, `Usar la de la instalación`; no swatch row |
| Theme mode | `src/theme/library.ts` (`readViewerMode`/`writeViewerMode`) + `ReportView.toggleMode` | a sun/moon action in the `⋯` menu, stored per report, **not in the URL** |
| Refresh | `useAutoRefreshMode(id)` + `AutoRefreshControl` | per report in `localStorage` |
| URL | `src/lib/reportQuery.ts` | `period`, `from`, `to`, `compare`, `filter.<id>`; validated against the definition |
| Shared page | `src/pages/SharedDashboard.tsx` | same `ReportSheet` + `ParamBar` (no refresh/palette/mode), PDF pinned in the row |

## Decisions researched

### 1. Tab semantics without a modal

`ReportSheet` stays `role="region"` with an `h2` that names the sheet (`aria-labelledby`). The tab
strip goes *inside* the header: `role="tablist"` with `aria-label` = the report's title, one
`role="tab"` per tab carrying `aria-selected` and `aria-controls="<panelId>"`, and the body becomes
`role="tabpanel"` with `aria-labelledby="<tabId>"` and `tabIndex={0}`. The heading keeps a `sr-only`
copy so the region still has an accessible name (axe `aria-required-children`/`region` rules).

Arrow keys: **optional activation** is not worth it here — two tabs, no async — so ArrowLeft/ArrowRight
move focus *and* select (automatic activation), Home/End jump to the first/last. `Tab` from the strip
enters the panel (the panel is the next focusable). The existing focus cycle and Esc handling stay
untouched.

Rejected: a `<fieldset>`/radio pair (looks like a form, not navigation) and a route change per tab
(the dashboard would reload and the URL would carry UI state the brief does not ask for).

### 2. URL keys for the viewer's view

| Key | Values | Default | Validation |
| --- | --- | --- | --- |
| `theme` | a preset id (`impacto`, `clasico`, `elegante`, `monocromo`, `contraste`, `daltonico`) | absent → the report's declared theme, else the installation's | `isPaletteId` (existing helper) |
| `mode` | `light` \| `dark` | absent → the report's `layout.theme.mode`, else the app's resolved mode | exact match |

A key that fails validation is ignored (no chip, no error), matching how `period`/`compare` behave.
The viewer mode is still written to `localStorage` per report (`writeViewerMode`) so the next visit
opens the same way; the URL wins on load when present. Removing the Tema chip clears both.

Rejected: putting `refresh` in the URL — a cadence is a device preference and the brief does not list
a chip for it.

### 3. Flush on close

`ParamsForm` debounces with a `setTimeout` owned by the panel, so unmounting the sheet (Listo, ×, Esc)
would cancel a change made in the last 250 ms. The panel therefore applies a pending *valid* draft in
its unmount cleanup (`validateSelection` + `isIncompleteCustom` are already the gate). The pending
apply is idempotent (`apply()` compares with `sameSelection` and no-ops), so a double flush is safe.

### 4. Swatch row for the palette

`themeStyle(theme, mode)` (047) turns a theme into the `--c-*` custom properties, and `Appearance.tsx`
already draws series bars with `bg-chart-1..8` inside a `data-theme="preview"` container. The palette
row reuses exactly that: one line of eight role-coloured swatches for the selected preset, painted from
`BUILTIN_THEMES[id]` in the current area mode. No hex literal enters the source (the `no-raw-colors`
gate scans for them).

### 5. Where export goes

`ReportActions` items already render icon + label in the `⋯` menu. Adding an optional `caption` to the
menu body (rendered once, under the items) carries the sentence that used to sit in `ExportSection`
("The applied selection is exported." / "Wait for the report to finish loading."). CSV joins PDF as a
menu item gated by `csvAvailable` (a table or ranking view with rows in the applied selection) and
reuses `exportCsv`, which already exports what is on screen.

### 6. Strings to prune (so the gates stay green)

`reportParams.exportSection`, `exportFormat`, `formatPdf`, `formatCsv`, `generate`, `exportApplied`
becomes the menu caption (`exportCaptionApplied`/`exportCaptionLoading`), and the `reportParams.apply`,
`pending`, `noPending` keys go with the non-live footer of `ParamsForm`. `t.reportParams.clear` stays
(the Parámetros footer uses it). `i18n-parity` compares key sets between `es` and `en`, so both files
change together.

## Open questions

None. Every ambiguity is recorded in the spec's "Decisiones tomadas (modo autónomo)".
