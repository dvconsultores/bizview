# Authoring a Bizview project

Bizview runs what you write; it does not write it. This document is the whole contract: the folder,
the request, the schemas, the rules, the validation step, and one complete example at the end.

You can follow it by hand, or hand the pack to any AI — the pack's `PROMPT.md` says the same rules
in the form an agent needs.

## 1. The eight steps

| # | Step | Command or screen |
|---|---|---|
| 1 | Add the source | **Fuentes de datos → Nueva**, then **Probar** |
| 2 | Describe it | `bizview describe <source>` or **Fuentes de datos → Estructura → Descargar** |
| 3 | Create the workspace | `bizview init workspace --name mycompany` |
| 4 | Write the request | edit `REQUEST.md` |
| 5 | Build the project | `bizview project new "<name>"`, then write the files |
| 6 | Validate | `bizview validate --write-lock` |
| 7 | Import | **Proyectos → Importar** (zip) |
| 8 | Apply and share | **Aplicar**, then **Compartir** / **Enviar por correo** |

`bizview describe` prints structure only — table names, column names, types, row counts. It never
returns rows, and no credential ever appears in its output.

Feature 052: the same content is on the source page — **Fuentes de datos → «source» → Estructura**
— with **Descargar estructura (.md)** and **(.json)**, or from the terminal:

```bash
bizview describe "Origen ERP" --pack --out .   # writes sources/<name>/structure.md + structure.json
```

The two files are the pack's: `structure.md` follows the template in
`pack/bizview-starter-pack/bizview-starter/sources/<nombre>/structure.md`, and `structure.json`
carries the same content with a `pack` header. Your notes in **Observaciones** and the personal-data
flags travel in both.

## 2. The folder

```text
mycompany/                          the workspace, one per organisation
├── bizview.yaml                    manifest: the name
├── bizview.lock                    written by `bizview validate --write-lock`
├── REQUEST.md                      what you want, for whom, with which filters
└── projects/<slug>/                one BI project per folder
    ├── project.yaml                name, slug, description
    ├── specs/NNN-<name>/           spec.md (+ plan.md, tasks.md, checklists/)
    ├── integrations/<id>/          integration.yaml + queries/*.sql | requests/*.yaml
    ├── reports/<id>/               report.yaml
    ├── distributions/<id>.yaml     scheduled sends (recipients by role only)
    └── assets/                     images a report shows (PNG/JPEG/WebP/SVG)
```

A **project** is what Bizview imports, applies and versions. Its `slug` is lowercase letters,
digits and hyphens.

## 3. The request

`REQUEST.md` is for you and your AI; the product never reads it. One page:

```md
# Panorama cripto

## Question
What does the crypto market look like in the last snapshot, and how did it move in the window?

## Reader
The trader on a phone, first thing in the morning.

## Decisions
- Ranking by market cap, top 10.
- Fear & greed and altseason index as two KPI tiles.
- Money in USD.

## Out of scope
- Historical prices beyond the window.
- Personal data: none of these sources has any.
```

## 4. The specification

Every project folder carries **lite specs**. `spec.md` is the only mandatory file:

```md
# Mercado cripto

**Tipo**: integracion
**Status**: Approved

Carga cada 30 minutos la última captura del mercado: capitalización, volumen, dominancia,
miedo/codicia y el índice de altseason.

**Fuente**: CoinMarketCap
**Tablas**: assets, global_metrics, fear_greed, altcoin_season
```

- The kind line is `**Tipo**: fuente | integracion | reporte | distribucion` (`**Type**: source |
  integration | report | distribution` is accepted too).
- `**Status**: Approved` is what allows artifacts to exist: no approved spec, no artifact.
- `plan.md`, `tasks.md`, `research.md`, `data-model.md`, `quickstart.md` and `checklists/*.md` are
  optional for an imported project. Use them when the work is big enough to plan.
- Numbers are three digits per project, consecutive, never reused.

## 5. The artifacts

### Integration — `integrations/<id>/integration.yaml`

