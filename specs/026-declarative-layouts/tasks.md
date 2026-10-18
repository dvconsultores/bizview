# Tasks: Declarative layouts for dashboards and PDF reports

**Input**: [spec.md](./spec.md) · **Feature**: `026-declarative-layouts`

Design: [plan.md](./plan.md) · [research.md](./research.md) · [data-model.md](./data-model.md) ·
[contracts/](./contracts/) · [quickstart.md](./quickstart.md)

Every task names the file it touches; field names, limits and enums come from
[data-model.md](./data-model.md) and must be implemented verbatim (`span` 1–12, `top_n` 2–12,
`page_size` 5–200, `height_mm` 30–200, margins 5–40, `text` 1–500 characters, `additionalProperties:
false` on every layout object, roles and named fonts only — never a hex, an RGB value or a URL).

## Phase 1: Setup

- [x] T001 Record the baseline this feature must not move (SC-006): `cd backend && uv run pytest`, `cd cli && uv run pytest`, `cd frontend && npm test`, and keep the output as the "before" evidence — `specs/026-declarative-layouts/plan.md`
- [x] T002 [P] Seed a report fixture carrying both layouts (KPI + line + bar + table web layout, one-page PDF layout with a table and a chart) and its expected figures — `backend/tests/fixtures/report_layout_026.json`

## Phase 2: Foundational (blocking: no story starts before this phase ends)

- [x] T003 Add `$defs.web_layout`, `$defs.web_component`, `$defs.pdf_layout`, `$defs.pdf_block`, `$defs.pdf_page`, `$defs.color_role`, `$defs.font_name` and the optional top-level `layout` property to the report schema, with `additionalProperties: false` on every object, the closed catalogues of component and block types, and the numeric limits of data-model §3–§5 — `cli/bizview_cli/schemas/report.schema.json`
- [x] T003b Add the optional `id` (metric-id pattern, NOT required) to every branch of `views[].oneOf`, so a layout can reference a view by id as FR-002 requires and `data-model.md` §10 defines; every existing report must still validate unchanged — `cli/bizview_cli/schemas/report.schema.json`
- [x] T003c [P] Test that a report whose views declare no `id` still validates, and that a view with an `id` validates — `cli/tests/test_validate_v2.py`
- [x] T004 [P] Extend the AI-facing schema summary with the layout (the catalogue, the roles, the font names and the limits) so `authoring.guide("report")` teaches `layout.web` and `layout.pdf` with one example each — `cli/bizview_cli/authoring.py`
- [x] T005 [P] Add the layout types to the API contract: `LayoutDocument`, `WebLayout`, `WebComponent`, `PdfLayout`, `PdfBlock`, `LayoutProblem`, and the additive `summary`/`totals` fields on the view types — `frontend/src/api/types.ts`
- [x] T006 [P] Add the series tokens `--c-chart-1`…`--c-chart-8` in the light and dark blocks, next to the existing `--c-chart-1`/`--c-chart-2` — `frontend/src/index.css`
- [x] T007 Implement `check_layout(definition, *, file, entry="report")` with the reference checks as **errors** (view, metric, dimension and filter ids that the report does not declare; unknown component or block type; duplicate ids; `columns`/`series` ids missing from the view) — `cli/bizview_cli/report_layout.py`
- [x] T008 Call `check_layout()` from the report traversal right after the report schema succeeds, so later checks never see an ill-formed layout; keep the `SCHEMAS` registry as it is (the layout is validated inside the report schema) — `cli/bizview_cli/validate.py`
- [x] T008b [P] Test that applying a workspace version whose layout has an error is refused with the same problems the CLI prints, through `compose.validate_project()` — `backend/tests/test_projects_compose.py`
- [x] T009 Expose `layout` in the normalized definition JSON, add the engine-generated `views[].summary` (one localised sentence per view, used as the web `aria-label` and the PDF caption) and `views[].totals` when a layout asks for totals, and emit `layout_problems` with the warnings — `backend/app/engine/report.py`
- [x] T009b Carry each view's `id` in the payload so both renderers bind a component to its view the same way (by id only, never by index or `type`); regenerate the payload snapshot through the sanctioned `UPDATE_SNAPSHOT_019=1` path and confirm in the diff that only the additive `id`/`summary` keys changed and `pdf_lines` did not — `backend/app/engine/report.py`, `backend/tests/fixtures/report_snapshot_019.json`
- [x] T009c Fix `_view_metrics()` so it returns a view's metric ids for **every** type (a `table` view declares `metrics: [...]` and the function returns `[]` for it today), which is why `totals: true` silently produced no Total row in either renderer — `backend/app/engine/report.py` (research R17)
- [x] T010 [P] Add the renderer strings of this feature to both catalogues (`layout.error_card`, `layout.more_rows`, `layout.totals_label`) — `frontend/src/i18n/es.ts`, `frontend/src/i18n/en.ts`
- [x] T011 [P] Add the PDF renderer strings (`pdf.more_rows`, `pdf.totals`, the summary caption label) to both catalogues — `backend/app/i18n/es.py`, `backend/app/i18n/en.py`

