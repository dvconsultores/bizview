# Feature Specification: Layout polish — KPI fills its span, equal card heights, labels that fit

**Branch**: `main` · **Created**: 2026-11-06 · **Status**: Draft

**Input**: Owner, 2026-11-06: four defects seen in production at `/r/ventas-marca` on a 1920 px
desktop — a `kpi` with `span: 6` draws a ~200 px card and leaves the rest of its column empty; the
delta badge sits glued to the value and the "antes" line collides with it; cards in one row have
different heights; horizontal bars clip category names at the left (`IOLOGICOS FORTE`,
`OLOGICOS PROVI…`). Plus the requested additions: value chips on hover/tap, optional value labels,
and a full-screen "Ampliar" per card.

**Builds on**: 026 (declarative layouts), 030 (delta badges, TV mode), 044 (visual components),
050 (design system). Constitution: no change — the authored YAML is untouched; only how it renders.

## User Scenarios & Testing

### User Story 1 — A KPI fills the space its author gave it (P1)

An author declares `kpi` with `span: 6` expecting half the row. Today one card takes a quarter of
that half and the rest is empty, so the dashboard looks broken and the author cannot fix it from
YAML. The card must fill its cell, and the delta row must have room of its own so a two-line value
never collides with "antes".

**Independent test**: render a layout with `kpi span 6` at 1280 and 1920; the card's width equals its
grid cell (± 1 px), the delta row has ≥ 12 px above it, and at a 300 px card the badge and the
"antes" text never overlap.

### User Story 2 — Cards in a row share a height (P1)

A bar chart next to a donut, or two KPIs with different "antes" lengths, end at different heights:
the row looks ragged and the eye cannot compare. Every cell and every card stretches to the row, and
a chart with fewer categories gets taller bars rather than a shorter card. Minimum heights per type
keep a KPI from collapsing on a narrow screen.

### User Story 3 — A long category name is shortened, never cut (P1)

`BIOLOGICOS PROVI…` is readable; `OLOGICOS PROVI…` is not, because the column is right-aligned at a
fixed width and the text is clipped at the left edge. The label column is measured from the real
font (up to 220 px and 40 % of the chart), names are shortened with a trailing ellipsis, the full
name travels in `<title>` and in the tooltip, and on a phone the label sits above its bar so nothing
is truncated at all.

### User Story 4 — Reading a value without leaving the dashboard (P2)

Hovering or tapping a bar, slice or point shows a chip with the full name, the formatted value and
its share; the rest of the series dims so the eye stays on the element. `labels: true` (or
`values|percent|both` on pie/donut) prints the numbers permanently for the charts that need them.

### User Story 5 — One card, full screen (P2)

A card can be opened full screen from its header or its menu: the chart redraws at that size, the
title/period/comparison travel with it, the card's own CSV and a PNG can be downloaded, ← → move
between the dashboard's cards, Esc/×/back closes, focus returns, and `?ampliar=<id>` makes it
shareable and reload-safe. TV mode ignores it.

### Edge Cases

- One KPI in a `kpis` view without a layout: the 2/4-column grid stays (it is the only thing that
  gives it width).
- A component whose view failed: the error card stretches like any other, no chip, no Ampliar box
  with an empty body.
- A label wider than the whole chart: it is still ellipsised at the column width, never drawn
  outside the SVG.
- Reduced motion: no scaling on hover, colour only; the chip still appears.
- A maximised component id that no longer exists after a filter change: the dialog closes rather
  than showing an empty frame.

## Requirements

- **FR-001** A `kpi` component renders one card that fills its cell (`w-full h-full`), with no inner
  grid; only the no-layout `kpis` view keeps the 2/4-column grid.
- **FR-002** Card anatomy: icon + label, value (fluid `clamp(28px, 2.6vw, 44px)`, tabular, full
  value in `title`), a delta row with `mt-3` holding badge and "antes" on one line that wraps under
  the badge when narrow, then the optional sparkline. The row's height is reserved with and without
  a comparison.
- **FR-003** Every layout cell is `h-full`, every card stretches to it, chart areas are `flex-1`, and
  minimum heights are kpi 150 px, chart 320 px, others none.
- **FR-004** Horizontal bar label column = `min(40 % of chart width, widest measured label up to
  220 px)`, at least 96 px; longer labels get a trailing ellipsis; `<title>` carries the full name.
- **FR-005** Below 480 px of chart width, horizontal bars draw the label on a full-width line above
  its bar (12 px bar, 8 px gap) so nothing is truncated; pie/donut legends move below the ring.
- **FR-006** Hover or tap on a bar, slice or point shows a value chip with the full category name, the
  formatted value and the share of total (plus the delta when a comparison exists); the hovered
  element scales 1.03 and brightens, the others dim to 70 %, 150 ms; the chip stays inside the card.
- **FR-007** `labels: true` on `bar`/`line`/`area` prints the value at the end of each mark and hides
  a label that does not fit; `labels: values|percent|both` on `pie`/`donut` prints it on the slice.
  The key is in `report.schema.json`, the CLI validator and `docs/AUTHORING.md`.
- **FR-008** Every layout card and every default view card offers **Ampliar** (header button and menu
  item) opening a full-screen dialog with the card's title, period, comparison and filter chips, the
  chart at full size, the footer caption, its CSV and a PNG, and ← → between the dashboard's cards.
- **FR-009** `?ampliar=<id>` round-trips (share, reload, back closes); TV mode ignores it.
- **FR-010** `prefers-reduced-motion` removes scaling; contrast of labels and axes stays ≥ 4.5:1 in
  both themes.

## Success Criteria

- **SC-001** `kpi span 6` occupies its whole cell at 1280 and 1920 (± 1 px).
- **SC-002** Two cards in one row report equal `offsetHeight`.
- **SC-003** A 45-character category label renders with a trailing ellipsis and its full text in
  `<title>`; at 375 px the full label is above the bar.
- **SC-004** No regression in `ReportViews` without a layout, and the 026/044/050 suites stay green.

## Assumptions

- The pixel measurements (SC-001, SC-002) are proven by a browser-based run; the jsdom suite proves
  the structural invariants that make them true (one card, no inner grid, `h-full` chain).
- `labels` defaults to off; existing YAML renders exactly as before.
- A PNG is produced from the card's SVG without a new dependency.
