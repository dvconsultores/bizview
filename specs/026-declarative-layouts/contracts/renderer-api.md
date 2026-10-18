# Contract: renderer interfaces, engine payload and validation problems

Three internal interfaces change or appear with this feature. They are contracts because three
different codebases implement them (CLI, backend, frontend) and because the guide documents them.

## 1. Engine payload additions (`GET /api/reports/{id}/data`)

Both renderers read one payload, so the two derived facts live here (R7). Shapes are additive: a
client that ignores them keeps working.

```jsonc
{
  "selection": { /* unchanged: period, current, previous, compare, filters, timezone */ },
  "filters": { /* unchanged */ },
  "freshness": { /* unchanged */ },
  "views": [
    {
      "id": "diaria",
      "type": "trend",
      "metric": "ventas_netas",
      "grain": "day",
      "points": [ /* unchanged */ ],
      "summary": "Ventas netas por día del 1 al 30 de septiembre de 2026; máximo 12.480,00 el 18.",
      "totals": { "ventas_netas": 128450.0 }        // only when a layout asks for totals
    }
  ],
  "layout_problems": [
    { "level": "warning", "code": "layout_chart_unsuitable",
      "path": "/layout/web/components/1/x", "message": "…", "expected": "…" }
  ]
}
```

- `summary` is always present (accessibility + PDF caption); it is generated once, in the engine, so
  the web `aria-label` and the PDF caption are the same sentence.
- `totals` appears only for views a layout marks with `totals: true`, computed with the metric's own
  aggregation and formatting.
- `layout_problems` is advisory: errors are already refused before a version is applied (FR-013); the
  warnings travel so the dashboard can render with its documented fallback instead of failing.

## 2. Web renderer: `frontend/src/components/report/LayoutRenderer.tsx`

```ts
export type WebComponent = { /* see specs/026-declarative-layouts/data-model.md §3 */ };
export type WebLayout = { gutter?: "sm" | "md" | "lg"; components: WebComponent[] };
export type LayoutProblem = {
  level: "error" | "warning"; code: string; path: string; message: string; expected?: string;
};

export function LayoutRenderer(props: {
  layout: WebLayout;
  data: ReportData;             // the payload above
  def: ReportDefinition;        // metrics/dimensions/filters/currency
  size?: "normal" | "tv";       // TV keeps working (ReportView's TvLayout path)
  csvBase?: string;             // CSV export stays available in the table components
  problems?: LayoutProblem[];   // warnings to show as a quiet note, not a failure
}): JSX.Element;
```

Behaviour contract: 12-column grid from the `md` breakpoint, declared order on phones; one adapter
per component `type`; an unknown type renders the error card naming the id and the type; nothing is
`eval`ed and no component reads a URL, an HTML string or a colour literal from the layout.
`ReportViews` keeps its exported name and props and delegates to `LayoutRenderer` when
`def.layout?.web` exists.

## 3. PDF renderer: `backend/app/reports/pdf_layout.py`

```python
def render_layout(*, definition: dict, payload: dict, styles, organization: str, product: str,
                  viewer: str | None, preview: bool, locale: str) -> list:  # ReportLab flowables
    """Story for `definition["layout"]["pdf"]`; the caller (pdf.render) keeps the template fallback."""

def page_setup(layout: dict) -> tuple[Any, dict[str, float]]:
    """(pagesize, margins in mm) from layout.pdf.page, with today's defaults."""
```

`pdf.render()` contract is unchanged for every existing caller (six routes plus mail): the new
parameter is the already-present `layout`, and the decision is
`definition["layout"]["pdf"]` → `render_layout()` else → the current fixed story. `preview=True`
stays the only difference for draft previews.

## 4. CLI validation entry point

```python
# cli/bizview_cli/report_layout.py
def check_layout(definition: dict, *, file: str, entry: str = "report") -> list[Issue]:
    """Reference checks (errors) and chart-suitability checks (warnings) for layout.web/layout.pdf."""

# cli/bizview_cli/validate.py
SCHEMAS = {n: _schema(n) for n in
           ("integration", "report", "request", "workspace", "project", "distribution")}
# unchanged: the layout is validated as part of the report schema
```

`check_layout()` is called from the report traversal (`validate.py::_load_entries` /
`_validate_v2`) right after the report schema succeeds, so an invalid layout is never followed by
checks that assume it is well formed. Every `Issue` carries `file` and a JSON Pointer `path`; the
backend reaches the same code through `backend/app/projects/compose.py` and
`backend/app/projects/apply.py`, which is what makes FR-013 ("no spec, no run" extends to layouts)
true on both sides.

## 5. Draft content check (FR-012, SC-004)

```python
# backend/app/assistant/tools.py::_write_ops  (draft path, after fs.apply_ops and before validation)
rejects: "#!python", "import ", "def ", "class ", "eval(", "exec(", "<script", "<?php", "{{", "{%"
allowed: YAML/JSON data, read-only SQL checked by sqlglot, markdown
```

A rejected draft returns the existing draft-problem shape (`file` + `path` + `message`) naming the
offending line, and no file is written. The 50-fixture adversarial set of SC-004 lives in
`backend/tests/test_draft_content_check.py`.
