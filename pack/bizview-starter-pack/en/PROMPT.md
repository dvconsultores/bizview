# Instructions for your AI — a BizView project

You are the one who writes a BizView project. I will import it into BizView, which validates it,
runs it, turns it into dashboards and shares them. You have no access to the database: only this
document, `REQUEST.md` and, when there is one, `sources/<source>/structure.md`.

## What you must return

**A single `.zip`.** Inside, the project files at the root (no wrapping folder), in exactly this
shape:

```
project.yaml
specs/001-<slug>/spec.md        required
specs/001-<slug>/plan.md        required
specs/001-<slug>/tasks.md       required, every task [X]
integrations/<id>/integration.yaml            when there is an integration
integrations/<id>/queries/*.sql               one read-only statement per file
integrations/<id>/requests/*.yaml             REST/SOAP instead of SQL
reports/<id>/report.yaml                      required
assets/**                                     optional: images (PNG, JPEG, WebP, SVG)
```

`<slug>` is `project.yaml`'s `slug`: lowercase letters, digits and dashes. The spec folder is
`001-<slug>` and each artifact's `id` is its folder name. A report id is a URL: `/r/<id>`. With more
than one spec, number them 002, 003… and point each artifact at its own with `spec: specs/NNN-<slug>`.

## The rules the validator applies (the nine checks)

1. **Schema and layout.** Every YAML follows `.bizview/schemas/`, and folders and file names are the
   ones of the format. No loose files, no invented folders.
2. **Approved spec.** Every artifact has its `spec.md` in its own `specs/NNN-…` folder, with
   `**Tipo**: integracion | reporte` and `**Status**: Approved`. No approved spec, no artifact.
3. **References.** Every `spec:` points at a folder that exists; every metric, dimension, view and
   filter names something declared; every `uses` names a declared integration and dataset.
4. **SQL.** One `SELECT` or `WITH` per file, read-only, no `;` chains, no DDL, no DML. In transforms
   a date is converted with `CAST(strftime(column, '%Y-%m-%d') AS DATE)`. Every column a report uses
   must be declared by the dataset it reads.
5. **Identifiers.** Each artifact `id` is unique in the installation and equals its folder; spec
   numbers are three digits, consecutive, never reused.
6. **Images.** If `images:` names a folder, it exists, is not empty, and its keys match the column; a
   PDF `chart`/`table` block cannot depend on SVG-only images.
7. **Personal data.** If a dataset carries a personal-data column, the integration's `spec.md` lists
   it on a `**Datos personales**: …` line. If there is none, write `**Datos personales**: ninguna`.
8. **Filters.** Every report declares at least one filter in `filters:`. A report without filters is
   not applied.
9. **Budget.** Artifacts: up to 400 files, 2 MB each, 20 MB total. Images: up to 2 000 files, 300 KB
   each, 25 MB total. What is not the project (this document, `REQUEST.md`, `sources/`, `.bizview/`)
   is not imported.

## The artifact contract

`project.yaml` — `name`, `slug`, `description`, `created`.

`integration.yaml` — `id`, `spec`, `source` (the source's name in BizView), `schedule` (cron),
`timezone`, `datasets:` with `primary_key`, `date_column`, `columns:` (`type`, `nullable`,
`description`, `enum` when it applies), `extract:` (`query: queries/x.sql` or
`request: requests/x.yaml`) and `incremental:` (`window_days`, `full_rebuild_cron`, `mode`). A
windowed dataset filters with `:window_start` and `:window_end` and declares both in
`extract.params`. Checks: `row_count`, `not_null`.

`report.yaml` — `id`, `spec`, `title`, `uses:` (alias → `<integration>.<dataset>`), `date`
(`alias.column`), `metrics:` (`sql` or `formula`), `dimensions:`, `periods:`, `compare:`,
`filters:`, `access:` (`roles: [admin, user]`), `views:`, `pdf:`, `layout:` (`web.components` and
`pdf.blocks`).

- A metric uses `sum`, `count`, `count(distinct …)`, `avg`, `min`, `max`, `coalesce`, `round`,
  `date_trunc`, always as `alias.column`. A `formula` only combines metrics that have `sql`.
- Views: `kpis`, `trend`, `ranking`, `table`, `gauge`, `index`, `share`, `asset`.
  **In a ranking, `dimension` and `metric` are singular**, never `dimensions`/`metrics`.
- In the layout, **a `bar` component uses `x` and `series`**; `line` uses `x` and `series`; `kpi`
  uses `metric`; `table` uses `columns`. `span` runs from 1 to 12.
- **Cross-filter (063)**: pressing a bar, slice, row or cell filters the dashboard. It is on by
  default; `interactions: {cross_filter: false}` turns it off. On one component, `cross_filter:
  false` makes it inert and `ignore` keeps it on the company totals. If the display label is not
  unique, declare the dimension as `{label, sql, key}`: filter by `key`, show `sql`.
- A direct report (no integration) declares `direct: {source, tables: {alias: schema.object}}`
  instead of `uses`, plus `date` and, when needed, `joins`. The short form of `tables` only works on
  a BI-ready source.

Business names, not engine names: `comprobante_id`, never `document_id`; `fecha`, never
`created_at` in what the reader sees. Labels in the language `REQUEST.md` asks for.

## How to work

1. Read `REQUEST.md`: the question, who reads it, which filters, which period, which visual style.
2. Read `sources/<source>/structure.md` when it exists: that is the real structure. Do not invent
   tables or columns that are not there.
3. Write `spec.md` first (the why and the datasets), then `plan.md` and `tasks.md`, then the
   artifacts.
4. Before answering, walk the nine checks one by one.
5. Return **one zip** with the files at the root and one sentence saying what it contains.

If you work with the folder open in an editor or a coding agent, write the files there and validate
with `bizview validate`. If we are in a chat, return the zip.

## What not to do

- Do not invent data, not even sample rows, inside the SQL: the project describes the read.
- Do not write credentials, hosts or connection strings.
- Do not leave tasks unticked in `tasks.md`: every one is `[X]`.
- Do not use `**Tipo**: fuente` when no artifact consumes it; use `integracion` or `reporte`.
- Do not add dependencies, scripts or executables: text and YAML only.
