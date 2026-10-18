# Phase 1 Data Model: declarative layouts

Nothing here is stored in a new table: every entity below lives inside the report definition
(`reports/<id>/report.yaml`) or is derived per request by the engine. The field names are the
contract the schema, the CLI checks, both renderers and the guide must agree on.

## 1. LayoutDocument (`report.yaml` → `layout`)

The optional top-level object FR-001 adds. Absent → today's behaviour on both outputs (FR-009).

| Field | Type | Required | Rules |
|---|---|---|---|
| `layout.web` | WebLayout | no | Composition of the dashboard. |
| `layout.pdf` | PdfLayout | no | Composition of the exported PDF. |

`additionalProperties: false` on every object in this model. There is no `version` field: the report
definition is versioned as a whole by the workspace, and a layout travels with the version that
declares it (`WorkspaceVersion`), so an applied layout never mixes with another version's views.

## 2. WebLayout

| Field | Type | Required | Default | Rules |
|---|---|---|---|---|
| `components` | WebComponent[] | yes | — | Declared order is the phone order; on desktop it is reading order inside the 12-column grid. |
| `gutter` | enum `sm`\|`md`\|`lg` | no | `md` | Maps to an existing Tailwind spacing step; no pixel values in the document. |

## 3. WebComponent

Every component shares the same binding fields (FR-002):

| Field | Type | Required | Rules |
|---|---|---|---|
| `type` | enum (catalogue below) | yes | Unknown type = validation error. |
| `id` | string | yes | Unique inside `components`; used by validation messages. |
| `view` | string | yes for every type except `text`/`spacer`/`filters` | Must equal a declared `views[].id` in the same report. |
| `span` | integer 1–12 | no | Grid columns from the desktop breakpoint; default `12` (full width). Phones stack in declared order regardless of `span`. |
| `title` | string / `title_en` | no | Falls back to the view's own title, then to the metric/dimension labels. |
| `colors` | ColorRole / ColorRole[] | no | Roles only (R8). |
| `summary` | boolean | no | Default `true`: show/announce the engine-generated text summary (accessibility). |

Per-type attributes:

