# Prompt — 056-layout-polish: KPI cards fill their span, equal card heights, category labels that fit

Paste everything below the line into the coding agent with the repository open.

---

You are working on the BizView repository (0.2.x). Read `.specify/memory/constitution.md`,
`specs/026-declarative-layouts/contracts/layout-web.md` and `specs/050-ui-design-system/spec.md`.
Implement **056-layout-polish** as `/speckit-specify` (from this text) → `/speckit-plan` →
`/speckit-tasks` → `/speckit-implement`. Do not ask me questions.

## Evidence (production, 2026-11-05, `/r/ventas-marca`, desktop 1920 px, light theme)

1. A `layout.web` `kpi` component with `span: 6` draws a card ~200 px wide at the left of its
   column and leaves the rest empty. Cause: `KpiComponent` renders through `KpiGrid`, whose `<ul>`
   is `grid-cols-2 lg:grid-cols-4` even when a single metric is shown, so one card takes a quarter
   of the span.
2. In the KPI card the delta badge (`+302,8 %`) sits glued under the value and the `antes …` line
   collides with it on two-line values. The badge needs its own row with top margin.
3. Cards in the same grid row have different heights (a bar chart next to a donut, a KPI next to a
   KPI with a longer "antes" line).
4. Horizontal `bar` charts clip category labels from the left (`IOLOGICOS FORTE`, `OLOGICOS
   PROVI…`, `RENDIMIENTO AG…`): `HorizontalBars` caps the label column at
   `min(112, max(64, width * 0.28))` and draws the text right-aligned, so long names are cut at the
   left edge instead of being shortened.

## Required behaviour

### KPI component (layout)

- A `kpi` component fills its span: one card, `w-full h-full`, no inner grid. Only the `kpis` view
  rendered without a layout keeps the 2/4-column grid.
- Card anatomy, top to bottom: icon + label row · value (fluid size: `clamp(28px, 2.6vw, 44px)`,
  tabular numbers; full value in `title`) · a **delta row** with `mt-3`: badge (`+302,8 %`) and
  `antes 149.250,44 USD` on the same line, wrapping under the badge when narrow · optional
  sparkline under it.
- Same vertical rhythm whether or not there is a comparison: reserve the delta row height so cards
  in one row align.

### Equal heights

- Every layout cell is `h-full` and every component card stretches to the cell (`flex flex-col`,
  chart area `flex-1`). Charts in one row therefore share the row height; a chart with fewer
  categories gets taller bars, never a shorter card.
- Minimum card height per type: kpi 150 px, chart 320 px, table/asset none.

### Category labels (horizontal bars, rankings, pie legends)

- Label column width = `min(40% of chart width, widest label up to 220 px)` measured with the real
  font (canvas `measureText` or an SVG `getBBox` pass), minimum 96 px.
- A label longer than the column is shortened **with an ellipsis at the end** (`BIOLOGICOS PROVI…`),
  never cut at the left; `<title>` carries the full text and the tooltip shows it.
- On phones (< 480 px) switch to **label above bar**: the label is a full-width line over its bar,
  so nothing is truncated; bars become 12 px with 8 px gap.
- Pie/donut legend: full name with `overflow-wrap: anywhere`, value and share aligned right in
  tabular numbers; legend below the ring on phones.
- Leading `*` or spaces in names are displayed as-is (data is not altered) but trimmed for sorting
  and width measuring.

### Value on hover / tap, with effect (bar, pie, donut, line, area, ranking)

- Hovering a bar, a slice or a point (or tapping it on touch) shows a **value chip** next to the
  element: full category name, formatted value (`6.482`, `84.401,05 USD`) and share of total
  (`11,4 %`); for comparisons also the delta badge. The chip follows the pointer, stays inside the
  card, and is announced to screen readers through the existing `<title>`/`aria-label`.
- Effect: the hovered element scales (`1.03`) and brightens, the others dim to 70 % opacity, over
  150 ms (`prefers-reduced-motion`: no scaling, only colour). On touch the chip stays until the next
  tap; Esc hides it.
- Optional **always-on value labels**: `labels: true` on `bar`/`line`/`area` components and
  `labels: values | percent | both` on `pie`/`donut` prints the number at the end of each bar / on
  each slice (hidden automatically when the bar is shorter than the label). Add the keys to
  `report.schema.json`, the CLI validator and `docs/AUTHORING.md`.

### Maximize a card (full screen)

- Every card in `layout.web` and every default view card gets an **Ampliar** button at the top
  right (icon `maximize-2`, 44 px touch target) next to the existing `⋯` menu, and the same item
  inside the menu. It opens the card **full screen** (`dialog` element, `role=dialog`,
  `aria-modal`, Esc / × / browser back closes, focus trapped and returned): the chart redraws at the
  full size (bars taller, every label fits, donut legend as a two-column table), the title, period,
  comparison and filter chips in the dialog header, and the card's footer caption below.
- Inside the full-screen view: the value chips and labels above, a **Descargar PNG** and
  **Descargar CSV** of that view only, and ← → to move to the previous/next card of the dashboard.
- URL state `?ampliar=<component id>` so a maximized card can be shared and survives reload; TV
  mode (030) ignores it.
- Double-tap on a card title on touch also maximizes.

### Accessibility and themes

- Contrast of label/axis text ≥ 4.5:1 in both themes; axe clean; `prefers-reduced-motion` respected.
- Snapshots at 375/768/1280/1920 in both themes for a fixture with: four `kpi` span 6, a `bar`
  (10 categories, names of 8–45 characters) next to a `donut`, two `bar` with 3 and 10 categories
  side by side.

## Tests
- Hover/tap on a bar shows the chip with name, value and share; other bars dim; chip never leaves
  the card; reduced-motion disables the scale; `labels: true` prints values and hides the ones that
  do not fit.
- Ampliar opens the dialog, chart re-renders at full size with no truncated label, Esc closes and
  returns focus, `?ampliar=` round-trips, ← → navigate, PNG/CSV download the right view.

- `kpi` with `span: 6` renders one card whose width equals its grid cell (± 1 px) at 1280 and 1920.
- Delta row has ≥ 12 px above it and the "antes" text never overlaps the badge at 300 px card width.
- Two cards in the same row report equal `offsetHeight` (chart vs donut, kpi vs kpi).
- A 45-character label is rendered with a trailing ellipsis and its `<title>` has the full name; at
  375 px the full label is shown above the bar.
- Existing 026/044/050 snapshot tests updated, no regressions in `ReportViews` without layout.

## Deliverables

Frontend (`LayoutRenderer`, `KpiGrid`/new `KpiCard`, `charts/BarChart`, `charts/PieChart`,
`TrendChart`, `RankingTable`, `CardMenu`, new `CardDialog` and `ValueChip`), schema + CLI (`labels`), `es.ts`/`en.ts` if any string changes, `specs/026-declarative-layouts/contracts/
layout-web.md` rendering-contract notes (fill span, equal heights, label policy), CHANGELOG under
Unreleased. Constitution: no change (mobile-first, declarative layout untouched — authored YAML
needs no edits).
