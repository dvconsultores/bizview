# Contract: `layout.web` document

**Owner**: `cli/bizview_cli/schemas/report.schema.json` (`$defs.web_layout`). This file is the
human-readable contract; the schema is normative. Consumers: `bizview validate`, the Asistente
authoring guide, `frontend/src/components/report/LayoutRenderer.tsx`.

## Shape

```yaml
# reports/ventas/report.yaml (excerpt)
layout:
  web:
    gutter: md            # sm | md | lg
    components:
      - id: mes
        type: kpi
        view: resumen
        metric: ventas_netas
        delta: previous_period
        span: 12
      - id: diaria
        type: line
        view: diaria
        x: fecha
        series: [ventas_netas]
        span: 8
        colors: [series1]
      - id: marcas
        type: bar
        view: marcas
        orientation: horizontal
        stacked: false
        category: marca
        value: ventas_netas
        top_n: 8
        span: 4
      - id: producto
        type: table
        view: producto
        columns: [producto, ventas_netas]
        totals: true
        sort: { by: ventas_netas, dir: desc }
        page_size: 25
        span: 12
        colors: [neutral]
      - id: nota
        type: text
        style: caption
        text: "Cifras provisionales del cierre de mes."
        text_en: "Provisional month-end figures."
        span: 12
```

## Rules the validator enforces

| # | Rule | Severity |
|---|---|---|
| 1 | Every `view` equals the `id` of a declared view of the same report (a view declares its own optional `id`; a layout may only reference a view that has one). Binding is by id — never by array index or by view `type`. | error |
| 2 | Every `metric`/`series[]`/`value`/`columns[]` id exists in the report's `metrics`/`dimensions`. | error |
| 3 | Every `filters.only[]` id is declared in the report's `filters`. | error |
| 4 | `type` is in the catalogue: `kpi`, `line`, `area`, `bar`, `pie`, `donut`, `table`, `text`, `filters`, `spacer`. | error |
| 5 | `id` values are unique inside `components`. | error |
| 6 | `span` is an integer 1–12; `stacked` has two or more `series`; `top_n` is 2–12; `page_size` is 5–200. | error |
| 7 | `colors`/`style` contain only roles and named styles — no hex, `rgb(`, `hsl(`, url. | error |
| 8 | `x` of `line`/`area` is an ordered dimension or a grain. | warning (renderer falls back to `bar`) |
| 9 | `pie`/`donut` `top_n` is at least 40% of the view's category count (the view's `limit`). | warning (renderer still groups "otros") |
| 10 | `text.text` is 1–500 characters. | error |

## Rendering contract (web)

- **Grid**: one column on phones; `span` columns of 12 from the `md` breakpoint. Declared order is
  the DOM order, so the phone layout, the tab order and the screen-reader order are the same.
- **Unknown component**: an error card naming the component id and type (FR-006). Never blank.
- **No `layout.web`**: `ReportViews` renders `data.views` in payload order, exactly as today.
- **Charts**: built on the app's SVG primitives; the current-period series uses the component's first
  colour role (default `series1`), the previous-period series the next one, dashed, as `TrendChart`
  already does.
- **Tables**: `columns` filters and orders the emitted columns; `totals` renders the engine's
  `views[].totals` as a last row; `sort` and `page_size` are client-side over the already-fetched
  rows; horizontal scroll inside the card is unchanged.
- **Accessibility**: each chart gets `role="img"` plus `aria-label` from the engine's
  `views[].summary`; tables keep their real header cells; `text` blocks render semantic headings.
- **Small screens**: KPI items wrap two per row; `spacer` collapses to the `sm` step; charts keep a
  minimum height of 160 px.