**Checkpoint**: the schema, the shared checks, the engine facts and the types exist; the three stories can now proceed in parallel.

## Phase 3: User Story 1 — the Asistente composes a dashboard (P1) 🎯 MVP

**Goal**: a `layout.web` in the report definition composes the dashboard; absent, today's order is kept.

**Independent Test**: the seeded report's layout renders KPI + line + bar + table in the declared order at 375 px and 1280 px, each bound to a declared view, with figures equal to the payload — and deleting `layout.web` restores the current order (quickstart scenario 1).

- [x] T012 [P] [US1] Unit tests: 12-column grid from the desktop breakpoint, declared order on phones, `span` honoured, unknown component renders the error card naming id and type, two components bound to two different views of the SAME view `type` render the two different payloads (the regression that index- or type-based binding would cause), and a component whose `view` is absent from the payload renders only its own error card — `frontend/tests/unit/layout-renderer.test.tsx`
- [x] T013 [P] [US1] Unit tests per chart kind: line/area keep the current/previous series and the null gaps; bar honours `orientation` and `stacked`; pie/donut keep `top_n` and group the rest under the localised "otros" label — `frontend/tests/unit/layout-charts.test.tsx`
- [x] T014 [P] [US1] e2e: the layout renders at 375 px and 1280 px in both themes, in the declared order and spans, with the accessibility summary present — `frontend/tests/e2e/layout.spec.ts`
- [x] T015 [US1] `LayoutRenderer.tsx`: grid, dispatch per component type, error card, and the `problems` note for warnings (never a blank dashboard) — `frontend/src/components/report/LayoutRenderer.tsx`
- [x] T016 [US1] Extend the SVG chart primitives with the missing kinds (vertical, horizontal and stacked bar; area; pie/donut with top-N and "otros"; KPI sparkline), sharing the scale, tick, currency and gap helpers of `TrendChart.tsx` — `frontend/src/components/report/charts/`
- [x] T017 [US1] `table` component attributes over the existing `DataTable` (ordered `columns`, `totals` rendered from the engine's `views[].totals`, client-side `sort`, `page_size`) keeping the horizontal scroll inside the card — `frontend/src/components/report/DataTable.tsx`
- [x] T018 [US1] `text` (markdown subset, `text`/`text_en` through `localized`, heading/paragraph/caption), `filters` (the report's own controls, `only[]`) and `spacer` components — `frontend/src/components/report/LayoutBlocks.tsx`
- [x] T019 [US1] `kpi` attributes: `metric` selection, `delta: previous_period|none` and optional `sparkline`, over the existing `KpiGrid`/`StatTile` — `frontend/src/components/report/KpiGrid.tsx`
- [x] T019b [US1] Resolve the semantic roles and the named fonts to concrete values: `colors` roles → the CSS variables (`--c-chart-1`…`--c-chart-8` and the existing semantic tokens, light and dark), `font_name` → the app's font stack inside `text` blocks; a role the theme does not define falls back to `primary` and never throws — `frontend/src/components/report/layoutRoles.ts`
- [x] T020 [US1] Safe fallbacks driven by the validation warnings: a line over a non-ordered dimension renders as bar; a pie whose categories exceed `top_n` renders top-N + "otros" — `frontend/src/components/report/LayoutRenderer.tsx`
- [x] T021 [US1] Delegate to `LayoutRenderer` when `def.layout?.web` exists, keeping the current `data.views` order, the TV size and the CSV base otherwise — `frontend/src/components/report/ReportViews.tsx`
- [x] T022 [US1] Dashboard reflects a new layout after a version is applied with no frontend redeploy (the definition arrives on `GET /api/reports/:id`, unknown keys already preserved) — `backend/app/services/dashboards.py`

## Phase 4: User Story 2 — the Asistente composes the PDF (P1)

**Goal**: a `layout.pdf` renders the declared blocks with ReportLab; absent, the fixed template stays.

**Independent Test**: the one-page layout exports as one PDF page in under 10 s, every figure equals the dashboard's payload, and `overflow` behaves as declared (quickstart scenario 2).

- [x] T023 [P] [US2] Tests: block order, one page stays one page, `overflow: continue` repeats the table header on the next page, `overflow: truncate` ends with the localised "y N más" line and the row count left out, an unknown block type fails validation before rendering — `backend/tests/test_pdf_declarative_layout.py`
- [x] T024 [P] [US2] Parity test: one query string through `GET /api/reports/{id}/data` and `POST /api/reports/{id}/pdf`; every figure of the payload appears in the PDF text read by `_pdf_lines`, including the summary of each view (SC-002) — `backend/tests/test_layout_parity.py`
- [x] T025 [P] [US2] Test: a 4-block report with a 500-row table renders under 10 s (SC-003) — `backend/tests/test_pdf_declarative_layout.py`
- [x] T026 [US2] `page_setup(layout)`: named size/orientation and integer margins (5–40 mm), defaulting to today's A4 portrait with 10 mm sides and 12 mm top/bottom — `backend/app/reports/pdf_layout.py`
- [x] T027 [US2] `render_layout(...)`: build the story block by block (`header` with the installation branding and logo role, `text`, `page_break`, `footer` with generated-at and page numbers, `kpi_row`) — `backend/app/reports/pdf_layout.py`
- [x] T028 [US2] `chart` blocks as vector drawings from `reportlab.graphics` (`LinePlot` for line, `VerticalBarChart`/`HorizontalLineChart` for bar, `Pie` for pie/donut, the engine's `summary` as caption, `height_mm` respected) — `backend/app/reports/pdf_layout.py`
- [x] T028b [US2] Resolve the semantic roles and the named fonts for the PDF: `colors` roles → the drawing palette (no hex from the layout), `font_name` → the ReportLab base-14 families the renderer already uses (`Helvetica`, `Helvetica-Bold`, `Times-Roman`, `Courier`), so no font file is shipped — `backend/app/reports/pdf_layout.py`
- [x] T029 [US2] `table` blocks with `repeatRows=1`, relative `widths`, the engine's `totals` as a final row outside the repeat region, and the `continue`/`truncate` policies — `backend/app/reports/pdf_layout.py`
- [x] T030 [US2] Wire the layout into `pdf.render()`: `definition["layout"]["pdf"]` → `render_layout(...)`, otherwise the current fixed story unchanged; keep `pdf.enabled` as the export gate and let `layout.pdf.page.orientation` win over `pdf.orientation` — `backend/app/reports/pdf.py`
- [x] T031 [US2] Keep the existing PDF suite green as the no-layout regression proof (SC-006) — `backend/tests/test_pdf_layout.py`

## Phase 5: User Story 3 — preview both layouts in the Asistente (P2)

**Goal**: a draft carrying layouts previews the dashboard and offers the preview PDF.

**Independent Test**: a complete draft with both layouts shows the dashboard from `layout.web` in Vista previa and downloads a PDF built from `layout.pdf`; a layout problem is listed with file and JSON path (quickstart scenario 3).

- [x] T032 [P] [US3] Tests: a draft with layouts previews the declaration, the preview data and the preview PDF; a layout problem appears in the draft result with file and JSON path — `backend/tests/test_assistant_preview.py`
- [ ] T033 [P] [US3] e2e: the assistant preview renders the layout and offers the preview PDF — `frontend/tests/e2e/assistant.spec.ts`
- [x] T034 [US3] Pass the draft definition's `layout` through the preview paths (definition, data, PDF) — `backend/app/api/projects.py`
- [x] T035 [US3] Report layout problems as draft problems with file, JSON path and the expected fragment, in the preview view as well — `backend/app/assistant/tools.py`
- [x] T035b [US3] ~~Ask for both layout halves in the report readiness check~~ **Superseded (2026-10-16)**: a missing layout must NOT gate readiness or applying — `ready = valid and not pending`, so the item made every layout-less draft unappliable, contradicting FR-009 and breaking 6 existing tests. FR-011 is carried by the guide and the preview instead (research R16). Net action: `backend/app/assistant/readiness.py` must behave as it did before this feature.
- [x] T035c [P] [US3] Regression test: a complete draft of a report that declares no layout is still `ready` with `pending == []` and applies (the existing `test_assistant_apply.py` and `test_assistant_direct.py::test_readiness_transitions_for_direct_draft` are that proof; do not weaken them) — `backend/tests/test_assistant_apply.py`, `backend/tests/test_assistant_direct.py`

## Phase 6: User Story 4 — a human edits the layout by hand (P3)

**Goal**: the same validation and the same documentation for a person editing `report.yaml`.

**Independent Test**: `bizview validate` accepts the golden layouts, fails on a dangling reference with file + JSON Pointer, warns on an unsuitable chart, and the guide documents every component and block (quickstart scenario 4).

- [x] T036 [P] [US4] CLI tests: golden layouts valid, dangling view/metric/filter/column reference reported with file and JSON Pointer, duplicate ids, out-of-range numbers, literal colour rejected, unsuitable chart warned without failing the run — `cli/tests/test_report_layout.py`
- [x] T037 [P] [US4] Guide test: every component and block of the catalogue is documented with one example and the two golden layouts validate — `cli/tests/test_authoring.py`
- [x] T038 [US4] Chart-suitability warnings in the shared checker, with the code, the `path` and the expected fragment (`layout_chart_unsuitable`, `layout_color_literal`, `layout_pdf_legacy_views`) — `cli/bizview_cli/report_layout.py`
- [x] T039 [US4] Add the golden *dashboard* layout (KPI row, line, bar ranking, table with totals) to the bundled golden workspace, adding the `id`s the layout references to its four views — `cli/bizview_cli/golden/projects/ejemplo/reports/facturas-dia/report.yaml`
- [x] T040 [US4] Add the golden *one-page PDF* layout to the direct-report golden workspace (with the view `id`s it references), so both shapes stay in CI — `cli/bizview_cli/golden-direct/projects/ejemplo/reports/ventas-directo/report.yaml`
- [x] T041 [US4] Document the layout model, the component and block catalogues with one example each, the roles, the font names and the golden layouts — `backend/app/assistant/guide/es/definir-un-reporte.md`, `backend/app/assistant/guide/en/definir-un-reporte.md`
- [x] T042 [US4] Document the effect on exports (layout-driven PDF, legacy `pdf.views`/`orientation`) — `backend/app/assistant/guide/es/exportar-pdf-csv.md`, `backend/app/assistant/guide/en/exportar-pdf-csv.md`
- [x] T043 [US4] Document (end-user voice, no YAML) how a declared layout changes a dashboard, what happens when `layout.web` is absent, the chart's summary sentence and the notice an unresolved card shows — `backend/app/assistant/guide/es/ver-reporte.md`, `backend/app/assistant/guide/en/ver-reporte.md` (page corrected 2026-10-16: `tableros.md` documents the dashboards *list* screen, `ver-reporte.md` documents viewing one)

## Phase 7: Polish & cross-cutting

- [x] T044 [P] Draft content check on the write path (reject `import `, `def `, `class `, `eval(`, `exec(`, `<script`, `<?php`, template markers and `#!` in a declarative draft), returning the existing draft-problem shape and writing nothing (FR-012) — `backend/app/assistant/tools.py`
- [x] T045 [P] 50 adversarial draft fixtures and their test: all rejected with file and line, a legitimate YAML layout accepted (SC-004) — `backend/tests/test_draft_content_check.py`
- [ ] T046 [P] Live eval: the Asistente proposes `layout.web` and `layout.pdf` valid on the first pass in at least 4 of 5 runs (SC-005) — `backend/tests/live/`
- [x] T047 [P] Regression proof that existing reports render identically with no layout declared (report payload, PDF story, view order) — `backend/tests/test_report_regression_019.py`, `frontend/tests/e2e/reporting.spec.ts`
- [x] T048 [P] Note the feature in the changelog and check the guide index for the new topic entries — `CHANGELOG.md`, `backend/app/assistant/guide/index.yaml`
- [x] T049 Full gate: backend `ruff` clean and `pytest` green **verified in focused groups** (a single-process full run exceeds practical time against the external database: ~24% in 90 min; every module in the feature's blast radius was run and is green), CLI `ruff` + **541 passed**, frontend `tsc` + **628 passed** + build + `check:compat`, Playwright **30/30** (layout, three engines × 320/375 px, both themes) + **2/2** (reporting regression) — `CONTRIBUTING.md`

## Dependencies

- **Phase 2 blocks everything**: T003 (schema) before T007/T008; T009 (engine facts) before T016, T028, T029 and T044's parity test.
- **US1 (Phase 3)** needs Phase 2 only; it is the MVP and is demonstrable on its own.
- **US2 (Phase 4)** needs Phase 2 only; it shares the payload with US1 but not its files, so the two can run in parallel.
- **US3 (Phase 5)** needs US1's renderer (T015) and US2's renderer (T030) to have something to preview.
- **US4 (Phase 6)** needs the schema (T003) and the checker (T038); the guide can start after T004.
- **Phase 7** T044/T045 need T009's payload and the assistant write path; T046 needs US1+US2+US4.

## Parallel execution examples

- **Phase 2**: T004 (CLI authoring), T005 (frontend types), T006 (CSS tokens), T010/T011 (catalogues) touch six different files → run together after T003.
- **US1**: T012, T013 and T014 are three independent test files → together; T016 (charts) and T018 (text/filters/spacer) are separate files → together.
- **US2**: T023, T024 and T025 are three independent test files → together; T026–T029 are one file written in order.
- **US4**: T036, T037 and the three guide-documentation tasks (T041–T043) touch disjoint files → together.

## Implementation strategy

1. **MVP**: Phase 1 + Phase 2 + US1 (Phase 3) — the Asistente composes a dashboard, with validation that fails on a dangling reference and today's behaviour preserved when no layout exists.
2. **Second increment**: US2 — the same declaration produces the one-page PDF, and SC-002's parity test is the gate between them.
3. **Third increment**: US3 (preview) and US4 (human editing: CLI, warnings, guide, golden layouts).
4. **Close**: Phase 7 — the content check, the adversarial fixtures, the regression proof and the live eval, then the full gate before the feature is called done.
