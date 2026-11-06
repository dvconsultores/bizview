# Implementation Plan — 056 layout polish

**Spec**: [spec.md](./spec.md) · **Branch**: `main` · **Date**: 2026-11-06

## Technical Context

React 19 + TypeScript, Tailwind tokens (050), SVG charts drawn on the app's primitives (026). No new
dependency: text is measured with a canvas 2-D context and a per-character estimate when canvas is
unavailable (jsdom); a PNG is produced by serialising the chart's `<svg>` into a canvas.

## Constitution Check

| Principle | Compliance |
|---|---|
| I. Mobile first | FR-005 changes the horizontal bar to label-above-bar under 480 px; tests at 375 px |
| IV. Separated concerns | geometry in `lib/chartLabel.ts`, PNG in `lib/png.ts`, card chrome in `CardDialog.tsx` |
| V. Fixed stack | no package added |
| IX. Declarative, no customer code | only rendering changes; the YAML contract gains one optional key |
| Constraint: validator is the single contract | `labels` is added in `cli/bizview_cli/schemas/report.schema.json` first; the CLI and docs follow |

**Result**: PASS.

## Design

- `KpiCard.tsx` (new): the single-card anatomy; `KpiGrid` keeps the 2/4-column grid for the no-layout
  view and delegates each tile to it.
- `LayoutRenderer`: cells become `h-full` with a per-type minimum height; a `kpi` renders
  `KpiGrid mode="single"`; charts receive `labels`; every card gets a `Maximize` control.
- `CardDialog.tsx` (new): the only file allowed to use a dialog. `?ampliar=` is owned by
  `ReportSheet`, which already owns `theme`/`mode` in the URL.
- `BarChart`/`PieChart`: measured label column, ellipsis, `<title>`, hover/tap index with dimming and
  a positioned chip; `labels` draws permanent values.
- `lib/chartLabel.ts`: `measureText`, `fitLabel`, `labelColumn`.
- The `no-modals` guard is narrowed to allow `CardDialog.tsx` by name and keep the ban everywhere
  else — the exception is asserted, not implied.

## Phases

1. Contract: `labels` in the schema and the CLI validator; docs.
2. KPI: `KpiCard`, `KpiGrid` single mode.
3. Height chain: cells, cards, chart areas, minimum heights.
4. Labels: measure, ellipsis, phone layout, pie legend.
5. Interaction: chips, dimming, `labels` rendering.
6. Maximize: `CardDialog`, URL state, PNG/CSV, ← →.
7. Tests and gates.
