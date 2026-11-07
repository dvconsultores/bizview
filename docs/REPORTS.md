🇬🇧 English · 🇪🇸 [Español](es/REPORTS.md)

# Report reference — the report and integration contract in depth

**Every integration and every report is a spec, and Bizview runs exactly what the spec says.**
The *workflow* — the five steps, the starter pack, importing — lives in
[AUTHORING.md](./AUTHORING.md) and [IMPORT.md](./IMPORT.md). This page is the reference those two
point at: the fields of an integration, of a report, of a direct report, and the rules the
validator enforces.

If you are starting a project, read AUTHORING.md first; come back here when you need a field.

## 1. Create the workspace (once per customer)

The workspace is a **private Git repository of the customer**, separate from the product.

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
uv tool install "bizview-cli @ git+https://github.com/<owner>/bizview#subdirectory=cli"
bizview init workspace --name acme --path acme-bizview   # v2 workspace: one folder per project
cd acme-bizview && git remote add origin <private repo> && git push -u origin main
bizview init project "Ventas" --source "Origen ventas"    # projects/ventas/, the starter pack
```

Each project starts from the same pack the app downloads (**Proyectos → Nuevo proyecto → Descargar
paquete inicial**): `bizview init project` writes it from a terminal. Work in `projects/<slug>/`
with whatever tool you prefer, and run `bizview validate --write-lock` from the workspace root (it
reports every project). The legacy flat tree below is still accepted (`bizview init <folder> --name
acme --layout legacy`).

```text
acme-bizview/
├── bizview.yaml
├── bizview.lock
└── projects/ventas/
    ├── project.yaml                      name, slug, description, created
    ├── .specify/memory/constitution.md
    ├── specs/001-origen/                 **Tipo**: fuente — the source and its tables
    ├── specs/002-ventas-diarias/         **Tipo**: integracion
    ├── specs/003-ventas/                 **Tipo**: reporte
    ├── specs/004-envio-semanal/          **Tipo**: distribucion
    ├── integrations/<id>/integration.yaml + queries/*.sql | requests/*.yaml
    ├── reports/<id>/report.yaml
    └── distributions/<id>.yaml           scheduled sends to roles, share-link policy
```

`bizview init` installs Spec Kit with the **Bizview preset** (spec/plan/tasks templates for
integrations and reports) and the **Bizview extension** (`/speckit.bizview.validate`,
`/speckit.bizview.describe`, and a mandatory `after_implement` hook that runs `bizview validate`),
plus the workspace constitution and the authoring rules (`CLAUDE.md`, `AGENTS.md`,
`.github/copilot-instructions.md`).

```text
acme-bizview/
├── bizview.yaml                      name, currency (ISO 4217), informative time zone
├── specs/integrations/NNN-<id>/      spec.md plan.md tasks.md
├── specs/reports/NNN-<id>/           spec.md plan.md tasks.md
├── integrations/<id>/integration.yaml + queries/*.sql | requests/*.yaml
├── reports/<id>/report.yaml
└── bizview.lock                      checksums written by `bizview validate --write-lock`
```

## 2. Look at the source — structure only

The super user creates a token in **Administración → Tokens de acceso** (scope `describe`,
shown once). Then, in the workspace:

```bash
export BIZVIEW_URL=https://bi.acme.com BIZVIEW_TOKEN=bzv_…
bizview describe "Origen ERP"            # PostgreSQL: tables, columns, keys, estimated rows
bizview describe "API pedidos" --path /orders   # REST: JSON shape (keys and types, no values)
```

Descriptions never contain row values. Give them to your AI as context for the spec.

Since feature 052 a super user can also do this from the interface — **Fuentes de datos →
«source» → Estructura** — press **Generar estructura con IA** (one internal pass: scan, AI,
verification) and then **Descargar estructura** to get the pack's own
`sources/<name>/structure.md` and `structure.json`. The generated pack is richer than the raw
catalogue: logical tables, field semantics, keys, date fields, relations, personal-data flags and
the notes that say what one row is. In the workspace, `bizview describe "<name>" --pack` writes the
same two files; `?mode=scan` gives the raw reading.

## 3. Write an integration spec

Ask your AI, for example: *"Integración: líneas de venta y devoluciones de la fuente
'Origen ERP', cada 30 minutos, últimos 7 días, recarga completa diaria"*. The spec must state for
each dataset: what one row is, inclusions/exclusions, primary key, date column, incremental
window, columns with types, and quality checks. The implementation is `integration.yaml` plus one
read-only `SELECT` per dataset:

```yaml
id: erp-ventas
spec: specs/integrations/001-erp-ventas
source: Origen ERP                       # name in Administración → Fuentes de datos
schedule: "*/30 * * * *"                 # installation time zone (TIMEZONE)
timezone: America/Caracas                # business dates
datasets:
  sale_lines:
    primary_key: [line_kind, line_id]
    date_column: local_date
    columns:
      line_kind: {type: text, nullable: false, enum: [sale, return]}
      line_id: {type: bigint, nullable: false}
      local_date: {type: date, nullable: false}
      net_amount: {type: numeric, nullable: false}
    extract: {query: queries/sale_lines.sql, params: [window_start, window_end]}
    incremental: {window_days: 7, full_rebuild_cron: "0 3 * * *"}
    checks:
      - {type: row_count, min: 1}
      - {type: reconcile, query: queries/daily_totals.sql, compare: [local_date, net_amount], tolerance: 1.0}
