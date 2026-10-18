# Feature Specification: Declarative layouts for dashboards and PDF reports

**Feature Branch**: `026-declarative-layouts`

**Created**: 2026-10-16

**Status**: Implemented (2026-10-16). Verified in this session: CLI **541 passed** + `ruff` clean;
frontend `tsc` clean, **628 tested**, build and `check:compat` OK; the layout browser suite **30/30
across Chromium, Firefox and WebKit at 320/375 px in both themes** (order and spans at 375 and
1280 px, the engine summary announced as the chart's label, and FR-009's no-layout case asserting the
payload order with no grid); the PDF, parity, content-check and assistant suites green. Still open:
SC-005's live eval (needs an AI provider; this installation runs with `AI_PROVIDER=none`) and a
complete backend run in one process (the suite is slow against the external database, so it was
verified in focused groups).

**Input**: Owner, 2026-10-16, relaying a recommendation: "DeepSeek is the report builder and
orchestrates both outputs: for PDFs it generates ReportLab code; for dashboards it generates
configuration objects (JSON) for a React charting library (Recharts/Tremor) that the frontend
renders."

**Decision taken in this spec**: the second half is adopted and generalised; the first half is
adopted in spirit but not literally. The AI MUST NOT generate executable code (ReportLab Python or
anything else) that the product runs. It generates **declarative layout documents** for both
outputs — a dashboard layout and a PDF layout — validated against JSON Schemas and rendered by
product code: React + Recharts for the web, ReportLab for the PDF. Reasons: constitution IX
("customer logic is declarative; no customer code in the product"), VIII (bounded AI), and plain
security — code written by a model and executed on the server with database access is remote code
execution by design. A declarative PDF layout gives the same outcome (the AI decides what the PDF
looks like) with a renderer you control and test once.

**Builds on**: 005/011 (report spec and definition), 014/015 (Asistente drafts), ReportLab exports
in `backend/app/reports/`. Recharts is already in the stack (constitution V); Tremor is not added.

**Constitution**: the load-bearing principles are **IX** (customer logic is declarative — the layout
is customer logic, so it is data, not code), **VIII** (AI is bounded — the AI chooses composition
from a closed catalogue and never proposes executable content), **V** (fixed stack — Recharts and
ReportLab are already there, nothing is added) and **VII** (branding stays installation
configuration, referenced by role). **2.1 (mobile-first)** is what decides the grid rules: the phone
order is the declared order and the desktop grid is the enhancement. No amendment is needed (see
*Constitution check*).

## Why one layout model for both outputs

Today a report definition declares metrics, dimensions, views and filters, and the frontend decides
how to draw them; the PDF export is a fixed template. This feature adds an explicit `layout` for
each output so the Asistente (or a human) can decide composition — order, sizes, chart types, KPI
rows, tables, text blocks, page breaks — while the data model (metrics/dimensions) stays untouched.
Both layouts reference the same views, so a dashboard and its PDF always show the same numbers.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The Asistente composes a dashboard (Priority: P1)

The super user asks "pon las ventas del mes arriba como KPI, debajo una línea diaria y a la derecha
el ranking de marcas". The Asistente writes `layout.web` in the report definition: a grid with a KPI
row, a line chart bound to the daily view, and a bar ranking bound to the brands view. The frontend
renders it with Recharts, mobile-first (stacked on phones, grid on desktop).

**Why this priority**: it is the heart of the feature and the piece everything else leans on — the
dashboard layout is at once the format, the renderer's input and the Asistente's output contract.
The PDF layout (US2) reuses the same binding rules, so building this first is what makes the second
story small.

**Independent Test**: for a seeded report, a layout with KPI + line + bar + table renders at 375px
and 1280px, each component bound to a declared view, and the numbers equal the views' data.

**Acceptance Scenarios**:

1. **Given** a report definition with `layout.web`, **When** the dashboard opens, **Then** components
   render in the declared order and grid spans; on phones everything stacks in order.
2. **Given** a component bound to a view that does not exist or to an undeclared metric, **When** the
   definition is validated, **Then** validation fails naming the component and the missing reference.
