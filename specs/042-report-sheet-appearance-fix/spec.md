# Feature Specification: Report sheet, Apariencia and KPI tiles — convergence of 030

**Feature Branch**: `042-report-sheet-appearance-fix`

**Created**: 2026-10-29

**Status**: Approved (owner prompt, 2026-10-29; design decisions written there are final)

**Input**: Owner, 2026-10-29, after reviewing `/r/panorama-cripto` and `/admin/apariencia` in
production. The 030 implementation diverged from its spec on three points; this feature closes
the gaps. The owner's full prompt is the authoritative text; this file condenses it.

## Diagnosed divergences (code evidence, 2026-10-29)

- **A — Parámetros is inline.** `ReportView.tsx` renders the legacy `ParamBar` block for
  `panel === "params"` while only `panel === "filters"` uses `ReportSheet` (030 FR-003 asked for
  both tabs in the sheet). The inline block pushes the dashboard down.
- **B — Palette appears dead.** The resolution order is report `layout.theme.palette` →
  installation preset → `impacto`; the generated report declares its own palette, so the
  Apariencia choice never shows. The Apariencia preview cards render no real components and the
  page ignores the standard admin container.
- **C — Tile types missing.** `gauge`, `share`, `index` and `asset` exist in no layer: the report
  schema enum ends at `kpi…spacer`, so reports fake them with empty KPIs («—»). KPI numbers have
  no compact formatting and the 3-tile row stretches across the page.

## Requirements (owner's design, binding)

### A. One `ReportSheet` for Filtros and Parámetros
- Desktop ≥1024px: right sheet 400px, full height under the header, non-modal (no backdrop,
  dashboard live), 200ms slide (none under reduced motion); Esc/× close and return focus.
- Phones: bottom sheet 72% height, drag handle, swipe down closes.
- Header + tabs `Filtros | Parámetros` (opener picks the tab), scrollable body, sticky footer
  `Limpiar` / `Listo`.
- Parámetros tab order: Período, Comparar con, Frecuencia, Paleta (swatch row, default «Usar la
  de la instalación»). Exportar moves to the actions-row «⋯» menu (PDF/CSV, helper line).
- Filtros tab: one control per declared filter; collapsible groups when >6; live apply (250ms).
- Chips under the meta line for applied filters and non-default parameters; `+N más` opens the
  sheet. URL keeps filters and parameters (reload/share restore).
- The inline `ParamBar` block disappears.

### B. Apariencia applies and looks standard
- Effective preset resolved once per report render into CSS custom properties on the report
  root; every chart, KPI, badge and the PDF palette read tokens, never literals.
- Saving persists `palette_preset`, invalidates the settings cache, next render uses it live.
- Standard admin container; preset cards grid 1/2/3 per row; apply-on-select + toast.
- Preview cards render a real mini dashboard (KPI+delta, 4-bar chart, 2-series sparkline) with
  the preset's colours, light and dark side by side, using the real components in `preview` mode.
- Presets stay as data (`frontend/src/theme/palettes/*.json`, mirrored for the PDF); the palette
  contrast check runs in CI for every preset × theme.

### C. KPI tiles
- Compact formatting for KPI values (`187,3 M` es / `187.3M` en; full value in tooltip and PDF);
  font steps down past 7 chars; numbers never wrap.
- New component types `gauge`, `share`, `index`, `asset` across schema, validator, types,
  renderer and PDF; an unimplemented type shows an explicit error card, never «—».
- Grid: 12 columns — tiles span 3 at ≥1280px, span 6 on tablets, full width on phones; 16px gaps.

## Constitution check
I (mobile-first; the sheet is non-modal — no modals rule respected), V (no new stack component;
a headless sheet primitive, if any, is a supporting library), VII (presets are product data),
every user-visible string in es and en. No amendment required.