```

Rules enforced by `bizview validate` and again by the installation:

- exactly one `SELECT`/`WITH` per file; no DML/DDL, `COPY`, `SELECT … INTO`, locking, or
  functions that read files, sleep, signal, or change settings; parameters only `:window_start`
  and `:window_end` (bound, never spliced);
- the query must return exactly the contract's columns; types are enforced on load;
- incremental datasets must filter by both window parameters.

A run loads every dataset into a staging table, runs the contract checks (nulls, enums, min/max,
duplicate keys) and the spec's checks (row counts, not-null, **reconciliation** against origin
totals computed independently), and only then replaces the window — all or nothing. A failed
check keeps the previous data and shows the reason in **Administración → Integraciones**.

REST/SOAP sources use `extract: {request: requests/<name>.yaml}` with `method`, `path`,
`params` (`{window_start}`, `{window_start_date}`…), `pagination` (`page`, `offset`, `cursor`,
`link`), `records` (JSON path to the list) and `fields` (column → JSON path).

## 4. Write report specs — many per integration

A report uses datasets of one or more integrations (aliases), declares joins, the date column,
metrics (SQL aggregate expressions or formulas over other metrics), dimensions, views, filters,
access, PDF and the optional AI narrative:

```yaml
id: ventas
spec: specs/reports/001-ventas
title: Ventas
uses: {lines: erp-ventas.sale_lines, products: erp-ventas.products}
joins: [{left: lines.product_id, right: products.product_id, type: left}]
date: lines.local_date
metrics:
  net_sales: {label: Ventas netas, sql: "coalesce(sum(lines.net_amount), 0)", format: currency}
  orders: {label: Pedidos, sql: "count(distinct lines.document_id)", format: integer}
  avg_ticket: {label: Ticket promedio, formula: net_sales / orders, format: currency}
dimensions:
  product: {label: Producto, sql: "coalesce(products.name, 'Sin producto')"}
views:
  - {type: kpis, metrics: [net_sales, orders, avg_ticket]}
  - {type: trend, metric: net_sales, grain: auto}
  - {type: ranking, dimension: product, metric: net_sales, limit: 10}
