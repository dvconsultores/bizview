# Tasks: 042-report-sheet-appearance-fix

Batches are DeepSeek briefs; each lands with its tests before the next starts.

## Batch A — the sheet
- [ ] T001 `ReportSheet` gains tabs (`Filtros | Parámetros`), 400px desktop width, 72% bottom
      sheet, sticky footer `Limpiar`/`Listo`.
- [ ] T002 `ReportView` opens the sheet for both buttons (opener picks the tab) and the inline
      `ParamBar` block is removed (`ParamBar.tsx` deleted or reduced to the sheet content).
- [ ] T003 Exportar moves to the actions-row «⋯» menu (PDF/CSV + helper line).
- [ ] T004 Chips: non-default parameters join the filter chips; `+N más` opens the sheet.
- [ ] T005 Filters tab renders every declared filter (fixture with 8 filters); empty state named.
- [ ] T006 Tests: viewport placement, non-modal interaction, tabs, Esc/focus, debounce, chips,
      URL round trip, reduced motion.

## Batch B — Apariencia and palette
- [ ] T007 Effective preset resolved once onto the report root as CSS variables; components and
      PDF read tokens only (audit for literal colours).
- [ ] T008 Apariencia uses the standard admin container; preset cards grid; apply-on-select +
      toast; cache invalidation so the open report re-themes without reload.
- [ ] T009 Preview cards render the real components in `preview` mode (KPI+delta, 4-bar, 2-series
      sparkline) light and dark side by side.
- [ ] T010 Palette contrast check in CI for every preset × theme.
- [ ] T011 Tests: preset switch changes `--series-1`/`--c-chart-1` on a rendered report; preview
      snapshots per preset × theme.

## Batch C — tiles
- [ ] T012 Compact number formatting (es/en) with tooltip + PDF full value; step-down size; no
      wrapping.
- [ ] T013 Schema + validator + types: `gauge`, `share`, `index`, `asset`.
- [ ] T014 Renderer components for the four types; unknown/unimplemented type → error card.
- [ ] T015 Grid spans (3/6/12) and 16px gaps.
- [ ] T016 Tests: formatting table, each type from the CoinMarketCap fixture, error card,
      grid snapshots 375/768/1280/1920.

## Batch D — polish and docs
- [ ] T017 `es.ts`/`en.ts` strings; CHANGELOG (Unreleased); guide topics «Parámetros y filtros
      del reporte» and «Apariencia»; 030 tasks.md Convergence phase.
- [ ] T018 Full frontend suite + affected backend suites green; owner deploys and verifies.