3. **Given** no `layout.web`, **When** the dashboard opens, **Then** the engine uses the default layout
   derived from the views (today's behaviour), so existing reports keep working.
4. **Given** a layout change in a new workspace version, **When** applied, **Then** the dashboard
   reflects it without redeploying the frontend.

---

### User Story 2 - The Asistente composes the PDF (Priority: P1)

The super user asks for "un PDF de una página con el resumen, la gráfica diaria y la tabla por
producto, con el logo del cliente". The Asistente writes `layout.pdf`: page size and orientation,
a header block (title, period, logo from the installation branding), a KPI row, a chart block, a
table block with column widths and totals, and a footer. The backend renders it with ReportLab;
charts are drawn by the backend (ReportLab graphics or a server-side chart image), never by the
browser.

**Why this priority**: the PDF is the artefact customers print and forward, and today it is the one
output nobody can compose — the fixed template cannot express "one page with the summary, the chart
and the table". It shares the binding rules and the data engine with US1, so it is the second half
of the same MVP rather than a separate feature.

**Independent Test**: the PDF for a seeded report renders in under 10 s, is one page as declared,
and every figure equals the dashboard's for the same filters and period.

**Acceptance Scenarios**:

1. **Given** `layout.pdf`, **When** "Exportar PDF" is pressed, **Then** the backend renders the
   declared blocks in order with the installation's branding (constitution VII: branding is
   configuration).
2. **Given** a table block with more rows than fit, **When** rendered, **Then** the table continues on
   the next page with repeated headers, or is truncated with a "y N más" line if the layout says
   `overflow: truncate`.
3. **Given** no `layout.pdf`, **Then** the current fixed template is used.
4. **Given** a block type the renderer does not know, **Then** validation fails before anything is
   rendered.

---

### User Story 3 - Preview both layouts in the Asistente (Priority: P2)

Inside a conversation (014/015), the super user sees the draft dashboard rendered with the new
layout and can download the draft PDF from the same preview data.

**Why this priority**: the preview is where a layout is accepted or rejected — it is the same
review habit 015 established for views and drafts. It is P2 because it needs US1 and US2's
renderers to exist before it can show anything.

**Independent Test**: inside a conversation, a valid draft carrying both layouts renders the
dashboard from `layout.web` in the "Vista previa" view and offers "PDF de vista previa" built from
`layout.pdf`, both from the preview data.

**Acceptance Scenarios**:

1. **Given** a valid draft with layouts, **When** "Vista previa" finishes, **Then** the "Vista previa"
   view renders `layout.web` from the preview schema and offers "PDF de vista previa" rendered from
   `layout.pdf` (015 FR-011).
2. **Given** a layout validation problem, **Then** it is reported with file, JSON path and expected
   schema fragment like any other draft problem (015 FR-003).

---

### User Story 4 - A human edits the layout by hand (Priority: P3)

A customer editing their Git workspace changes `layout.web` in `report.yaml`, runs `bizview
validate`, and gets the same validation as the Asistente. The authoring guide (015 FR-001) documents
every component and block with an example.

**Why this priority**: it is the guarantee that the format is customer logic and not an AI-only
channel — the same file the Asistente writes is the file a person can read, edit and validate. P3
because it adds no new capability, only the documentation and the CLI path to the validation US1
and US2 already demand.

