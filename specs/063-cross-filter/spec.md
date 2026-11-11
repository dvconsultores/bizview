# Feature Specification: Cross-filter from any chart, slice or ranking row

**Feature Branch**: `063-cross-filter`

**Created**: 2026-11-11

**Status**: Ready for planning

**Input**: Owner brief of 2026-11-11: clicking a value in any dashboard component filters the whole
dashboard, the way mainstream BI tools behave. Bizview today can only filter from the Filtros sheet,
which makes reading `ventas-marca` (eight rankings over marca, producto, cliente and vendedor) slower
than clicking.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Click a value and the dashboard follows (Priority: P1)

A reader opens a dashboard and clicks the bar, slice, ranking row or table cell of a product. Every
component — KPIs included — reloads filtered by that product; the URL carries the filter and the chip
row says `Producto: BRAVECTO 500 MG ×`.

**Why this priority**: it is the whole feature: reading by clicking instead of opening a sheet.

**Independent Test**: with a fixture shaped like `ventas-marca`, click one `producto` bar and assert
the request, the chip, the URL, the KPIs and the other seven views.

**Acceptance Scenarios**:

1. **Given** a dashboard, **When** a mark is clicked, **Then** the report filter `dimension = value`
   is applied to every component and the URL carries it.
2. **Given** the filtered dashboard, **When** the same mark is clicked again, **Then** the filter is
   removed.
3. **Given** a filtered dashboard, **When** Ctrl/Cmd-click (or long-press) another mark of the same
   dimension, **Then** both values are selected (`IN`).
4. **Given** a filter on `producto`, **When** a `cliente` mark is clicked, **Then** the `producto`
   filter is removed and the `cliente` one applies; Ctrl/Cmd-click keeps `producto` and adds
   `cliente` (AND).
5. **Given** a cross-filtered chart, **Then** the source chart keeps every value, the chosen mark is
   highlighted and the others dim; every other component shows filtered data.
6. **Given** a keyboard user, **When** they Tab to a ranking row and press Enter/Space, **Then** the
   filter applies and the row exposes `aria-pressed="true"`.
7. **Given** a filtered dashboard, **Then** the URL is shareable, survives reload and feeds PDF/CSV and
   email.

### User Story 2 - The chip row and sheet agree (Priority: P2)

The applied cross-filter appears as a removable chip under the meta line; multi-select collapses to
`Producto: 3 seleccionados`; `Limpiar` clears every filter; the Filtros sheet shows the same value when
the dimension is listed there.

**Independent Test**: apply two values of one dimension and one of another; assert the chips, the
sheet and `Limpiar`.

### User Story 3 - Authors decide (Priority: P3)

`interactions.cross_filter: false` disables the report's marks; `cross_filter: false` makes one
component inert; `cross_filter: ignore` keeps that component on the company total. A dimension used
only by a view (not listed in `filters:`) is still cross-filterable.

**Independent Test**: validate each YAML switch and assert the rendered behaviour; send an undeclared
filter id and receive 422.

### Edge Cases

- `Otros` buckets, totals and trend points are never clickable.
- A value with a different display label and identity declares `key:`; the filter uses the key.
- A filter on a dimension absent from a daily rollup falls back to the base dataset and logs once.
- A maximized card filters identically; closing returns to the filtered dashboard.
- The same value in two dimensions is two filters (AND), never merged.
- More than 50 values for one dimension is refused, as the sheet does today.

## Requirements *(mandatory)*

- **FR-001**: bar, pie, donut, ranking, table, asset, share and default-view cards MUST make every
  one-value mark clickable (pointer, Enter, Space) and MUST set a report filter.
- **FR-002**: click replaces the cross-filter with the value's dimension (the previous dimension's
  filter is removed); clicking the only selected value again removes it; Ctrl/Cmd-click (long-press
  on touch) adds it to the dimension's `IN` selection and keeps the other dimensions (AND).
- **FR-003**: the source chart MUST keep every value, highlight the selected mark(s) and dim the rest.
- **FR-004**: a removable chip MUST appear under the meta line; multi-select reads
  `Producto: N seleccionados`; `Limpiar` clears all; the Filtros sheet reflects the same state.
- **FR-005**: the URL MUST use the existing `filter.<dimension>=value` parameters; reload, share,
  PDF/CSV and email MUST reuse them.
- **FR-006**: the engine MUST accept a filter on any declared dimension, listed in `filters:` or not,
  and MUST refuse an undeclared id with 422.
- **FR-007**: for the view owning an active dimension, the payload MUST include the view computed with
  every filter except that dimension.
- **FR-008**: reports MUST accept `interactions.cross_filter` (default true) and components
  `cross_filter: false | ignore`; `ignore` keeps that component's unfiltered-by-cross-filter data.
- **FR-009**: authors MAY declare a dimension as `{label, sql, key}`; filtering uses `key`, display
  uses `sql`.
- **FR-010**: marks MUST have `role="button"`, `aria-pressed`, a visible focus ring and a touch target
  of at least 32 px; the value chip of 056 gains «Clic para filtrar» / «Clic para quitar el filtro».
- **FR-011**: cached, comparison, direct and daily-materialized reports MUST keep working; a rollup
  missing the filtered dimension falls back to the base dataset and logs once.
- **FR-012**: the schema, CLI validator, AUTHORING/RENDERING docs, starter PROMPT, help topic
  «Filtrar haciendo clic» (ES/EN) and CHANGELOG MUST document the switches.

### Key Entities

- **Cross-filter**: a report filter on a dimension, with one or more rendered values.
- **Source view**: the owning view computed without its own active dimension.
- **Ignore view**: a component's view computed without cross-filters.

## Success Criteria *(mandatory)*

- **SC-001**: one click on a product filters the dashboard and updates the URL in under one second on
  the fixture.
- **SC-002**: the source chart never loses its values while its dimension is filtered.
- **SC-003**: all switches (`report`, `false`, `ignore`) change behaviour exactly as declared.
- **SC-004**: keyboard and axe checks pass for ranking, bar and pie marks.
- **SC-005**: PDF/CSV of a cross-filtered dashboard carries the filter and prints its chip.

## Decisiones tomadas (modo autónomo)

- [specify] decision — `cross_filter: ignore` is computed as "all filters except dimensions that are
  not listed in `filters:`", because the URL does not distinguish a sheet filter from a cross-filter;
  dimensions listed in `filters:` remain sheet-controllable and are not silently ignored.
- [specify] decision — `key:` is optional and backward compatible; when absent the rendered value is
  the filter value, exactly as today.
- [specify] decision — no new query shape: cross-filters stay ordinary `filters` in `selection`, so
  cache keys, comparison, direct reads and daily snapshots are untouched.

## Assumptions

- Dashboards are declared in YAML; the reader has no authoring UI.
- The existing filter URL contract (`filter.<id>=<value>`, max 50) is kept.
- Touch long-press is the additive gesture; a plain tap toggles.
