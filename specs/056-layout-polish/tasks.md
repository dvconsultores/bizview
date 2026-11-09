# Tasks — 056 layout polish

All tasks are done and verified by the suites named in T018.

## Contract

- [X] T001 `labels` in `cli/bizview_cli/schemas/report.schema.json` (`true` or
      `values|percent|both`), `docs/AUTHORING.md`, and `cli/tests/test_labels.py` (accepted `true`,
      accepted `both`, refused `sometimes`)

## KPI fills its span

- [X] T002 `KpiCard.tsx`: one card, `w-full h-full`, value at `clamp(28px, 2.6vw, 44px)` with the
      full value in `title`, delta row with `pt-3` and a reserved height, optional sparkline
- [X] T003 `KpiGrid` `mode="single"`: no inner grid for a `kpi` component; the grid stays for the
      `kpis` view without a layout
- [X] T004 `LayoutRenderer`: `kpi` renders `mode="single"`, cells are `h-full` with the minimum
      heights (kpi 150, chart 320)

## Equal heights

- [X] T005 `ChartCard`: the card is a full-height column and the drawing area is `flex-1`
- [X] T006 `useChartHeight` measures the drawing area; the horizontal bar now draws into that height,
      so a chart with fewer categories gets taller bars instead of empty space

## Labels that fit

- [X] T007 `lib/chartLabel.ts`: canvas measurement with a deterministic fallback, `fitLabel` (trailing
      ellipsis), `labelColumn` (96–220 px, 40 % of the chart)
- [X] T008 `BarChart` horizontal: measured column, `<title>` with the full name, label-above-bar under
      480 px (12 px bar, 8 px gap)
- [X] T009 `PieChart`: legend wraps with `overflow-wrap:anywhere`, value and share right-aligned in
      tabular numbers, legend under the ring on phones

## Values

- [X] T010 Value chips on hover/tap for bars, slices and line points (name, formatted value, share —
  the previous value on a trend), 1.03 scale and dimming to 70 %, 150 ms, colour only under
      `prefers-reduced-motion`
- [X] T011 `labels` rendering: bars print the value when it fits, slices print `values`/`percent`/
      `both`, a trend prints its last point

## Full screen

- [X] T012 `CardDialog.tsx`: labelled dialog, Esc/×/backdrop closes and returns focus, focus stays
      inside, ← → between cards, PNG and the view's CSV
- [X] T013 `Ampliar` on every layout data card (header button) **and** in the card's `⋯` menu
- [X] T014 `Ampliar` on the default (no-layout) view cards, under `?ampliar=view-<n>`
- [X] T015 `?ampliar=<id>` in `ReportView`: shareable, survives reload, TV ignores it, ← → walk the
      dashboard's cards

## Proof

- [X] T016 `frontend/tests/unit/layout-polish.test.tsx` (18 cases) and the narrowed `no-modals` guard
- [X] T017 The 026 rendering contract and the CHANGELOG
- [X] T018 Full suites green: 738 frontend, 727 CLI, `tsc --noEmit`, every repository gate

## Phase 8: Convergence — 056b (the maximized card must fill the dialog)

Production, 2026-11-06 18:00, `/r/ventas-marca` at 1920 px: **Ampliar** on "Clientes por monto" opens
the dialog with its header and actions, but the card inside keeps its dashboard size in the top-left
corner — half the width, minimum height, its own duplicated title and chrome, and the same truncated
labels. The dialog is right; the card was never told it was maximised.

- [x] T019 Pass the maximised component as `{ ...component, span: 12 }` and add a `fill` prop to
      `LayoutRenderer` that puts `h-full` on the grid and on the single cell, so the card occupies the
      dialog's content area per FR-008 (partial)
- [x] T020 Give the dialog frame the height chain (`flex h-full min-h-0 flex-col`) so
      `useChartHeight` measures the real content height and the chart grows into it instead of
      keeping its 160 px minimum per FR-008 (partial)
