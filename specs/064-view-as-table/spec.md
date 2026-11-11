# Feature Specification: See the data behind any card as a table

**Feature Branch**: `064-view-as-table`

**Created**: 2026-11-11

**Status**: Ready for planning

**Input**: Owner brief of 2026-11-11: a reference BI tool offers «View as table» on every chart
(`Chart Data: Cliente (Top 10)` with a search box, a row counter, a copy button and a sortable
two-column table). In Bizview the numbers behind a bar or a donut can only be read by hovering mark
by mark or by downloading the CSV.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read the exact numbers of any card (Priority: P1)

A reader presses **Ver como tabla** on a bar chart, a donut or a KPI. A dialog titled
`Datos: <card title>` opens with the rows the chart drew, formatted like the dashboard, and the
reader can search, sort and copy them without leaving the report.

**Why this priority**: it is the whole feature: reading the data behind a drawing instead of
hovering each mark.

**Independent Test**: on a report with a bar, a donut and a KPI, open each table and compare every
row with the payload the chart used.

**Acceptance Scenarios**:

1. **Given** a bar card, **When** the reader opens its `⋯` menu and chooses **Ver como tabla**,
   **Then** the dialog shows one row per category and one column per metric the chart draws.
2. **Given** the same card, **When** the reader uses the table icon next to **Ampliar** or
   double-clicks the card body (not a mark), **Then** the same dialog opens.
3. **Given** a maximized card, **When** the reader picks **Tabla** in the header toggle, **Then**
   the dialog body becomes the table and the choice survives ← →.
4. **Given** a table view shared as `?tabla=<component id>`, **When** the link is opened, **Then**
   the dialog opens on that table.
5. **Given** the table, **When** the reader types in the search box, **Then** rows narrow
   accent-insensitively; sorting a header toggles asc/desc; **Copiar** writes TSV with headers.

### User Story 2 - Every kind of card has its data (Priority: P2)

Trends show one row per bucket, rankings show the dimension, value, previous, change and share,
tables show their declared columns, and KPI cards show metric, value, previous and change (plus the
sparkline series when there is one).

**Independent Test**: open the table of a `trend`, a `ranking`, a `table`, a `kpi`, a `gauge`, a
`share`, an `index` and an `asset` card and assert the column labels and the first row.

### User Story 3 - Complete the rows and keep them shareable (Priority: P3)

When a ranking or table was cut by `limit`/`top_n`, **Ver todas las filas** requests the same view
without the cut (at most 1,000 rows, 50 per page). `data_table: false` hides the entry points for
one component; `interactions.data_table: false` hides them for the report.

**Independent Test**: open a truncated ranking, press **Ver todas las filas** and assert the extra
rows; validate `data_table` in the schema and assert the hidden UI.

### Edge Cases

- `Otros` appears exactly as the chart drew it; the table never invents rows.
- A view with an error or no data opens no table: the entry points are hidden.
- The title is the card's own words (component title → view title → metric label), never its id.
- Copy/CSV are hidden for a share link created without export; the table stays readable.
- The first column stays frozen and only the table scrolls horizontally on a phone.

## Requirements *(mandatory)*

- **FR-001**: every data card (`kpi`, `line`, `area`, `bar`, `pie`, `donut`, `ranking`, `table`,
  `gauge`, `share`, `index`, `asset`) MUST expose **Ver como tabla** in its menu and as a table
  icon beside **Ampliar**; phones keep the menu item and may drop the icon.
- **FR-002**: `?tabla=<component id>` MUST open the table dialog and MUST compose with
  `?ampliar=<id>`; a maximized card MUST offer a **Gráfico | Tabla** toggle that survives ← →.
- **FR-003**: a double-click/double-tap on the card body (not on a mark) and `T` on a focused card
  MUST open the table.
- **FR-004**: the dialog MUST show exactly the rows the chart drew, from the payload in memory, with
  the chart's order and formats; comparison adds `Anterior` and `Variación`; rankings and pies add
  `% del total`.
- **FR-005**: the table MUST offer search (accent-insensitive), a row counter, sorting by any
  column (default chart order), **Copiar** (TSV + «Copiado» toast), **Descargar CSV**, and
  **Descargar XLSX** only when the backend offers it.
- **FR-006**: a truncated view MUST offer **Ver todas las filas**, requesting the view without
  `limit`/`top_n` (cap 1,000, 50 per page) and keeping the report's cache rules.
- **FR-007**: headers MUST use the localized metric/dimension labels; numbers right-aligned in
  tabular figures; negatives use the negative token; the first column is frozen on phones.
- **FR-008**: rows MUST be clickable for cross-filter with the same highlight and chips as the
  marks (063).
- **FR-009**: the dialog MUST have `role="table"` semantics, a sticky header, zebra rows, focus
  trap, Esc/back to close, and a 360 px layout with no page-level horizontal scroll.
- **FR-010**: `data_table: false` on a component and `interactions.data_table: false` on the report
  MUST hide every entry point; the default is true.
- **FR-011**: schema, CLI validator, AUTHORING docs (ES/EN), starter PROMPT, help topic «Ver los
  datos de un gráfico» (ES/EN) and CHANGELOG MUST document the switch.
- **FR-012**: share-link viewers MUST get the table; when the link disallows export, copy and CSV
  MUST be hidden while the table remains readable.

### Key Entities

- **Data-table model**: the rows and columns a card's view draws, in the chart's order.
- **Full request**: the same report selection with `full=1`, which keeps every row up to 1,000.

## Success Criteria *(mandatory)*

- **SC-001**: every data card opens its table from the menu and from the icon.
- **SC-002**: the dialog's rows equal the chart's data (same order, same formatted values) for bar,
  donut, KPI, trend, ranking and table.
- **SC-003**: search, sort, copy and CSV operate on the same rows the dialog shows.
- **SC-004**: `?tabla=` round-trips and the maximized toggle keeps its choice across ← →.
- **SC-005**: `data_table: false` leaves no entry point.
- **SC-006**: 360 px keeps the first column frozen without page-level horizontal scroll; axe clean.

## Decisiones tomadas (modo autónomo)

- [specify] decision — «sin exportación» has no separate flag in the current share-link model, so a
  shared report hides copy/CSV when the report's own `pdf` export is disabled; the table itself is
  always readable. A dedicated flag would be a different feature.
- [specify] decision — XLSX is not offered anywhere in the product today, so FR-005's XLSX button is
  skipped rather than inventing a new export format.
- [specify] decision — "the rows the chart drew" is the payload view the component binds to; a
  component that draws several series gets one column per series, and `top_n`/`Otros` stay as drawn.