| `type` | Extra fields | Rules |
|---|---|---|
| `kpi` | `metric` (required, declared metric id), `delta`: `previous_period`\|none (default `previous_period`), `sparkline`: boolean (default `false`) | `delta: previous_period` requires the view to carry previous-period data; a `kpi` view with more than one item is allowed and renders as a row. |
| `line` / `area` | `x` (dimension or grain from the view), `series[]` (metric ids) | `x` must be an ordered dimension or a grain, otherwise a warning (R10) and the renderer falls back to `bar`. |
| `bar` | as above plus `orientation`: `vertical`\|`horizontal` (default `vertical`), `stacked`: boolean (default `false`) | `stacked` needs at least two `series`; otherwise validation error. |
| `pie` / `donut` | `category` (dimension), `value` (metric), `top_n` (integer 2–12, default 6), `other_label` / `other_label_en` | When the view returns more categories than `top_n`, the renderer keeps the top N and groups the rest as "otros" with the summed value; the `other_label` default comes from the i18n catalogue. |
| `table` | `columns[]` (metric/dimension ids; default: the view's own columns), `totals`: boolean (default `false`), `sort`: `{by, dir}` , `page_size` (integer 5–200, default: view `limit`) | `columns` ids must exist in the view; `sort.by` must be one of `columns`. |
| `text` | `text` (required, string 1–500), `text_en`, `style`: `heading`\|`paragraph`\|`caption` (default `paragraph`) | Markdown subset: bold, italics, links and line breaks only. No HTML. |
| `filters` | `only[]` (filter ids declared by the report; default: all) | Renders the report's own filter controls; `only` ids must be declared in `filters`. |
| `spacer` | `size`: `sm`\|`md`\|`lg` | Layout only; prints nothing in the PDF. |

## 4. PdfLayout

| Field | Type | Required | Default | Rules |
|---|---|---|---|---|
| `page` | `{size: a4\|letter, orientation: portrait\|landscape, margins: {top,right,bottom,left}}` | no | `a4`, `portrait`, the current 10 mm sides / 12 mm top-bottom | Overrides `pdf.orientation` when both are present (R2). Sizes are named; no numeric page sizes. |
| `blocks` | PdfBlock[] | yes | — | Rendered in order. |
| `overflow` | enum `continue`\|`truncate` | no | `continue` | Default policy for table blocks: `continue` repeats headers on the next page, `truncate` stops and prints "y N más". |

## 5. PdfBlock

| Field | Type | Required | Rules |
|---|---|---|---|
| `type` | enum `header`\|`kpi_row`\|`chart`\|`table`\|`text`\|`page_break`\|`footer` | yes | `page` is a property of `layout.pdf`, not a block. Unknown type = validation error before rendering. |
| `id` | string | yes | Unique inside `blocks`. |
| `view` | string | yes for `kpi_row`/`chart`/`table` | A declared view id, same rule as the web. |

Per-type attributes:

| `type` | Extra fields | Rules |
|---|---|---|
| `header` | `title`: boolean (use the report title), `subtitle`: boolean (report description), `period`: boolean, `logo`: boolean, `logo_role`: `brand`\|none | Everything resolves from the installation's branding and the report definition; no free URLs (R8). |
| `kpi_row` | `items[]` (metric ids), `delta`: boolean | One row of KPI cells; wraps by `columns`. |
| `chart` | `kind` (same chart kinds as the web), `x`, `series[]`, `height_mm` (integer 30–200, default 60), `category`, `value`, `top_n` | Vector drawing via `reportlab.graphics` (R6). |
| `table` | `columns[]`, `widths[]` (relative weights, same length as `columns`), `totals`, `overflow`: `continue`\|`truncate` (defaults to `layout.pdf.overflow`) | `repeatRows=1` when continuing. |
| `text` | `text`, `text_en`, `style`, `align`: `left`\|`center`\|`right` | Same markdown subset. |
| `footer` | `generated_at`: boolean, `page_numbers`: boolean, `legal`: string / `legal_en` | The legal line is authored content, not a link. |
| `page_break` | — | Forces a new page at that position. |

## 6. Shared value objects

**ColorRole** — enum `primary`, `positive`, `negative`, `neutral`, `muted`, `series[1..8]`. Resolved by
the installation: the web maps them to CSS variables (`--c-chart-1..8` plus the existing semantic
tokens, light and dark), the PDF to the generated palette of the active theme (R8). A hex value is a
validation error, never a warning.

**FontName** — enum `sans`, `sans_bold`, `serif`, `mono`. The web ignores it for the body text of the
app shell but honours it inside a `text` block; the PDF maps it to the ReportLab base-14 family it
already uses (`Helvetica`, `Helvetica-Bold`, `Times-Roman`, `Courier`). No font file is shipped.

**ViewRef** — the `view` field of a component or block: the id of a declared view. It is the single
indirection that makes dashboard/PDF parity possible: both renderers resolve the same id to the same
row set of the same payload (R7). See §10 for the `id` this requires on a view.

## 10. View identity (decision of 2026-10-16, found while planning against the code)

The report's `views` entries had **no `id`** before this feature: each item is a `oneOf` branch keyed
by `type` (`kpis`, `trend`, `ranking`, `table`) with `additionalProperties: false`, so two `trend`
views are indistinguishable to a reference. FR-002 requires binding "by id only", so the feature adds
an **optional** `id` to every `views[].oneOf` branch, with the same pattern as a metric id
(`^[a-z][a-z0-9_]{0,40}$`).

| Aspect | Rule |
|---|---|
| Required? | No. It stays out of every branch's `required`, so every existing report validates unchanged (FR-009). |
| When needed | Only a report that declares a `layout` needs ids, and only on the views that layout references. |
| Reference | `layout.web.components[*].view` / `layout.pdf.blocks[*].view` must equal a declared view's `id`. |
| Resolution | By id only. Never by array index and never by view `type` — two views of the same `type` are a legitimate case (research R15). |
| Payload | Each view in the API payload carries its `id` so both renderers can bind the same way; a view without an `id` omits the key. |
| Error | A layout reference that resolves to nothing is `layout_view_missing`, whose fix hint tells the author to declare `id` on the view. |

## 7. Derived view facts (engine, per request)

Produced once in `backend/app/engine/report.py` and consumed by both renderers (R7).

| Field | Type | When | Rules |
|---|---|---|---|
| `views[].summary` | string | Always | One sentence, localised, generated from the view's type, grain/period, metric labels and top values. Used as the web chart's `aria-label`/`figcaption` and the PDF chart's caption (accessibility edge case). |
| `views[].totals` | object | When a layout asks for `totals` on that view | Value per metric with the metric's own formatting and `better` semantics; the frontend table and the PDF table print the same numbers, so a total can never disagree between the two outputs. |

## 8. LayoutProblem (validation result)

Reuses `cli/bizview_cli/validate.py::Issue` exactly; no new type is introduced.

| Field | Meaning |
|---|---|
| `entry` | the artifact kind (`report`). |
| `code` | stable code (`layout_view_missing`, `layout_metric_missing`, `layout_column_missing`, `layout_filter_missing`, `layout_block_unknown`, `layout_chart_unsuitable`, `layout_color_literal`, …). |
| `level` | `error` (blocks apply) or `warning` (renders with a safe fallback). |
| `file` | `reports/<id>/report.yaml`. |
| `path` | JSON Pointer into the definition, e.g. `/layout/web/components/2/view`. |
| `expected` | the schema fragment or the allowed set. |
| `fix` | optional human hint, as `_hint()` already produces. |

State transition of a layout, per report version: `absent` → today's behaviour; `invalid` → the
version cannot be applied (FR-013); `valid` → rendered by both renderers.

## 9. Relationships

```text
report.yaml
├── metrics ────┐
├── dimensions ─┤                       (existing, untouched)
├── views ──────┼──< ViewRef >── layout.web.components[*].view
│  (+ optional  └──< ViewRef >── layout.pdf.blocks[*].view
│   `id`, §10)
├── filters ────────< id in >── layout.web.components[type=filters].only[]
├── pdf {enabled, orientation, views}   (existing; `enabled` still gates the export)
└── layout {web, pdf}                   (new, optional)

request time:  run_views(view refs) ─┬─→ /data payload ─→ LayoutRenderer (web)
                                      └─→ same payload ─→ PdfLayoutRenderer (reportlab)
                                          + views[].summary, views[].totals (added by the engine)
```

Deleting a view from a report that a layout references produces a validation error naming the
component and the missing id (US1 acceptance 2) — the layout never silently renders less.
