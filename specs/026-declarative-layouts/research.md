# Phase 0 Research: declarative layouts for dashboards and PDF reports

Every decision below is grounded in the code as it stands on 2026-10-16. Paths are repository
relative; line numbers were read while planning and may drift.

## R1. Where the layout schema lives

**Decision**: define `web` and `pdf` as `$defs` entries (`web_layout`, `pdf_layout`, and the shared
fragments `layout_problem`-free pieces: `color_role`, `font_name`, `view_ref`) inside
`cli/bizview_cli/schemas/report.schema.json`, and add one optional top-level property `layout`
with `additionalProperties: false` and `properties: {web, pdf}`.

**Rationale**: the layout is not a separate artifact — it is a key of `report.yaml` — so it must be
validated by the report schema, whose top level already declares `additionalProperties: false` and
would reject an unknown `layout` key today. Internal `$ref`s inside one file need no registry:
`cli/bizview_cli/validate.py` builds `Draft202012Validator` per schema and resolves `#/$defs/...`
automatically. Keeping it in this file also puts the layout in front of the AI for free, because
`cli/bizview_cli/authoring.py::_report_summary()` reads `validate.SCHEMAS["report"].schema`, and
`authoring.guide("report")["schema"]` is the fragment the Asistente receives.

**Alternatives considered**: a new `cli/bizview_cli/schemas/layout.schema.json` (rejected: it would
need a cross-file `$ref` registry in `_schema()` and a second registration in `SCHEMAS`, and it would
still be a key of `report.yaml`, so the report schema would need the property anyway); a JSON Schema
in the frontend (rejected: three copies to keep in step, which is exactly what FR-001 forbids).

## R2. Naming and migration of the existing `pdf` object

**Decision**: keep `pdf.enabled` exactly as it is — it is the export gate read by six call sites —
and add `layout.pdf` as the composition document. Precedence when both exist:
`layout.pdf.page.orientation` wins over `pdf.orientation`, and `layout.pdf` blocks define order.
When `layout.pdf` is absent, `pdf.orientation` and `pdf.views` behave as today (FR-009).

**Rationale**: `backend/app/api/reports.py`, `backend/app/api/projects.py`,
`backend/app/api/shared.py`, `backend/app/api/assistant.py`, `backend/app/mail/subscriptions.py` and
`backend/app/mail/sends.py` raise or skip the export on `definition["pdf"]`; the value comes from the
engine (`backend/app/engine/report.py::definition_json`, which always writes `"pdf": bool(...)`) and
never from the raw YAML. Deprecating `pdf.enabled` would therefore touch the mail and share paths for
no gain. `pdf.views` (indices into `views`) is a weaker version of what `layout.pdf` expresses by id,
so it stays supported but undocumented in the guide as the old way.

**Alternatives considered**: rename `pdf` to `layout.pdf.config` and migrate everything (rejected:
touches six unrelated call sites and the distribution/email flows, and gives no new capability); make
`pdf` a strict alias and emit a validation warning when `pdf.views` is present together with
`layout.pdf` (accepted as part of R10 — the warning, not the alias).

## R3. A single module for the layout rules

**Decision**: add `cli/bizview_cli/report_layout.py` for every rule that is not expressible in JSON
Schema: reference checks (view/metric/dimension/filter ids), chart-suitability warnings,
`overflow`/`columns` consistency, and the draft content check (R9). The CLI validator calls it; the
backend gets it for free because `backend/app/projects/compose.py` and `apply.py` already import
`bizview_cli.validate`.

**Rationale**: FR-014 requires warnings to be the same in the CLI and the Asistente, and
`cli/bizview_cli/validate.py::Issue` already carries `entry`, `code`, `message`, `level`, `file`,
`path`, `expected` and `fix` — everything a warning needs. One module means one behaviour; the
renderers stay dumb about validation.

**Alternatives considered**: reimplement the checks in the backend (rejected: two behaviours to keep
in step); put them in `backend/app/engine/` (rejected: the CLI cannot import the backend, which
would break `bizview validate` and the "same schemas" promise of FR-013).

**Naming**: `cli/bizview_cli/layout.py` is taken — it is the project workspace layout of feature 020
(project folders and allowed paths) and is imported by the backend and the zip importer. The new
module must not shadow it.