**Independent Test**: edit `layout.web` by hand in a workspace's `report.yaml`, run `bizview
validate`, and obtain the same errors and warnings the Asistente would get, with the authoring guide
documenting every component and block with one example.

**Acceptance Scenarios**:

1. **Given** a workspace with a hand-written layout, **When** `bizview validate` runs, **Then** the
   layout is validated with the same schemas the backend and the Asistente use, and each problem
   names the file and the JSON path.
2. **Given** the authoring guide, **Then** every web component and every PDF block is documented with
   one example, and the two golden layouts it ships are kept valid by CI.

---

### Edge Cases

- A component declares a chart type that makes no sense for its view (a pie with 40 categories, a
  line over a non-ordered dimension): validation warns (not fails) and the renderer applies a safe
  fallback (bar, top-N with "otros").
- Very small screens: KPI rows wrap to two per row; tables scroll horizontally inside their card;
  charts keep a minimum height.
- Dark mode and the installation palette: the renderer maps semantic colour roles (`primary`,
  `positive`, `negative`, `series[n]`) to theme tokens; layouts never contain hex colours.
- PDF fonts: only fonts shipped with the product; the layout picks from a named set.
- Long titles and labels in Spanish: wrapping and truncation rules defined once in the renderers.
- Layout references a filter not declared by the report: validation fails.
- Accessibility: every chart component carries a text summary (auto-generated from the view) used
  as `aria-label` and in the PDF as alt text.

## Requirements *(mandatory)*

### Layout model (shared)

- **FR-001**: The report definition gains an optional `layout` object with `web` and `pdf`. Both are
  declarative JSON/YAML, validated by JSON Schemas that live in `cli/` next to the other artifact
  schemas (single source for CLI, backend and the Asistente's authoring guide).
- **FR-002**: Layout components bind to the report's declared views, metrics, dimensions and filters
  by id only. No expressions, no inline data, no SQL, no code, no URLs, no colours.
  *Decision (2026-10-16, found while planning against the code)*: the report's `views` entries carry
  no `id` today — each is a `oneOf` branch keyed by `type`, so two views of the same type are
  indistinguishable to a reference. This feature therefore adds an **optional** `id` to every view
  (optional so that a report with no layout keeps validating unchanged, FR-009), and a layout may
  reference a view only by that id; a reference that resolves to nothing is a validation error whose
  fix hint says to declare the id. Details: `research.md` R15, `data-model.md` §10.
- **FR-003**: Component catalogue, web: `kpi` (value, delta vs compare period, sparkline optional),
  `line`, `area`, `bar` (vertical/horizontal, stacked), `pie`/`donut` (top-N + otros), `table`
  (columns, totals, sort, page size), `text` (markdown subset), `filters` (which report filters are
  shown and where), `spacer`. Grid: 12 columns on desktop, `span` per component, declared order is
  the phone order.
- **FR-004**: Block catalogue, PDF: `page` (size, orientation, margins), `header` (title, subtitle,
  period, logo role), `kpi_row`, `chart` (same chart kinds as web), `table` (column widths, totals,
  overflow policy), `text`, `page_break`, `footer` (generated-at, page numbers, legal line).
- **FR-005**: Semantic colour roles and named font set only; the renderers resolve them from the
  installation's theme and branding.

### Rendering

- **FR-006**: Web: a `LayoutRenderer` in `frontend/` maps components to existing Recharts-based
  chart components and the existing table/KPI components; nothing is `eval`ed; unknown component →
  render error card, never a blank dashboard.
- **FR-007**: PDF: a `PdfLayoutRenderer` in `backend/app/reports/` maps blocks to ReportLab flowables;
  charts rendered server-side; output `application/pdf` only; typical report under 10 s.
- **FR-008**: Both renderers read data through the existing report engine; a dashboard and its PDF
  for the same filters and period MUST show identical figures.
- **FR-009**: Absent `layout.web`/`layout.pdf` → current default behaviour, so every existing report
  keeps working unchanged.

### Asistente

- **FR-010**: The authoring guide (015 FR-001) includes the layout schemas, the component/block
  catalogue with one example each, and two golden layouts (a one-page PDF and a 4-component
  dashboard) that CI keeps valid.
- **FR-011**: The Asistente MUST produce `layout.web` and `layout.pdf` as part of a complete draft
  (015 FR-009); the preview renders both.
  *Decision (2026-10-16, found by running the suite)*: the completeness expectation is **guidance,
  not a gate**. `readiness.compute()` returns `ready = valid and not pending`, so making a missing
  layout a `pending` item made every draft of a layout-less report unappliable — which is the
  opposite of FR-009 and broke five existing apply tests plus the direct-report readiness test. The
  requirement is therefore carried by the authoring guide (the Asistente reads it) and by the
  preview (US3), and never by the readiness gate. Details: `research.md` R16.
- **FR-012**: The AI never receives or emits code for rendering; any draft file outside the allowed
  declarative formats is rejected (014 path/size limits extended with a content check: YAML/JSON/SQL
  only, SQL still read-only via sqlglot).

### Validation and tooling

- **FR-013**: `bizview validate` validates layouts with the same schemas; the backend refuses to
  apply a version whose layouts fail ("no spec, no run" extends to layouts).
- **FR-014**: Validation warnings (unsuitable chart for a view) are distinguished from errors and
  shown in the Asistente and the CLI.

### Key Entities *(include if feature involves data)*

- **Layout document**: the optional `layout` object of a report definition, with a `web` half and a
  `pdf` half. Pure declarative data — no expressions, no code — validated against the artifact
  schemas that live beside the other schemas of the CLI.
- **Component (web) / block (PDF)**: one entry of a layout. Names a type from the closed catalogue
  and binds, by id only, to the report's views, metrics, dimensions and filters; carries composition
  attributes (order, span, chart kind, columns, overflow policy) and semantic roles (colour role,
  font name) — never literal values.
- **View binding**: the reference from a component to one declared view, together with the filters
  and compare period it is read with. The single thing both renderers resolve, which is why a
  dashboard and its PDF cannot disagree.
- **Theme role and font name**: the semantic names a layout may use (`primary`, `positive`,
  `negative`, `series[n]`, a font from the shipped set); the installation's theme and branding
  resolve them, so the same layout looks right in every installation.
- **Layout problem**: a validation result attached to a file and a JSON path, carrying a severity
  (error or warning) and the expected schema fragment; surfaced identically in the preview, the CLI
  and the Asistente.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A layout with KPI row, line, bar and table renders correctly at 375px and 1280px in
  both themes for the seeded reports; visual tests in the frontend suite.
- **SC-002**: 100% figure parity between dashboard and PDF for the same report, filters and period
  (automated).
- **SC-003**: PDF render under 10 s for a report with 4 blocks and a 500-row table; one-page layouts
  stay one page.
- **SC-004**: 0 executable content accepted in drafts: the content check rejects any Python/JS/HTML
  in a fixture set of 50 adversarial drafts.
- **SC-005**: In the live eval (015 SC-001) the Asistente produces valid `layout.web` and
  `layout.pdf` on the first validation pass in at least 4 of 5 runs.
- **SC-006**: All existing reports render identically before and after this feature when no layout
  is declared (regression suite).

## Constitution check

- II/VI: renderers read optimized models through the report engine; no new queries to the origin.
- V: Recharts and ReportLab already in the stack; Tremor not added; no new stack component.
- VII: branding (logo, palette) stays installation configuration, referenced by role.
- VIII/IX: AI output stays declarative and validated; no free-form or executable entry point.
- Constraints: PDFs by the backend with ReportLab; html2canvas not used for PDFs.

→ PASS, no amendment needed.

## Assumptions

- The default dashboard behaviour today can be expressed as a generated `layout.web`, which makes
  FR-009 a one-time derivation rather than two code paths kept forever (plan decides).
- Server-side chart rendering for PDFs uses ReportLab's graphics module; if quality is insufficient
  the plan may propose a supporting library (listed with its reason, constitution V).
- The demo installation spec previously referred to as 026 becomes 027.

## Decisions taken while implementing (2026-10-16)

- **The report's views had no `id`, so "bind by id only" was not implementable as written**
  (FR-002, found by reading the schema before writing code). Every `views[].oneOf` branch gained an
  **optional** `id`, deliberately out of `required` so every existing report keeps validating
  untouched (FR-009). A layout may reference only a view that declares one, and a reference that
  resolves to nothing is `layout_view_missing` with the fix hint to declare the id. Index binding —
  what the pre-existing `pdf.views: [0, 1, 2, 3]` does — was rejected: it silently repoints a
  component when a view is inserted. Every view payload now carries its `id` so both renderers bind
  identically. Details: research R15, data-model §10.
- **The completeness expectation does not gate readiness** (FR-011 vs FR-009). Making a missing
  layout a `pending` readiness item looked reasonable and was wrong: `readiness.compute()` returns
  `ready = valid and not pending`, so every draft of a layout-less report became unappliable — the
  inverse of FR-009 — and six existing tests failed. Reverted; FR-011 is carried by the authoring
  guide and by the preview. Details: research R16.
- **`totals` needed a one-line engine fix.** `_view_metrics()` returned `[]` for a `table` view, so
  `views[].totals` was never emitted and a layout declaring `totals: true` on a table printed no
  Total row in either renderer — the exact defect class this feature must not ship (a layout that
  says something the renderer ignores). Its own docstring already said "whatever its type".
  Details: research R17.
- **`font_name` is accepted only on a `text` component/block.** It was first accepted everywhere,
  where most components would silently ignore it; the schema now rejects it elsewhere
  (`if font_name then type must be text`), so the schema cannot advertise a no-op.
- **A colour and an address are two different problems.** Rejecting both as one code gave an author
  of `rgb(1,2,3)` the message that addresses are not allowed. Split into `layout_color_literal`
  (hex/RGB/HSL) and `layout_address_forbidden` (`://`, `url(`, `data:`), with the address winning a
  value that carries both, so `url(#ff0000)` is still refused.
- **The draft content check rejects structurally, not by substring hunting.** A `.yaml` must
  safe-load to a **mapping** (a bare script loads as a scalar), then its loaded data is scanned for
  executable markers with a `seen` set that guards YAML-anchor recursion; `.sql` reuses the existing
  read-only validator; markdown only has its first line sniffed. Scanning markdown wholesale
  rejected this repository's own specs, which quote `<script>` and `<?php` in prose.
- **The browser suite needed a seeded layout or it would have been vacuous.** `layout.spec.ts` first
  read the layout from the API and *skipped* when the seeded report declared none — a suite that
  cannot fail. `backend/tests/workspace_fixture.py` now seeds a second report, `ventas-layout`, with
  four id-bearing views and both layout halves, leaving `ventas` untouched so the FR-009 case and
  the existing PDF assertions still mean what they meant.
- **Two artifacts were corrected, not the code.** `tasks.md` T043 pointed the end-user guide note at
  `tableros.md` (the dashboards *list* screen) instead of `ver-reporte.md`
  (viewing a report).
