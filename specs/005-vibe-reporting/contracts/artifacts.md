# Artifact Contract — `integration.yaml`, `report.yaml`, `bizview.lock`

JSON Schemas for these files ship in `cli/bizview_cli/schemas/` and are shared by `bizview
validate` and the backend. Ids: `^[a-z][a-z0-9-]{1,49}$`. Every artifact names its spec folder;
without a complete, approved spec it is refused (FR-001, FR-002).

## integration.yaml

```yaml
id: erp-ventas
spec: specs/integrations/001-erp-ventas     # Spec Kit feature folder
source: Origen ERP                           # data-source catalogue name (feature 004)
schedule: "*/30 * * * *"                                  # cron, installation time zone
time_limit_minutes: 20
timezone: America/Caracas                                 # for local dates in datasets
datasets:
  sale_lines:
    description: Completed sale and return lines
    primary_key: [document_id, line_no, line_kind]
    date_column: local_date                               # drives windows and report periods
    columns:
      document_id:  {type: text, nullable: false, description: Sale document id}
      line_no:      {type: integer, nullable: false}
      line_kind:    {type: text, nullable: false, enum: [sale, return]}
      completed_at: {type: timestamptz, nullable: false}
      local_date:   {type: date, nullable: false}
      product_code: {type: text, nullable: false}
      quantity:     {type: numeric, nullable: false, min: 0}
      net_amount:   {type: numeric, nullable: false}
    extract:
      query: queries/sale_lines.sql                        # PostgreSQL: one read-only SELECT
      params: [window_start, window_end]                   # provided by the engine
    incremental:
      window_days: 7                                       # re-read last N days each run
      full_rebuild_cron: "0 3 * * *"
      slice: month                                         # full rebuild in monthly slices
    checks:
      - {type: row_count, min: 0}
      - {type: not_null, columns: [document_id, product_code]}
      - {type: reconcile, query: queries/daily_totals.sql, compare: [local_date, net_amount], tolerance: 0.01}
  products:
    primary_key: [product_code]
    columns:
      product_code:  {type: text, nullable: false}
      name:          {type: text, nullable: false}
      category_name: {type: text, nullable: true}
    extract: {query: queries/products.sql}
    incremental: {mode: full}                              # small dimension: replace all
```

REST/SOAP extraction instead of `query`:

```yaml
    extract:
      request: requests/orders.yaml     # method, path, params (with {window_start}/{window_end}),
                                        # pagination {type: page|cursor|link, ...},
                                        # records: JSONPath to the row list, fields: column → JSONPath
```

Column types: `text`, `integer`, `bigint`, `numeric`, `boolean`, `date`, `timestamptz`.

## report.yaml

```yaml
id: ventas
spec: specs/reports/001-ventas
title: Ventas
description: Resumen, tendencias y productos de tus ventas.
icon: chart-line
uses:                                   # one or more integrations' datasets
  lines: erp-ventas.sale_lines
  products: erp-ventas.products
joins:
  - {left: lines.product_code, right: products.product_code, type: left}
date: lines.local_date
materialize: daily                      # optional pre-aggregation for speed
metrics:
  net_sales:   {label: Ventas netas, sql: "sum(case when lines.line_kind='sale' then lines.net_amount else -lines.net_amount end)", format: currency, better: higher}
  orders:      {label: Pedidos, sql: "count(distinct case when lines.line_kind='sale' then lines.document_id end)", format: integer, better: higher}
  units:       {label: Unidades, sql: "sum(case when lines.line_kind='sale' then lines.quantity else -lines.quantity end)", format: number, better: higher}
  avg_ticket:  {label: Ticket promedio, formula: net_sales / orders, format: currency, better: higher}
dimensions:
  category: {label: Categoría, sql: "coalesce(products.category_name, 'Sin categoría')"}
  product:  {label: Producto, sql: products.name}
periods: {default: mtd, allowed: [today, yesterday, last_7_days, mtd, last_month, qtd, ytd, last_12_months, custom]}
compare: {default: previous_period, allowed: [previous_period, previous_year]}
views:
  - {type: kpis, metrics: [net_sales, orders, units, avg_ticket]}
  - {type: trend, metric: net_sales, grain: auto}
  - {type: ranking, dimension: product, metric: net_sales, limit: 10}
  - {type: ranking, dimension: category, metric: net_sales, limit: 10}
filters: [category]
access: {roles: [admin], grants: true}  # admins always; users by grant (feature 002)
pdf: {enabled: true}
ai_narrative:                           # optional; only these aggregates reach the AI (FR-003)
  enabled: true
  inputs: [net_sales, orders, avg_ticket]
  with_comparison: true
  instructions: Resume en 3 frases qué cambió respecto al período anterior y por qué podría ser.
```

Formulas (`formula:`) combine other metrics; division by zero → null. Metric SQL may reference only
the aliases declared in `uses`.

## bizview.lock

```yaml
generated_by: bizview-cli 0.1.0
generated_at: 2026-09-29T20:10:00Z
workspace: cliente-b
entries:
  integrations/erp-ventas:
    spec: {folder: specs/integrations/001-erp-ventas, status: Implemented,
           sha256: {spec.md: …, plan.md: …, tasks.md: …}}
    artifacts: {integration.yaml: …, queries/sale_lines.sql: …, queries/products.sql: …}
  reports/ventas:
    spec: {folder: specs/reports/001-ventas, status: Implemented, sha256: {…}}
    artifacts: {report.yaml: …}
```