## R4. Web renderer shape

**Decision**: a new `frontend/src/components/report/LayoutRenderer.tsx` receives `layout`, `data` and
`def`, produces a 12-column CSS grid (`grid-cols-1` on phones, `md:grid-cols-12` from the desktop
breakpoint) and dispatches each component to an adapter that reuses the existing components:
`kpi` → `KpiGrid`/`StatTile`, `line`/`area`/`bar` → the SVG chart primitives, `table` → `DataTable`
with the layout's columns/totals, `text` → a markdown subset, `filters` → the existing `ParamsForm`
block, `spacer` → an empty grid cell. `ReportViews.tsx` keeps its role and delegates: no
`layout.web` → today's `data.views.map(...)` (FR-009); unknown component → an error card that names
the component, never a blank dashboard (FR-006).

**Rationale**: `ReportViews.tsx` is already the single place where the implicit composition is
decided and it is already shared by the report screen and the assistant preview, so the change is one
branch in one file plus the renderer. `KpiGrid` already handles `compared` and `size`, `DataTable`
already scrolls horizontally inside its card, and `ParamsForm` already owns the filter controls and
the `loadOptions` callbacks.

**Alternatives considered**: replacing `ReportViews` (rejected: TV mode, the assistant preview and
the CSV export paths all use it); a generic recursive renderer driven by the schema (rejected: the
component catalogue is small and typed, and TSX props are the better contract).

## R5. Charts: extend the SVG primitives, do not adopt Recharts here

**Decision**: build the missing kinds — vertical/horizontal/stacked `bar`, `area`, `pie`/`donut` with
top-N plus "otros", and the KPI `sparkline` — on the app's existing SVG approach in
`frontend/src/components/report/charts/`, sharing scale/tick/label helpers with `TrendChart.tsx`.

**Rationale**: the app has no Recharts import today; charts are hand-written SVG with currency
formatting, null-gap handling and semantic CSS classes, and they are covered by tests. Adding
Recharts for this feature would mean a second charting system, a second theming path and a second set
of tests, while constitution V lists Recharts only as an available stack component. No new dependency
is introduced either way.

**Alternatives considered**: adopt Recharts for the new kinds (deferred: legitimate, but it is a
visual-language decision for the whole product, not a requirement of layouts — recorded in
plan.md's findings for the Owner); render charts server-side to images for the web (rejected:
defeats the responsive, theme-aware dashboard).

## R6. PDF renderer shape

**Decision**: a new `backend/app/reports/pdf_layout.py` holds `PdfLayoutRenderer`, mapping blocks to
ReportLab flowables — `page` sets page size/orientation/margins, `header`/`footer` build paragraphs
with the branding logo (`organization`, `product` are already passed into `pdf.render`), `kpi_row` a
`Table`, `chart` a `reportlab.graphics` drawing (`LinePlot` as today, `VerticalBarChart`/`Pie` for
the new kinds), `table` a `Table` with a `repeatRows=1` header and the declared `overflow` policy,
`text` paragraphs, `page_break` a `PageBreak`.

**Rationale**: `backend/app/reports/pdf.py::render` already receives `definition`, `payload`,
`organization`, `product`, `viewer`, `preview`, `layout` and `locale`; the fixed block sequence lives
in lines 230-288 and becomes a dispatch over `layout.pdf.blocks` when present, with the current
sequence as the fallback (FR-009). `reportlab.graphics.charts` is part of the installed ReportLab, so
constitution V is respected; the existing PDF tests already assert on uncompressed streams
(`test_reports_params.py::_pdf_lines`), and `pageCompression=0` plus `invariant=1` are already set
for testability.

**Alternatives considered**: rasterising charts with a headless browser (rejected: a container
dependency and a second rendering engine); matplotlib (rejected: new stack component); keeping one
monolithic renderer in `pdf.py` (rejected: `pdf_layout.py` keeps the 300-line fixed template readable
and testable on its own).

## R7. Parity (FR-008, SC-002) and the figures both renderers must agree on

**Decision**: parity is structural — `GET /api/reports/:id/data` and
`POST /api/reports/:id/pdf` both call `backend/app/api/reports.py::_data()`, which calls
`engine.run_views(...)`. On top of that structure the plan adds two derived facts produced **once**
in the engine and consumed by both renderers:

- `summary` per view: the one-sentence text summary used as the web chart's `aria-label` and as the
  PDF chart's caption/alt text (the spec's accessibility edge case). Generated server-side so the two
  renderers cannot word it differently.
- `totals` per table/ranking view: computed in the engine, where the metric aggregation semantics
  live, and requested by the layout's `table.totals`.

**Rationale**: SC-002 is "automated" and the honest way to automate it is to assert the dashboard
payload's figures appear in the PDF for the same query string. Doing the totals and the summary in the
engine also avoids the classic defect of a total that adds up in the web table and not in the PDF.

**Alternatives considered**: computing totals in the frontend (rejected: PDF has no frontend);
summing rendered rows in the PDF renderer (rejected: the same metric would be accumulated twice,
differently).

## R8. Theme roles and fonts

**Decision**: the layout accepts only semantic roles: `primary`, `positive`, `negative`, `neutral`,
`series[1..8]`, and font names from a closed set (`sans`, `sans_bold`, `serif`, `mono`). The web
resolves roles through CSS variables; `frontend/src/index.css` grows `--c-chart-1..8` (light and
dark) next to the existing `--c-chart-1`/`--c-chart-2`. The PDF resolves the same roles to the
ReportLab base-14 fonts (`Helvetica`, `Helvetica-Bold`, `Times-Roman`, `Courier`), which the product
already ships and which `pdf.py` already uses.

**Rationale**: layouts must never carry hex colours (spec FR-005 and the dark-mode edge case), and
today there is no `series[n]` mechanism to reference — only two chart variables. No font files are
added, so "only fonts shipped with the product" holds; `pdf.py` currently registers no custom font,
so the named set maps onto the base-14 fonts it already relies on.

**Alternatives considered**: shipping Inter/DejaVu for the PDF (deferred: a licensing and packaging
decision, not needed to place blocks); letting the layout name CSS variables directly (rejected: that
is implementation leaking into customer data, and CLI validation could not check it).

## R9. The AI is bounded (FR-012, SC-004)

**Decision**: the content check runs on the draft write path
(`backend/app/assistant/tools.py::_write_ops`, which already calls `fs.apply_ops` and
`compose.validate_project`). It rejects content that is executable or code-shaped in a declarative
artifact: Python/JS/HTML markers (`import `, `def `, `eval(`, `exec(`, `<script`, `<?php`), and any
key value that is not scalar or collection data. For layouts specifically, the schema already makes
injection structurally impossible: `additionalProperties: false`, an enum of component and block
types, no free-text attribute that a renderer evaluates, and no URL or colour field. The existing CLI
read-only SQL enforcement (`sqlglot`, `backend/app/assistant/personal.py`) is untouched, and the
existing limits (`backend/app/projects/fs.py`: 512 KiB per file, 400 files, 240-char paths, plus the
`cli/bizview_cli/layout.py::ALLOWED_TEXT` path set) stay as they are; the layout needs no new file
type, because it lives inside the already-allowed `reports/<id>/report.yaml`.

**Rationale**: the draft path is where untrusted model output enters the product, and it is one
function; putting the check there covers every draft file at once. Naming the markers explicitly is
what makes SC-004's 50 adversarial fixtures testable.

**Alternatives considered**: extending the check to the human editor path
(`backend/app/api/projects.py::write_file`) as well (rejected for this feature: a person editing their
own Git workspace is not the threat model FR-012 describes, and the CLI validator already refuses a
layout it cannot validate); a full YAML-sanitising library (rejected: a new dependency for a check
that a dozen markers and the schema cover).

## R10. Errors, warnings and the "no spec, no run" extension (FR-013, FR-014)

**Decision**: JSON Schema violations are errors (as today, with `file` + JSON Pointer `path` +
`expected` via `validate.py::_schema_errors`). The checks in `report_layout.py` raise errors for
dangling references (a component bound to a view, metric, dimension or filter that the report does
not declare; a `table.columns` id that is not in the view; a block type outside the catalogue) and
warnings for a poor-but-renderable choice (a pie over more categories than the top-N threshold, a
line over a non-ordered dimension, `pdf.views` together with `layout.pdf`). The backend refuses to
apply a version whose layout has errors, through the existing
`backend/app/projects/compose.py::validate_project` / `backend/app/workspace/service.py::validate_root`
path, so the refusal is the same one that already guards reports.

