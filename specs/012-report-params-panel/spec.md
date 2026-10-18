# Feature Specification: Report parameters panel

**Feature Branch**: `012-report-params-panel`

**Created**: 2026-10-01

**Status**: Implemented (closed 2026-10-08, full suites green)

**Input**: Owner, 2026-10-01: "check report params design, it has to be this way, professional as
form; also worth to check Superset's filter section; use what fits best for the case,
professional and current best practice." References: Customer A "Resumen por Departamento" export
form (context block Fecha/Usuario/Empresa; "Opciones de exportación" card with format radio
PDF/CSV, labelled filled selects Proceso/Período/Tipo de Nómina, primary "Generar reporte"), and
Superset dashboard (left "Filters and controls" panel, collapsible, "Apply filters" / "Clear all";
per-chart menu; data tables). Builds on features 009 (views, no modals) and 010 (Customer A look).

## Design decision (best fit for BizView)

- **Superset's structure** for interactive reports: a left **"Filtros y controles"** panel beside the
  report on desktop, collapsible, with explicit **"Aplicar filtros"** and **"Limpiar todo"**, so a
  report is not recomputed on every click.
- **Customer A's form style** inside that panel: labelled sections, filled inputs, required marks, a
  primary action, and an export section (format PDF/CSV + "Generar reporte").
- **Customer A's context block** at the top of the report: period, comparison, data freshness, who is
  viewing.
- **Superset's per-table menu** for CSV: each table/ranking can be downloaded as CSV from its card.
- No modals (feature 009): on phones the panel is a view opened from a "Filtros" button.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Set the report's parameters in a clear form (Priority: P1)

A user opens a report. On desktop a "Filtros y controles" panel on the left shows the period
(preset or custom range), the comparison, and one field per report filter. They change several
values, see that there are pending changes, press "Aplicar filtros", and the report updates once.
"Limpiar todo" returns every field to the report's defaults.

**Why this priority**: the parameters are how every user reads a report; today they are scattered
small controls that apply on each click.

**Independent Test**: open a report with filters at 1920 px, change period to "Mes anterior",
comparison to "Año anterior" and a brand, apply, and check the figures, the URL and the context
block; then "Limpiar todo".

**Acceptance Scenarios**:

1. **Given** a report on desktop, **When** it opens, **Then** the panel shows sections "Período"
   (preset select; "Personalizado" reveals "Desde"/"Hasta" date fields), "Comparar con" (Sin
   comparación / Período anterior / Año anterior — only those the report allows) and one labelled
   searchable field per filter, with the current values.
2. **Given** edited fields not yet applied, **When** the user looks at the panel, **Then** "Aplicar
   filtros" is enabled and the panel says how many changes are pending; the report still shows the
   applied values.
3. **Given** pending changes, **When** the user presses "Aplicar filtros", **Then** the report
   reloads once with those values and the URL reflects them (shareable, survives reload).
4. **Given** a custom period with "Hasta" before "Desde" or a missing date, **When** the user tries
   to apply, **Then** the field shows the error and nothing is applied.
5. **Given** applied filters, **When** the user presses "Limpiar todo", **Then** fields return to the
   report's defaults and the report reloads once.
6. **Given** a filter, **When** the user opens its field, **Then** they can search the values for the
   current period and select **several** values; the report then includes all of them.

---

### User Story 2 - See at a glance what the report is showing (Priority: P1)

Above the figures, a context block states the applied period with dates, the comparison period
with dates, when the data was last updated and the active filters as removable chips.

**Why this priority**: professional reports state their parameters; users share screenshots and
PDFs that must be self-explanatory.

**Independent Test**: apply a period, a comparison and two filter values; read the context block;
remove one chip.

**Acceptance Scenarios**:

1. **Given** an applied selection, **When** the report shows, **Then** the context block lists
   "Período" (name and dates), "Comparado con" (dates or "Sin comparación"), "Datos actualizados"
   (date and time or "aún sin cargar") and one chip per active filter value.
2. **Given** a filter chip, **When** the user removes it, **Then** that value is removed and the report
   reloads once.