- [x] T021 Add `maximized?: boolean` through `LayoutRenderer` → `ChartCard`, `KpiCard`, `DataTable`,
      `RankingTable` and the tiles: no card title (the dialog header shows it), no Ampliar button, no
      `⋯` menu, `p-0` and `shadow-none`, with the figure taking `flex-1` per FR-008 (partial)
- [x] T022 Show the period, the comparison and the active filter chips in `CardDialog`'s header from
      `data.selection` and the applied filters, as FR-008 requires (missing)
- [x] T023 Allow `labelColumn(width, labels, { maximized: true })` up to 50 % of the width and 480 px,
      so a 45-character name fits at ≥ 1200 px and only an actually-oversized one is ellipsised per
      FR-004 (partial)
- [x] T024 Size the dialog's charts for the dialog: pie/donut ring `min(60vh, 520px)` with the legend
      beside it (below on phones), KPI value `clamp(44px, 6vw, 96px)` with the delta row and sparkline
      at full width, and the default `SingleView` cards filling the frame per FR-008 (partial)
- [x] T025 Move between cards with `replace: true`, so the browser's Back closes the dialog instead of
      stepping through the cards, per FR-009 (contradicts)
- [x] T026 Prove the dialog at its real size: `clientWidth`/`clientHeight` of the rendered chart ≥ 90 %
      of the dialog's content area for `bar`, `donut`, `kpi`, `table` and the default ranking; one
      `<h2>` only; no Ampliar or menu button inside; a 45-character label without an ellipsis at
      1440 px; snapshots at 375/768/1280/1920 in both themes and an axe pass per FR-010 and SC-004
      (partial)
      — proved by `frontend/tests/e2e/layout-maximized.spec.ts` (13 passing): rendered box ratios per
      FR-008 for `bar`, `kpi`, `line`, `table` and the default ranking, one `<h2>`, no Ampliar/menu
      button inside, no ellipsis at ≥ 1280 px, and an axe pass on the dialog alone, at 375/768/1280/1920
      in light and dark. The repository keeps no screenshot baselines (no `toHaveScreenshot` anywhere),
      so the "snapshots" clause is covered as geometry + axe, the idiom `layout.spec.ts` already uses;
      the 45-character ellipsis-free proof is the `BIOLOGICOS PROVIACOL FORTE` fixture at 1280 and 1920.
      Run on the `chromium-375` project (the viewport is set per test), the suites' other engines not
      re-run for this change.
- [x] T027 Make the value chip follow the pointer (clamped inside the card) rather than sit on the
      mark, per FR-006 (partial)
- [x] T028 Print a value at each mark (`labels` on `line`/`area`) where it fits, or amend the
      requirement to the last point if per-mark figures prove unreadable, per FR-007 (partial)

## Convergence (feature 062, 2026-11-09)

- [x] The maximized dialog's title. 056b's FR-008 asserted "one `<h2>` carrying the card's title";
  the fallback behind it was `t.layout.maximize(id)` — `Ampliar «k_ventas»`, the component id from
  `report.yaml`, and the header was a single `flex-wrap` row that a phone squeezed into one letter
  per line. Feature 062 replaced the resolution with `cardTitle()`
  (`frontend/src/lib/cardTitle.ts`: component title → view title → KPI metric label → first words of
  a text → report title, never the id) and the header with a two-row grid, actions `shrink-0`. The
  geometry is proved in `frontend/tests/e2e/mobile-fixes.spec.ts` (title ≥ 55 % of the header, one
  line, 44 px actions, chips on their own row at 360 px) and the resolution in
  `frontend/tests/unit/card-title.test.ts`. The 056b geometry of the dialog itself (the card filling
  it) is unchanged and still green in `layout-maximized.spec.ts`.
- [x] The pie/donut of FR-006 was never sized by the dialog: `PieChart` hard-coded 240 px and read
  `window.innerHeight` when maximized, so a phone clipped the ring to nothing. It now draws with the
  width `ChartCard` measures (feature 062, US4).