**Rationale**: `Issue.level` and the `errors`/`warnings` split already exist end to end — the CLI
prints warnings without failing (`__main__.py` returns non-zero only on `result.ok` being false), and
the assistant's draft result already exposes `valid`, `errors`, `warnings`, `files`, `readiness`.

**Alternatives considered**: warnings only in the frontend (rejected: FR-014 demands CLI and
Asistente both, and the CLI is where a human author works).

## R11. Preview (US3)

**Decision**: reuse the existing preview path unchanged in shape —
`backend/app/api/projects.py::preview_report` (definition), `preview_report` data via
`assistant_preview.report_data`, and `preview_report_pdf` (which already calls
`pdf.render(..., preview=True)`). The frontend preview reuses `ReportViews`, so `layout.web` renders
in the preview the moment US1 lands; `layout.pdf` renders in the preview PDF the moment US2 lands.
A layout problem is reported as a draft problem with file and JSON path (015 FR-003), which is what
R10's `Issue` shape already provides.

**Rationale**: 015 built exactly this pipeline for views; layouts are another key of the same
document, so nothing new is needed beyond passing the definition through.

## R12. Guide and golden layouts (FR-010)

**Decision**: `cli/bizview_cli/authoring.py` gains a layout section in `_report_summary()` (derived
from the schema, so it cannot drift) and the component/block catalogue with one example each in
`authoring.guide("report")`. The human-facing guide bodies (`backend/app/assistant/guide/es|en/`)
update `definir-un-reporte.md`, `exportar-pdf-csv.md` and `tableros.md`. The two golden layouts live
in the bundled golden workspaces (`cli/bizview_cli/golden/...` and
`cli/bizview_cli/golden-direct/.../report.yaml`), which CI already validates through the CLI suite —
so "CI keeps them valid" is a property of the existing tests, not a new mechanism.

**Rationale**: the guide is generated from the schema where it can be, which is the only way the
catalogue and the validator stay in step; the golden workspaces are what the AI is shown as examples
(`GOLDEN` in `authoring.py`), so a golden dashboard layout and a golden one-page PDF layout teach the
model by example exactly as FR-010 intends.

## R13. i18n of layout text (constitution constraint)

**Decision**: a `text` component/block takes `text` plus an optional `text_en`, resolved by the
existing `localized(value, field)` helper on the frontend and by `backend/app/reports/pdf.py`'s
existing `localized(...)` call on the backend — the same convention report titles and metric labels
already use. Renderer messages (error card, "y N más", summary lines) go into
`frontend/src/i18n/{es,en}.ts` and the backend catalogue.

**Rationale**: no new localization mechanism, and the rule "authored workspace content is shown as
written" (constitution) is respected: the layout author decides both languages.

## R14. Test strategy per user story

**Decision**:

| Story | Proof |
|---|---|
| US1 | vitest unit tests per component kind (`LayoutRenderer` grid, span and order; fallback card for an unknown component) + Playwright `layout.spec.ts` at 375 px and 1280 px in both themes, with the accessibility summary asserted. |
| US2 | `backend/tests/test_pdf_declarative_layout.py`: block order, one-page layout stays one page, 500-row table under the 10 s budget, `overflow: truncate` emits "y N más", repeated headers on continuation, unknown block fails validation before rendering. |
| US2/SC-002 | `backend/tests/test_layout_parity.py`: drive one query string through `/data` and `/pdf` and assert every figure of the payload appears in the PDF text (`_pdf_lines`). |
| US3 | extend `backend/tests/test_assistant_preview.py` (draft with layouts → preview definition, preview data and preview PDF) + a Playwright assertion in the existing assistant/preview spec. |
| US4 | `cli/tests/test_report_layout.py`: `bizview validate` accepts the golden layouts, fails on dangling references with file + JSON Pointer, warns on unsuitable charts, and the guide exposes every component and block. |
| SC-004 | `backend/tests/test_draft_content_check.py` over a 50-fixture adversarial set. |
| SC-005 | the existing live eval harness (`backend/tests/live/`, 015 SC-001) gains the "layout present and valid on the first pass" assertion. |
| SC-006 | the existing report regression suite (`backend/tests/test_report_regression_019.py`, `test_pdf_layout.py`) must pass untouched — that is the no-layout-unchanged proof. |

