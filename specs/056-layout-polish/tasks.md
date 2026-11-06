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