filters: [product]
ai_narrative: {enabled: true, inputs: [net_sales, orders], instructions: Resume en 3 frases.}
```

Every alias of `uses` has to be reachable from the alias of `date` through `joins`: a report is one
query, so a set nobody joins cannot be read and the dashboard would answer «Conjuntos sin unión».
The validator says so before the report can be applied, with the line to add.

Expressions may use only the declared aliases' columns and allow-listed functions (`sum`,
`count`, `avg`, `min`, `max`, `coalesce`, `case`, `round`, `date_trunc`, …); no sub-queries.
Periods (today … last 12 months, custom), comparisons (previous period, previous year, zero base
→ "Nuevo"), freshness and PDF are provided by the product. The AI narrative receives **only** the
metrics listed in `inputs` — aggregated, never rows.

### Theme per report (optional)

Every installation manages the themes of its reports in **Administración → Apariencia**: the five it
ships (`Impacto`, `Clásico`, `Monocromo`, `Contraste alto`, `Daltónico`), the ones uploaded there and
the ones a project brought. A report may declare its own; it then travels with the workspace version
and applies to the web page and the PDF:

```yaml
layout:
  theme:
    id: contraste        # any theme of the installation, uploaded ones included
    mode: auto           # auto | light | dark
```

The value is a theme id, never a colour: report definitions carry semantic roles only, so the
validators can guarantee contrast and distinguishability in both modes. `palette:` is accepted for
one version as the deprecated alias of `id`, so a report written before themes had ids keeps
applying. `mode: dark` paints the report's own area dark even when the viewer's application is
light — the chrome stays as they chose — and a sun/moon toggle on the report lets the viewer override
it for the session. The PDF always uses the theme's light variant.

`id` must name a theme that exists: the installation's library or one the project brings in
`themes/<id>.yaml`. A report naming a theme nobody has is a validation problem, not a silent
fallback. See [THEMES.md](./THEMES.md) for the theme file itself.

### English labels (optional)

Reports can provide English variants via `_en` keys:

```yaml
title: Ventas
title_en: Sales
metrics:
  net_sales:
    label: Ventas netas
    label_en: Net sales
    sql: "coalesce(sum(lines.net_amount), 0)"
    format: currency
dimensions:
  product:
    label: Producto
    label_en: Product
    sql: "coalesce(products.name, 'Sin producto')"
views:
  - {type: ranking, dimension: product, metric: net_sales, limit: 10, title: Ranking de productos, title_en: Product ranking}
```

Supported keys: `title_en`, `description_en`, `metrics.<id>.label_en`,
`metrics.<id>.description_en`, `dimensions.<id>.label_en`, and `title_en` on ranking and
table views.

- English texts are shown when the interface is in English; if an `_en` variant is missing,
  the Spanish text is shown. Authored content is never machine-translated.
- These labels are also used in PDFs, email subjects and headings, CSV exports, and the
  dashboard catalogue, which is searched in both languages.
- Spec markers are accepted in English as well: `**Personal data**:`
  (= `**Datos personales**:`), `**Mode**: direct` (= `**Modo**: directo`), `**Source**:`,
  `**Tables**:`, `**Maintained by**:`, `**Expected volume**:`.
- Number and date formats follow the language: `es` uses `1.234,56`; `en` uses `1,234.56`.
- The CLI language comes from the global option placed before the command (`bizview --lang en validate`), else `BIZVIEW_LANG`, else `LC_ALL` / `LC_MESSAGES` / `LANG` (first non-empty decides), else Spanish.

### Images (optional)

A project can ship images with its files and use them in a table, in an asset tile or in a KPI.
Declare the sets in the report and name one from the component:

```yaml
images:
  coins:                        # the set's name; components refer to it
    folder: assets/coins        # inside the project
    key: symbol                 # the dimension or column that names the file
    fallback: initial           # initial | none
layout:
  web:
    components:
      - {id: tabla, type: table, view: detalle, image: coins, span: 12}
