# Tasks: Parámetros into the same sheet as Filtros

**Feature**: `053-parameters-sheet` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Legend: `[P]` parallel-safe, `[US1]`…`[US5]` user story from the spec. Order is execution order; a
task is ticked only when it is implemented and its file exists.

## Phase 1 — the sheet grows tabs (FR-001, US1, US5)

- [x] T001 `frontend/src/components/report/ReportSheet.tsx`: optional `tabs`
      (`{ id, label }[]`), `tab`, `onTabChange`; header renders `role="tablist"` +
      `role="tab"`/`aria-selected`/`aria-controls`, body becomes `role="tabpanel"` with
      `aria-labelledby` and `tabIndex={0}`; the `h2` keeps the region's accessible name (visually
      hidden when tabs are present); ArrowLeft/ArrowRight/Home/End select; Esc, focus cycle,
      outside click and reduced motion unchanged
- [x] T002 `[P]` `frontend/tests/unit/report-sheet.test.tsx`: tablist roles, selection, arrow keys,
      panel labelling, and the no-tabs sheet still has no tablist
- [x] T003 `frontend/src/i18n/es.ts` + `en.ts`: `reportSheet.tabs` labels (`filters`, `params`) and
      `reportSheet.tabsLabel`

## Phase 2 — the Parámetros tab content (FR-004…FR-007, US2)

- [x] T004 `frontend/src/components/report/ParamsForm.tsx`: `variant="stacked"` renders one control
      per row with the label above (no `bar` row), keeps `section`, the 250 ms debounce and a
      flush of a pending valid draft on unmount; drop the non-live footer (`apply`, pending status)
- [x] T005 `frontend/src/components/report/PaletteSelect.tsx`: swatch row of the selected theme
      (`themeStyle` + `bg-chart-1..8`, `data-theme="preview"`) and the installation option first;
      remove the `compact` variant with `ParamBar`
- [x] T006 `frontend/src/components/report/ReportParamsPanel.tsx` (new): the five rows in order
      (Período, Comparar con, Frecuencia de actualización, Paleta, Tema del reporte — the last only
      when the report declares a theme), with `Limpiar` and `Listo` in the sheet footer
- [x] T007 `frontend/src/i18n/es.ts` + `en.ts`: `reportParams.theme`/`themeAuto`/`themeLight`/
      `themeDark`, `palette.installation` reuse, `reportSheet.clear`/`done` for the footer
- [x] T008 `[P]` `frontend/tests/unit/params-sheet.test.tsx` (new): row order, read-only comparison
      when only one option exists, theme row hidden without a declared theme, `Limpiar` restores
      defaults, a pending draft is applied when the panel closes

## Phase 3 — the page: one sheet, two openers (FR-002, FR-003, US1)

- [x] T009 `frontend/src/pages/ReportView.tsx`: one `panel: "filters" | "params" | null` state, both
      openers open the sheet on their tab, the open one closes it, `ReportSheet` receives the tabs
      and the panel renders `ParamsForm section="filters"` or `ReportParamsPanel`
- [x] T010 `frontend/src/pages/SharedDashboard.tsx`: same sheet and tabs, Parámetros with period and
      comparison only (no refresh/palette/mode)
- [x] T011 Delete `frontend/src/components/report/ParamBar.tsx` and
      `frontend/src/components/report/ExportSection.tsx`; prune `reportParams.exportSection`,
      `exportFormat`, `formatPdf`, `formatCsv`, `generate`, `apply`, `pending`, `noPending` from both
      catalogues
- [x] T012 `[P]` `frontend/tests/unit/report-header.test.tsx`: both openers open the same
      `report-sheet` on the right tab; pressing the open one closes it

## Phase 4 — export in the ⋯ menu (FR-008, US3)

- [x] T013 `frontend/src/components/report/ReportActions.tsx`: optional `caption` rendered once in
      the menu body, below the items with `text-xs text-ink-muted`
- [x] T014 `frontend/src/pages/ReportView.tsx`: add the `csv` action (gated by `csvAvailable`) and
      the caption (`reportParams.exportCaptionApplied` / `exportCaptionLoading`)
- [x] T015 `[P]` `frontend/tests/unit/report-export.test.tsx`: PDF and CSV items in the menu, the
      caption in both states, `ExportSection` tests removed

## Phase 5 — the URL for the viewer's view and its chips (FR-009, FR-012, US4)

- [x] T016 `frontend/src/lib/reportView.ts` (new): `parseViewState(params)` (validated `theme`,
      `mode`), `serializeViewState(state, params)` (removes one key at a time),
      `isDefaultViewState`
- [x] T017 `frontend/src/pages/ReportView.tsx`: read `theme`/`mode` from the URL (URL wins over the
      stored value), write them on change, remove them on `Limpiar`, clear the stored mode with the
      Tema chip
- [x] T018 `frontend/src/components/report/ParameterChips.tsx` (new) +
      `frontend/src/components/report/ReportMetaLine.tsx`: chips `Período: …`, `vs …`,
      `Paleta: …`, `Tema: …` beside the filter chips, removable, no overflow
- [x] T019 `frontend/src/i18n/es.ts` + `en.ts`: `reportParams.chipPeriod`, `chipCompare`,
      `chipPalette`, `chipTheme`, `removeParamChip(label, value)`
- [x] T020 `[P]` `frontend/tests/unit/parameter-chips.test.tsx` (new): chip per non-default value,
      removal resets the default and rewrites the URL, defaults show nothing

## Phase 6 — documentation (FR-014)

- [x] T021 `backend/app/guide/es/parametros-y-filtros-del-reporte.md` and its English twin
      (033): the two tabs, what each holds, the chips, where export lives, phones
- [x] T022 `backend/app/guide/index.yaml`: the topic entry (section, roles, aliases, related) — the
      help page builds its list from there, not from `_ayuda.md`
- [x] T023 `CHANGELOG.md` under Unreleased: **Changed** (one sheet with two tabs, export to the ⋯
      menu, parameter chips) and **Removed** (the inline parameters card, `Generar reporte`)
- [x] T024 `specs/030-report-page-polish/tasks.md`: convergence note — FR-003's Parámetros tab
      finished by 053

## Phase 7 — e2e and gates (US5, SC-001…SC-005)

- [x] T025 `frontend/tests/e2e/report-params.spec.ts`: `param-bar` replaced by the sheet's
      Parámetros tab; open → change Período → Listo → chip present → reload keeps it; `⋯` downloads
      PDF/CSV; axe on both tabs
- [x] T026 `frontend/tests/e2e/appearance.spec.ts` + `autorefresh.spec.ts`: they reach the sheet
      through the Parámetros tab instead of `param-bar`
- [x] T027 Gates: `npx tsc -b`, `npx vitest run`, and
      `grep -rn "param-bar\|ParamBar\|Generar reporte\|exportSection" src` empty
