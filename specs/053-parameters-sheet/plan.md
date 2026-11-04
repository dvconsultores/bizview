# Implementation Plan: Parámetros into the same sheet as Filtros

**Branch**: `053-parameters-sheet` | **Date**: 2026-11-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/053-parameters-sheet/spec.md`

## Summary

Feature 030 designed one `ReportSheet` with two tabs and only built the filters half: the report page
still opens a second, inline parameters card (`ParamBar`) that pushes the dashboard down and mixes
**EXPORTAR** with the parameters. This plan finishes the design in the frontend only.

`ReportSheet` gains an optional header tab strip (`role="tablist"`), `ParamBar` and `ExportSection`
disappear, the Parámetros tab becomes a real column of five labelled rows inside the same sheet, the
two downloads move to the actions row's `⋯` menu with one caption, and the non-default parameters
appear as removable chips next to the filter chips. Palette and light/dark join the URL (`theme`,
`mode`) so chips and reload work like filters. Both the private page (`ReportView`) and the shared
page (`SharedDashboard`) use the same sheet.

## Technical Context

**Language/Version**: TypeScript 5.x + React 19 on Vite (frontend only; no Python change)

**Primary Dependencies**: react-router 7 (`useSearchParams`), lucide-react icons, the existing
`ReportSheet`, `ParamsForm`, `AutoRefreshControl`, `PaletteSelect`, `ReportActions`, `FilterChips`,
`useTheme`/`themeStyle` (047) — no new dependency

**Storage**: URL query string (`period`, `from`, `to`, `compare`, `filter.*`, plus `theme`, `mode`);
`localStorage` for the auto-refresh mode and the viewer mode per report (existing helpers)

**Testing**: `npx tsc -b`, `npx vitest run` (jsdom, `tests/unit`), Playwright `tests/e2e/report-params.spec.ts`
and the appearance/auto-refresh specs, axe built into those specs

**Target Platform**: the product's web app, mobile-first (375 px) up to TV widths

**Project Type**: web application (frontend feature)

**Performance Goals**: one data request per change (250 ms debounce), no layout shift when the sheet
opens (it is an overlay), no re-render of the dashboard beyond the request it already makes

**Constraints**: no dialog/modal (constitution I and the `no-modals` gate), no colour literal in the
source (`no-raw-colors`), no user-visible literal outside `i18n` (`no-literals`), i18n parity es/en,
guide topics in both languages

**Scale/Scope**: 2 pages, 1 sheet component, 1 new tab-panel component, 2 controls reused, ~6 unit
test files touched, 1 e2e spec updated, 2 help topics (es/en) and the CHANGELOG

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | How this feature satisfies it |
| --- | --- | --- |
| I. Mobile-First, Always | every UI decision starts at 375 px | the same bottom sheet (≤72 %), tabs at the top, one control per row; desktop is the progressive enhancement |
| III. Source of Truth Is External | nothing about data moves | no schema, engine or endpoint change |
| IV. Separated Concerns by Folder | frontend changes under `frontend/src` | components in `components/report`, page wiring in `pages`, helpers in `lib` |
| V. Fixed Technology Stack | React + Tailwind + the design tokens | reuses `Select`, `Button`, `themeStyle`, existing tokens; no new library |
| VII. One Product, Many Installations | no literal colour, theme-driven | swatches paint with `themeStyle` + `bg-chart-N` roles |
| IX. Spec-Driven Reporting | the report definition is authored outside | palette/mode are view-only; nothing writes the definition |
| 030 FR-003 (no modals) | the panel is a landmark `region` | keeps `role="region"` + focus handling; tabs are not dialogs |

No violation, no complexity to justify.

## Project Structure

### Documentation (this feature)

```text
specs/053-parameters-sheet/
├── spec.md              # Requirements and decisions
├── plan.md              # This file
├── research.md          # Phase 0: what exists, what the brief changes, the URL contract
├── quickstart.md        # Phase 1: the eight manual checks
└── tasks.md             # Phase 2 (/speckit-tasks)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── components/report/
│   │   ├── ReportSheet.tsx          # + tabs (tablist/tab/tabpanel), heading stays for SR
│   │   ├── ReportParamsPanel.tsx    # NEW: the Parámetros tab content (five rows + footer actions)
│   │   ├── ParamsForm.tsx           # stacked variant: one row per control, label above
│   │   ├── ReportMetaLine.tsx       # + ParameterChips next to the filter chips
│   │   ├── ParameterChips.tsx       # NEW: removable chips for period/compare/palette/mode
│   │   ├── PaletteSelect.tsx        # + swatch row of the selected theme
│   │   ├── ReportActions.tsx        # menu items accept a caption line
│   │   ├── ParamBar.tsx             # DELETED
│   │   └── ExportSection.tsx        # DELETED
│   ├── pages/
│   │   ├── ReportView.tsx           # one sheet, two tabs; PDF/CSV in the ⋯ menu
│   │   └── SharedDashboard.tsx      # same sheet with the two tabs
│   ├── lib/
│   │   └── reportView.ts            # NEW: read/write `theme` and `mode` in the URL, validated
│   └── i18n/{es,en}.ts              # tabs, rows, chips, captions; export strings pruned
├── tests/unit/
│   ├── report-sheet.test.tsx        # tabs: roles, switching, arrows, focus
│   ├── params-sheet.test.tsx        # NEW: order of rows, Limpiar, flush on close, chips
│   ├── report-header.test.tsx       # both openers open the same sheet
│   ├── parameter-chips.test.tsx     # NEW: chips, removal, URL
│   ├── report-export.test.tsx       # ⋯ menu items + caption; ExportSection tests removed
│   └── no-literals.test.ts          # unchanged, must stay green after pruning strings
└── tests/e2e/
    └── report-params.spec.ts        # sheet tabs, reload keeps chips, ⋯ downloads, axe