```

- The file for a row is `assets/coins/<key>` — `BTC` finds `BTC.png`, `btc.png`, `BTC.svg`,
  `BTC.webp` or `BTC.jpg`; case does not matter, and a key with `/` or spaces becomes `_` in the
  file name. You never write a path in the report: the installation resolves it.
- A key with no file draws the circle with the first letter, coloured from the palette (`initial`),
  or nothing at all (`none`).
- Allowed: `.png`, `.jpg`, `.webp`, `.svg` under `assets/`, at most 300 KB each and 25 MB per
  project. A `.png` must really be a PNG, and an SVG is cleaned on import — no scripts, no
  external references.
- The PDF prints the raster files; an SVG-only set prints the circle instead, so add a PNG when the
  report is shared on paper.
- A set fed by a URL column reads the value from the row, so the view that the component uses must
  return that column: declare a dimension with `sql: <alias>.<columna>` and add it to the view's
  dimensions — it is not shown unless the component lists it in its own `columns`. A set that names
  a `column:` and a view that does not project it is a warning (`image_column_not_projected`), and
  every row would show the fallback.
- A `kpi` tile has no row, so its set is keyed by the metric id
  (`images: {coins: {folder: assets/coins, key: total_facturado}}`).
- **Licence**: ship only images you may redistribute. Logos of your own customers' brands, the
  vendor's own artwork or a CC0 set (for example the CC0 cryptocurrency logos) are fine; an image
  copied from a website usually is not, and it travels inside the project when you export it.

### Direct reports ("Reportes directos")

Use a direct report only when the data is already prepared by another process — a tested
BI table, a reporting view maintained by the ERP; otherwise write an integration. The
author follows the same rule. There is no integration, no worker run and no copy; the
report reads the source live on every render.

```yaml
direct:
  source: bi
  tables:
    v:
      table: public.bi_ventas
      columns:
        fecha: { type: date }
        sucursal: { type: text }
        monto: { type: numeric }
        unidades: { type: integer }
  cache_seconds: 300
date: v.fecha
metrics:
  total_vendido: { label: Total vendido, sql: "sum(v.monto)", format: currency }
dimensions:
  sucursal: { label: Sucursal, sql: v.sucursal }