**Rationale**: each story is testable without the next one, which is what the spec's Independent Test
lines claim, and no new test framework is introduced.

## R15. Views need an id before a layout can reference them

**Decision**: add an **optional** `id` (same pattern as a metric id) to every `views[].oneOf` branch
of the report schema, and make a layout reference a view by that id only. The engine includes the id
in each view payload; the CLI checker refuses a layout reference that resolves to no declared id
(`layout_view_missing`, with the fix hint "declare `id` on the view").

**Rationale**: this was found by reading the schema while planning, not by assuming. Today a `views[]`
item is a `oneOf` branch keyed by `type` with `additionalProperties: false` and no `id`, so views are
identifiable only by array position — which is exactly the fragility the old `pdf.views: [0, 1, 2, 3]`
(an array of indices into `views`) already suffers from, and which FR-002 forbids ("bind by id only").
Two views of the same `type` are legitimate and would be indistinguishable by index-free means.
Making the id optional keeps every existing report valid untouched (FR-009), so the cost is paid only
by the reports that adopt a layout, and the error message tells the author exactly what to add.

**Alternatives considered**: bind by array index, reusing the existing `pdf.views` convention
(rejected: contradicts FR-002, breaks the moment a view is inserted or reordered, and makes the
"dangling reference" error impossible to word usefully); derive an id from `type` plus the metric
(rejected: two `trend` views on the same metric, or a reordering of the definition, would silently
repoint a component at another view); make `id` required on every view (rejected: it would invalidate
every existing report at once, which FR-009 exists to prevent).

**Recorded in**: `spec.md` (decision note) and `data-model.md` §10.

## R16. A missing layout must not gate readiness or applying

**Decision**: the "a complete draft declares both layout halves" expectation (FR-011) is carried by
the authoring guide and by the preview, **not** by `backend/app/assistant/readiness.py`. A draft of a
report without a layout stays `ready` and applies exactly as before.

**Rationale**: `readiness.compute()` ends with `ready = valid and not pending`, so anything appended
to `pending` makes a draft unappliable. Adding the layout halves there made **every** draft of a
layout-less report un-ready: five tests in `backend/tests/test_assistant_apply.py` and
`test_assistant_direct.py::test_readiness_transitions_for_direct_draft` (which asserts
`pending == []` and `ready is True` on a complete draft) failed. That is FR-009 inverted — "existing
reports keep working unchanged" cannot survive a gate that requires a layout to apply an existing
report's new version. A recommendation nobody can ignore is not a recommendation.

**Alternatives considered**: updating the six tests to expect the new pending item (rejected: it
would redefine "complete" for every customer's existing drafts and leave the product unable to apply
a version of a report that legitimately declares no layout); adding a separate advisory channel to
the readiness payload (deferred: a contract change across the assistant UI for no behavioural gain,
while the guide already reaches the model on every turn); keeping the item only for drafts the
Asistente composes (rejected: indistinguishable from a human's draft on this path).

**Measured**: the six failures reproduce on this branch and are the evidence for this decision.

## R17. `totals` needs the metrics of every view type, not just `kpis`

**Decision**: `backend/app/engine/report.py::_view_metrics()` must return the metric ids of a view
whatever its type — a `table` view declares `metrics: [...]`, and today the function returns `[]`
for it.

**Rationale**: found by the test that asserts `totals: true` on a table block. `_view_totals()`
computes `_view_metrics(vdef) ∩ ctx.metrics`, so a `table` view yields an empty set and
`views[].totals` is never emitted — the `totals: true` the golden layout declares for its `detalle`
table silently prints no Total row in either renderer. It is precisely the defect class this feature
must not ship: a layout that says something the renderer silently ignores. The function's own
docstring already says "whatever its type", so the code contradicts its contract.

**Alternatives considered**: fixing `_view_totals` to read `vdef["metrics"]` directly (rejected:
duplicates the metric-extraction rule that `_view_metrics` exists to own); making `totals` legal only
on `kpis` (rejected: FR-003 lists totals among a table's attributes).