3. **Given** the PDF export, **When** it is generated, **Then** it carries the same parameters as the
   context block (today's PDF already includes the selection).

---

### User Story 3 - Export in the format I need (Priority: P2)

In the panel's "Exportar" section the user picks the format (PDF or CSV) and presses "Generar
reporte": PDF downloads the whole report as today; CSV downloads the report's tables. Each table or
ranking card also has a menu with "Descargar CSV" for just that table.

**Why this priority**: CSV is standard for further analysis (Excel); it depends on the panel of US1.

**Independent Test**: export PDF and CSV from the panel and one table's CSV from its menu; open the
CSV in a spreadsheet.

**Acceptance Scenarios**:

1. **Given** the panel, **When** the user chooses PDF and "Generar reporte", **Then** the PDF of the
   applied selection downloads (current behaviour), and the button shows progress while waiting.
2. **Given** CSV, **When** "Generar reporte" is pressed, **Then** one CSV file per table/ranking view
   is offered — or, when the report has several, a single CSV containing each table one after
   another with its title line — using the applied selection.
3. **Given** a table card, **When** the user chooses "Descargar CSV" from its menu, **Then** a CSV with
   that table's columns (labels as headers) and rows downloads.
4. **Given** numbers and dates in a CSV, **When** opened in a Spanish-locale spreadsheet, **Then**
   values are machine-readable (dot decimal, ISO dates, UTF-8 with BOM, `;` separator).

---

### User Story 4 - Same form on the phone (Priority: P2)

On a phone, a "Filtros" button with the number of active filters opens the same form as a view
(feature 009); "Aplicar filtros" applies and returns to the report; back cancels the pending
changes.

**Independent Test**: at 375 px open Filtros, change values, press back (nothing applied), reopen,
change, apply.

**Acceptance Scenarios**:

1. **Given** 375 px, **When** the report opens, **Then** the panel is hidden and a "Filtros" button
   shows the count of active filters next to the context block.
2. **Given** the filters view, **When** the user presses back, **Then** pending changes are discarded.
3. **Given** the filters view, **When** the user applies, **Then** the view closes and the report
   reloads once.

### Edge Cases

- A report without filters: the panel shows period, comparison and export only.
- Reports where only one comparison mode is allowed: the field is shown read-only.
- A filter with no values in the period: the field says "Sin valores en el período".
- A filter with more than 200 values: the search narrows the list; the field says that only the
  first 200 matches are listed (existing limit).
- Collapsing the panel on desktop gives the report the full width; the choice is remembered on the
  device.
- Old shared links with a single `filter.<id>=value` keep working.
- Narrative (AI summary) and PDF use the applied selection, never pending edits.

## Requirements *(mandatory)*

- **FR-001**: Desktop reports MUST show a collapsible "Filtros y controles" panel beside the report
  with sections Período, Comparar con, Filtros (one field per report filter) and Exportar.
- **FR-002**: Changes MUST be applied only with "Aplicar filtros" (or removing a chip / "Limpiar
  todo"); pending changes MUST be indicated and MUST NOT affect the shown figures, PDF or narrative.
- **FR-003**: Applied parameters MUST be kept in the URL (shareable, reload-safe), compatible with
  existing links.
- **FR-004**: Filter fields MUST support searching and selecting several values; the report MUST
  include rows matching any selected value of a filter (and all filters together).
- **FR-005**: A context block MUST show period and comparison with dates, data freshness and active
  filters as removable chips.
- **FR-006**: Export MUST offer PDF (whole report, current behaviour) and CSV (tables/rankings, per
  US3 AS2–AS4); each table/ranking card MUST offer "Descargar CSV".
- **FR-007**: On phones the same form MUST be a view (feature 009) opened by a "Filtros" button with
  an active-filter count; back discards pending changes.
- **FR-008**: The panel and form MUST follow the feature-010 look (filled inputs, labels, primary and
  secondary buttons, cards) in light and dark, WCAG 2.1 AA, Spanish, mobile-first, no modals.
- **FR-009**: Filter values sent by the browser MUST be validated server-side against the report's
  declared filters and passed to the database as bound values (never spliced into SQL).

## Success Criteria *(mandatory)*

- **SC-001**: Changing three parameters and applying triggers exactly one report reload.
- **SC-002**: 100% of applied selections survive a page reload and a shared link.
- **SC-003**: With two brands selected, the report totals equal the sum of each brand alone.
- **SC-004**: CSV files open correctly in a Spanish-locale spreadsheet (columns split, numbers
  numeric, accents intact) in 100% of exports.
- **SC-005**: 0 serious/critical accessibility violations on the report and the filters view, both
  themes; no horizontal scroll at 320/375 px.

## Assumptions

- CSV is built from the data the report already received for the applied selection (tables are
  limited as their views declare); no new server export endpoint is required unless multi-table CSV
  needs it.
- Multi-value filters need a backend change in how the report reads `filter.<id>` (repeated
  parameter); single-value links remain valid.
- Workspace report YAML does not change.