```

**Structure Decision**: frontend-only change in the existing web app. `ReportSheet` owns the shell and
the a11y of the tabs; `ReportParamsPanel` owns the Parámetros content and its footer; `ReportView` and
`SharedDashboard` keep deciding *what* goes in each tab (the shared page passes only period and
comparison). The URL helpers live in `lib/reportView.ts` next to `reportQuery.ts`, so a chip and a
control use one implementation.

## Phase 0 — Research (see [research.md](./research.md))

Decisions taken there: the tab semantics and the accessible name of the panel; the URL keys and their
validation; what "default" means for palette and mode; how the flush-on-close interacts with the
debounce; and the exact strings to prune so `no-literals`/`i18n-parity` stay green.

## Phase 1 — Design (see [quickstart.md](./quickstart.md))

Contracts kept: `ReportSheet` props (additive `tabs`/`tab`/`onTabChange`, `title` still accepted for a
sheet without tabs), `ReportActions` items (additive `caption`), `ParamsForm` (`section`, `variant`
unchanged). Data model: no entity change; `ReportSelection` untouched; `ReportViewState` is
`{ theme: string | null; mode: ThemeMode | null }`, both URL-only.

## Phases

| Phase | Work |
| --- | --- |
| 1. Sheet shell | tabs in `ReportSheet`, arrow-key navigation, `aria-controls`/`aria-labelledby`, panel keeps focus handling |
| 2. Parámetros content | `ReportParamsPanel` with the five rows and the Limpiar/Listo footer; `ParamsForm` stacked rows; swatches in `PaletteSelect` |
| 3. Page wiring | one `panel` state with a tab, both openers, `theme`/`mode` URL helpers, flush on close, PDF/CSV in `⋯` |
| 4. Chips | `ParameterChips` beside `FilterChips`, removal resets defaults |
| 5. Removal | delete `ParamBar` and `ExportSection`, prune their strings, update the e2e that used `param-bar` |
| 6. Documentation | help topic *Parámetros y filtros del reporte* (es/en), CHANGELOG, 030 tasks convergence note |

## Verification

- `npx tsc -b` clean.
- `npx vitest run` green (all suites, not only the new ones).
- `npx vitest run tests/unit/no-literals.test.ts tests/unit/no-modals.test.ts tests/unit/i18n-parity.test.ts` green after the string pruning.
- `grep -r "param-bar\|ParamBar\|Generar reporte\|exportSection"` returns nothing under `src/`.
- Playwright `report-params.spec.ts`, `appearance.spec.ts` and `autorefresh.spec.ts` (they touch the
  same page) — run when the e2e stack is available; the unit + build gates above are the offline proof.