```

Everything else — joins between declared aliases, metrics, dimensions, views, filters,
periods, compare, access, PDF and AI narrative — works unchanged. A report has exactly one
of `uses` or `direct`; `materialize` is refused because the cache is the speed mechanism.
Golden example: the `example-direct` authoring pack (workspace `golden-direct`).

Sources are `bi` — this installation's BI database, allowed by `DIRECT_REPORTS_BI`
(default on) — or a PostgreSQL source of the catalogue with "Permitir reportes directos"
turned on in Administración → Fuentes de datos (default off; password confirmation;
audited). SOAP, REST and Supabase (REST) sources cannot be read directly. The name `bi`
is reserved.

Validation fails for each missing spec line:

```markdown
**Modo**: directo
**Fuente**: bi
**Tablas**: public.bi_ventas
**Mantenido por**: <the process that shapes the data>
**Volumen esperado**: <rows and growth>
```

Add `**Datos personales**: <columns>` when a dimension or filter uses a column flagged
as personal data.

Limits:

| Setting | Range / default | Meaning |
| --- | --- | --- |
| `cache_seconds` | 60–86400, default 300 | results cached per report, selection and time bucket; identical concurrent requests share one query |
| `timeout_seconds` | 1–60, default 15 | statement deadline |
| `max_rows` | 1–5000, default 500 | rows of table views |
| `DIRECT_REPORT_CONCURRENCY` | default 2 | queries at once per source; others wait up to the timeout, then "La fuente está ocupada" |
| `DIRECT_REPORT_WARN_ROWS` | default 5 million (estimated) | tables above this need an index whose first column is the date column (or partitioning by it), otherwise validation says "Tabla grande sin índice por fecha: crea una integración con materialize: daily o indexa <columna>" |

Safety: sessions are read-only and run only SQL the engine generates. Product tables of
the BI database (users, sessions, audit, credentials, sharing,
`alembic_version`, and schemas `pg_catalog`, `information_schema`, `app_test_*`,
`preview_*`) are refused with "Tabla del producto: no se puede leer en un reporte
directo"; `ds_*` dataset tables may be read. Views over product tables are refused too;
see INSTALL §5 for `DIRECT_BI_ROLE`.

Identifiers are lower case only: `table` is `schema.table` matching
`^[a-z_][a-z0-9_]{0,62}\.[a-z_][a-z0-9_]{0,62}$`, aliases and columns match
`^[a-z][a-z0-9_]{0,40}$`. Sources with upper-case or quoted names need a lower-case view
on the source side (e.g.
`CREATE VIEW reporting.ventas AS SELECT "FechaDoc" AS fecha, ... FROM "Ventas"`).

On validate/apply the installation compares every declared table and column with the live
source: missing table, missing column or incompatible type fails. Compatible types:
text ← text/varchar/char/uuid/citext/name; integer ← integer/smallint;
bigint ← bigint/integer/smallint;
numeric ← numeric/integer/bigint/smallint/real/double precision; boolean; date;
timestamptz ← timestamp with/without time zone. Source down at validation is a warning
only. Offline `bizview validate` checks schema, spec lines and reserved names; add
`--describe NAME=FILE` (output of `bizview describe NAME --json`) or `--live` (uses
`BIZVIEW_URL` and `BIZVIEW_TOKEN`) to check structure.

Users see "Datos en vivo · <fuente> · consultado <hora>" in the footer (also in the PDF
and shared view). When the source fails and a cached result up to 24 h exists the report
shows "Datos de <hora>; la fuente no respondió", otherwise a clear error; there is no
tight retry loop (30 s back-off). A dropped column shows "La estructura de la fuente
cambió: falta <columna>" and the workspace screen (`/admin/espacio`) marks the report
"Estructura cambiada" (each report shows its mode Dataset/Directo, source and tables).
Auto-refresh "Al llegar datos nuevos" refreshes once per `cache_seconds`. Every direct
query is logged without values; Administración → Seguridad counts direct reads per source
over 24 h and how many images the image cache has fetched from third parties (count, size,
outcome — never the images).

## 5. Validate, lock, commit — then apply

```bash
bizview validate --write-lock      # also run by the after_implement hook
git add -A && git commit -m "Reporte ventas" && git push
```

On the installation's server: `cd /opt/bizview/workspace && git pull`, then **Administración →
Workspace (`/admin/espacio`) → Validar → Aplicar** (password confirmation). The installation validates
again (plus: sources exist, lock matches the files) and copies the version into its database;
files changed afterwards do nothing until the next apply. **Volver a la versión anterior**
restores the previous version in seconds. Reports appear in the users' home as dashboards;
access follows the usual grants.

Each project is validated and applied on its own page: the problems it shows are its own (another
project's problems are only counted, never offered as a fix), and applying one composes it with the
rest of the workspace — if another project breaks the composition, the apply names it. See
[proyectos/aislamiento.md](./guides/proyectos/aislamiento.md).

When a dashboard cannot be painted (a dataset is gone, a metric divides by zero, a format is outside
the catalogue, a PDF block cannot be drawn) the tile shows a card with its code and the piece that
failed, and the rest of the dashboard still renders; a report whose dataset was never loaded answers
`dataset_missing` instead of an anonymous error. See
[tableros/errores.md](./guides/tableros/errores.md).

A project is applied only when three more things hold, and each says which one is missing in the
status bar under **Pendiente para aplicar**:

- every `queries/*.sql` and `requests/*.yaml` has passed **Volver a comprobar** since its last
  change (the check runs against the source, structure and counts only);
- no dataset column flagged as personal data lacks the spec line `**Datos personales**: <columns>`;
- the report declares at least one filter (`filters: [<dimension>]`).

The first two are reported by `bizview validate` too — the personal column as an error, the missing
filters as a warning — so the author's AI can fix them before the import.

## "No spec, no run"

Nothing runs unless its spec folder has `spec.md`, `plan.md`, `tasks.md`; the spec's
`**Status**` is `Approved` or `Implemented`; `**Spec type**` matches; every task is checked; and
`bizview.lock` matches the files.