```yaml
id: mercado-cripto               # unique across the whole workspace
spec: specs/001-mercado-cripto   # the spec that owns it, inside this project
source: CoinMarketCap            # the source's name in Bizview
schedule: "*/30 * * * *"         # cron, in the installation's timezone unless `timezone:` says
datasets:
  assets:
    primary_key: [snapshot_at, symbol]
    date_column: snapshot_at
    columns:
      snapshot_at: {type: timestamptz, nullable: false}
      symbol: {type: text, nullable: false}
      price: {type: numeric}
    extract: {query: queries/assets.sql}
    incremental: {mode: full}
```

- One read-only statement per file in `queries/` (a single `SELECT` or `WITH`, no `;` chains).
- `incremental.mode: full` replaces the window; `incremental.mode: window` keeps what is there and
  adds.
- A REST/SOAP source uses `requests/*.yaml` instead of SQL.
- Never a credential and never a row of real data in the repository.

### Report — `reports/<id>/report.yaml`

```yaml
id: panorama-cripto
spec: specs/002-panorama-cripto
title: Panorama cripto
uses:
  assets: mercado-cripto.assets
date: assets.snapshot_at
metrics:
  market_cap: {label: Capitalización, format: currency, better: higher, sql: sum(assets.market_cap)}
dimensions:
  symbol: {label: Moneda, sql: assets.symbol}
views:
  - {id: kpis, type: kpis, metrics: [market_cap]}
  - {id: tabla, type: table, dimensions: [symbol], metrics: [market_cap], limit: 10}
```

- `uses` maps a local alias to `<integration-id>.<dataset>`; `sql` reads it as `alias.column`.
- A metric may be `sql` or a `formula` over other metrics.
- `views` are what the reader sees: `kpis`, `trend`, `ranking`, `table`, `gauge`, `index`, `share`,
  `asset`.
- A report over an existing table without ETL declares `direct:` instead of `uses:` (see
  [VIBE-REPORTING.md](./VIBE-REPORTING.md) for the direct-source contract). When the source is
  **BI-ready** (the super user declared what it exposes) a table needs no column list: write
  `alias: schema.object` and the columns come from the source's own structure, exactly what the
  structure pack shows you.

  ```yaml
  direct:
    source: Almacén ventas
    tables:
      v: reporting.v_ventas_dia     # columns read from the source
      p: reporting.dim_producto
  joins:
    - {left: v.producto_id, right: p.id}
  date: v.fecha
  materialize: none               # none | daily (daily: the figure is stored once a day)
  ```

  The declaration is the whole truth: an object outside it is refused when you validate, and again
  when the report renders. Choose an integration instead when the origin is transactional, when you
  need history, cross-source joins or heavy transformation — a BI-ready source is for data another
  process already shaped.

### Distribution — `distributions/<id>.yaml`

```yaml
id: envio-semanal
spec: specs/003-envio-semanal
report: panorama-cripto
subscriptions:
  - frequency: weekly
    weekday: 1
    hour: 7
    period: mtd
    recipients: {roles: [admin]}
    attach_pdf: true
    link_days: 7
```

Recipients are **roles**, never addresses.

### Images — `assets/`

A report shows pictures two ways:

```yaml
images:
  coins: {folder: assets/coins, key: symbol, fallback: initial}
  logos: {column: assets.logo_url, key: symbol, fallback: initial}
```

- `folder:` reads the file named after the row's key inside the project (`BTC.png`, `btc.jpg`,
  `BTC.webp`, `BTC.svg`), ≤ 300 KB each and ≤ 25 MB per project, and travels in the export.
- `column:` names a column whose value is a URL: the worker downloads it once, keeps it in the
  installation's image cache (90 days by default) and rewrites the value, so the reader's phone
  never calls the third party.
- Without a file, or with `fallback: none`, the tile draws the initial and a palette colour.

## 6. Validate

```bash
bizview validate --write-lock
```

The same validator the server runs, over the same JSON Schemas in `cli/bizview_cli/schemas/` — that
is why a project that validates here applies there. It checks:

- the YAML against its schema, and the folders against the layout;
- that every artifact has an approved spec in its own project;
- that every `spec:` points at a folder that exists, and every reference resolves;
- that SQL is a single read-only statement, and every column a report uses is declared by the
  dataset it reads;
- unique ids across the workspace, spec numbers, image folders and their keys;
- the `images:` sets exist, are not empty, and are not SVG-only when a PDF block draws them.

`--write-lock` writes `bizview.lock` with a hash per file, so an apply can prove nothing changed
after validation. A failure is written to `problems.json`:

```json
[{"file": "projects/panorama/reports/panorama-cripto/report.yaml",
  "path": "/metrics/market_cap/sql",
  "code": "unknown_column",
  "message": "assets.market_cap no existe en el dataset assets",
  "fix": "usa una de: price, volume_24h"}]
```

`--live` also runs each query against the source (structure and counts only) when the installation
lets the CLI reach it.

## 7. Import and apply

**Proyectos → Importar** takes the zip of the project folder. It maps what it finds, reports
collisions, validates again and shows the tree before anything is applied. **Aplicar** creates a
version composed with the other applied projects and starts the schedule. Nothing runs before that.

The details, including the CLI equivalents and the collision rules: [IMPORT.md](./IMPORT.md).

## 8. A worked example

The pieces below are the `coinmarketcap` project: one integration with four datasets joined on
`snapshot_at`, and a report that shows a KPI row, a trend, a ranking and a table.

`specs/001-mercado-cripto/spec.md`

```md
# Mercado cripto

**Tipo**: integracion
**Status**: Approved
**Fuente**: CoinMarketCap
**Tablas**: assets, global_metrics, fear_greed, altcoin_season
```

`integrations/mercado-cripto/queries/assets.sql`

```sql
SELECT captured_at AS snapshot_at, symbol, price_usd AS price,
       market_cap_usd AS market_cap, volume_24h_usd AS volume_24h
FROM public.crypto_assets
```

`integrations/mercado-cripto/integration.yaml` — the dataset from §5 with four entries: `assets`,
`global_metrics`, `fear_greed`, `altcoin_season`, each with its `primary_key`, its `columns` and its
`extract.query`.

`reports/panorama-cripto/report.yaml`

```yaml
id: panorama-cripto
spec: specs/002-panorama-cripto
title: Panorama cripto
description: Mercado de criptomonedas en la última captura
uses:
  assets: mercado-cripto.assets
  global_metrics: mercado-cripto.global_metrics
  fear_greed: mercado-cripto.fear_greed
  altseason: mercado-cripto.altcoin_season
joins:
  - {left: assets.snapshot_at, right: global_metrics.snapshot_at, type: left}
  - {left: global_metrics.snapshot_at, right: fear_greed.snapshot_at, type: left}
  - {left: fear_greed.snapshot_at, right: altseason.snapshot_at, type: left}
date: assets.snapshot_at
metrics:
  market_cap: {label: Capitalización, format: currency, sql: sum(assets.market_cap)}
  dominance: {label: Dominio de la cartera, format: percent,
              formula: market_cap / total_market_cap * 100}
  altseason_index: {label: Índice altseason, format: integer, sql: max(altseason.value)}
dimensions:
  symbol: {label: Moneda, sql: assets.symbol}
periods: {default: last_7_days, allowed: [last_7_days, last_30_days, mtd, ytd]}
views:
  - {id: kpis, type: kpis, metrics: [market_cap, dominance, altseason_index]}
  - {id: tendencia, type: trend, dimensions: [snapshot_at], metrics: [market_cap]}
  - {id: ranking, type: ranking, dimensions: [symbol], metrics: [market_cap], limit: 10}
  - {id: tabla, type: table, dimensions: [symbol], metrics: [market_cap, volume], limit: 50}
```

Then:

```bash
bizview validate --write-lock     # problems.json empty
```

and **Proyectos → Importar** with the zip, **Aplicar**, **Compartir**.

The product's own test suite keeps this project as a fixture
(`backend/tests/fixtures/projects/coinmarketcap/`), so the example is not illustrative: it is
rendered on every run.
