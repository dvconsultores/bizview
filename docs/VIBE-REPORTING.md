# Vibe reporting — author guide

**Every integration and every report is a spec.** You describe what you need to an AI agent
(Claude Code, GitHub Copilot, Cursor…) in the customer's *workspace*; GitHub Spec Kit turns it
into spec → plan → tasks → declarative files; Bizview runs exactly what the spec says, and nothing
without one.

```text
you: "Reporte de ventas por marca, mes en curso vs mes anterior, con PDF"
 └─ /speckit.specify → spec.md (Status: Draft → Approved)
 └─ /speckit.plan    → plan.md (which files)
 └─ /speckit.tasks   → tasks.md
 └─ /speckit.implement → reports/<id>/report.yaml  (+ `bizview validate` hook, mandatory)
 └─ git commit + push → the installation validates and applies it (Administración)
```

## 1. Create the workspace (once per customer)

The workspace is a **private Git repository of the customer**, separate from the product.

```bash
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git
uv tool install "bizview-cli @ git+https://github.com/<owner>/bizview#subdirectory=cli"
bizview init acme-bizview --name acme              # v2 workspace: one folder per BI project
cd acme-bizview && git remote add origin <private repo> && git push -u origin main
bizview project new "Ventas" --agent claude         # projects/ventas/ with Spec Kit inside
```

Each project is its own Spec Kit folder: open `projects/<slug>/` with your agent, and run
`bizview validate --write-lock` from the workspace root (it reports every project). The legacy
flat tree below is still accepted (`bizview init --layout legacy`).

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
plus the workspace constitution and agent rules (`CLAUDE.md`, `AGENTS.md`,
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

Descriptions never contain row values. Give them to the agent as context for the spec.

## 3. Write an integration spec

Ask the agent, for example: *"Integración: líneas de venta y devoluciones de la fuente
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

Expressions may use only the declared aliases' columns and allow-listed functions (`sum`,
`count`, `avg`, `min`, `max`, `coalesce`, `case`, `round`, `date_trunc`, …); no sub-queries.
Periods (today … last 12 months, custom), comparisons (previous period, previous year, zero base
→ "Nuevo"), freshness and PDF are provided by the product. The AI narrative receives **only** the
metrics listed in `inputs` — aggregated, never rows.

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

### Direct reports ("Reportes directos")

Use a direct report only when the data is already prepared by another process — a tested
BI table, a reporting view maintained by the ERP; otherwise write an integration. The
agent follows the same rule. There is no integration, no worker run and no copy; the
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
the BI database (users, sessions, audit, credentials, assistant, sharing,
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
over 24 h and, under *Bocetos del chat*, how many images the conversations have sent to the AI
provider (count, size, conversations, provider and model — never the images).

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

## The in-app assistant: Spec Kit commands

When AI is enabled, each BI project has a chat (Proyectos → a project, or the Asistente panel)
that follows the same Spec Kit flow as an author in Git, one command at a time. Type `/` in the
composer to pick a command:

| Command | What it changes |
|---|---|
| `/speckit-constitution <principles>` | the project constitution (the installation rules block stays) |
| `/speckit-specify <description>` | a new `specs/NNN-<name>/spec.md` and its quality checklist |
| `/speckit-clarify` | `spec.md` (answers under `## Clarifications`) |
| `/speckit-plan` | `plan.md`, `research.md`, `data-model.md`, `quickstart.md` |
| `/speckit-tasks` | `tasks.md` |
| `/speckit-analyze` | nothing (read-only report) |
| `/speckit-checklist <topic>` | a new or extended `checklists/<topic>.md` |
| `/speckit-implement` | the spec's artifacts, task ticks and `**Status**: Implemented` |
| `/speckit-converge` | appends a convergence phase to `tasks.md` |

In a project the chat lives in the docked panel (the **Asistente** button in the project header,
or the sparkles button in the top bar); on phones and tablets, where the panel has no room, it is
the **Chat** tab of the project. Each conversation belongs to one project.

The server enforces those limits: the agent changes files **only** inside a command and only
the paths above; in a plain message it can look at sources and files and answer, and it offers
an **Insertar** button with the command to run. `/speckit-implement` asks first when the spec is
not `Approved` (your "sí" approves it) or when a checklist has unchecked items. A run that waits
for your answer can be closed with **Terminar**; an interrupted run continues where it stopped
when you run the same command again. Applying the project is always your action (Aplicar).

### Asking for an autonomous run

Say it in the brief and the run stops asking: *"modo autónomo"*, *"sin preguntar"* or
*"decide tú y anota las suposiciones"*. The assistant then picks the most reasonable default,
writes each assumption into the document it is producing, and only stops for something
irreversible or about privacy, credentials or scope. A brief that names the decisions it would
otherwise ask about (for example *"estatus pagada = paid"*) removes those questions entirely.

Two things stay in your hands, by design:

- **Commands do not start each other.** One message runs one command; the **Pipeline** button
  chains `specify → plan → tasks → implement` and asks once before it sends the four messages.
- **A personal column** that you did not explicitly ask for is never included silently: either the
  brief excludes it ("sin columnas personales") or the assistant names it and waits.

The chat only handles reports, integrations, ETL, data sources and the use of BizView. Clearly
off-topic requests get a fixed answer without calling the AI; documents and tool results are
passed to the model as data, never as instructions.

### A mockup as the brief

With a model that reads images, the composer's clip button (📎, its tooltip and accessible name
say *Adjuntar boceto* / *Attach a brief*) takes a picture
(PNG, JPEG, WebP or GIF, up to `ATTACHMENTS_MAX_MB` — 5 MB by default — and
`ATTACHMENTS_MAX_PER_MESSAGE` — 4 — waiting to be sent at a time) so you can say *"un reporte
como este"* and attach the mockup instead of describing its layout in words. The image travels
with that message only; the answer states what it read, and the spec files are written by the
command you are in, as with any other request.

- The images live in `ATTACHMENTS_DIR` (`attachments/` next to the product, never inside a
  project folder): **include that directory in your backups**, and know that it is *outside*
  the project export, the Git mirror and the applied version.
- The first time you send an image the chat shows a notice and waits: images go to the AI
  provider you configured, so use mockups or examples, never screenshots with real customer
  data. The acknowledgement is remembered per account.
- The picture is *data*: the message preceding it is labelled as untrusted input, so nothing
  written inside an image is treated as an instruction.
- The audit log records who uploaded what (session, size, media type, a short hash) and never
  the bytes or the original file name.
- Without a vision model (`AI_VISION=false`, or an OpenAI-compatible endpoint under `auto`) the
  button is disabled and sending images is refused with a clear message; the rest of the chat
  works as usual.

Not sure what to run next? Type `/ayuda` for the command list, examples and the next step of each
spec in the project (answered without calling the AI), or `/ayuda <tema>` — for example
`/ayuda reporte directo` — for one guide topic. The same topics are on the **Ayuda** page
(`/ayuda`); the walkthroughs "Un reporte directo paso a paso" and "De la fuente a la
distribución" follow this guide step by step in the app. You can also ask the chat "explícame este
proyecto" or "¿qué falta?": it reads the project overview (stages, next command, decisions with
file and line).

## "No spec, no run"

Nothing runs unless its spec folder has `spec.md`, `plan.md`, `tasks.md`; the spec's
`**Status**` is `Approved` or `Implemented`; `**Spec type**` matches; every task is checked; and
`bizview.lock` matches the files.
