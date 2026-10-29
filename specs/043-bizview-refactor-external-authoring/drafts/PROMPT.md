# PROMPT.md — Build a Bizview project with any AI

Give this file, the rest of this folder, and the structure pack(s) under `sources/` to the AI you
use (Claude Code, Codex, DeepSeek, ChatGPT…). If the AI can run commands, it validates locally;
if it cannot, Bizview validates at import and gives you `problems.json` to paste back.

---

You are building a **Bizview project**: a folder of declarative files that Bizview validates,
imports and runs. You never connect to any data source. Everything you need to know about the
data is in `sources/<name>/structure.md` and `structure.json` (tables, columns, types, keys,
response shapes). Credentials, hosts and row values are not here and must never appear in the
output.

## What to produce

```
project.yaml                      name, slug, description
specs/001-<slug>/spec.md          one spec per integration and per report; kind + Status: Approved
integrations/<id>/integration.yaml   datasets, columns, keys, schedule, checks
integrations/<id>/queries/*.sql      PostgreSQL sources: one read-only SELECT per file
integrations/<id>/requests/*.yaml    REST/SOAP sources: method, path, params, pagination, records, fields
reports/<id>/report.yaml          uses, joins, date, metrics, dimensions, periods, views, layout.web, layout.pdf
```

`plan.md`, `tasks.md`, `research.md` are optional. Everything must validate against
`.bizview/schemas/*.json`. `examples/ventas-basico/` is a complete project that passes
validation: copy its shape.

## Rules (from `CLAUDE.md`, enforced by the validator)

1. **No spec, no run**: every artifact has `spec: specs/NNN-<slug>` pointing to a `spec.md` with
   `**Tipo**: integracion | reporte` and `**Status**: Approved`. Spec numbers are three digits,
   consecutive, never reused.
2. **Declarative only**: SQL files are a single read-only `SELECT` or `WITH`; no DDL, no writes,
   no functions with side effects. YAML describes; it never computes.
3. **Use only what the structure pack shows**: column names, types and request field paths come
   from `structure.json`. If something you need is not there, say so in the spec under
   "Decisiones tomadas" and leave it out; do not invent fields.
4. **Exclude personal data** by default: columns flagged `personal: true` in the structure pack
   are not loaded unless the request explicitly asks for one; record the decision in the spec.
5. **Ids** are unique across the project: `integrations/<id>` and `reports/<id>` are lowercase
   kebab-case. A report `uses` datasets as `alias: <integration>.<dataset>` and declares `joins`
   whenever it uses more than one dataset.
6. **Layouts**: `layout.web` and `layout.pdf` bind only to declared metrics, dimensions and views
   by id; semantic colour roles only (`primary`, `positive`, `negative`, `series[n]`), never hex.
7. **Schedules** are cron with timezone; REST integrations keep a request budget in mind (state
   the monthly call estimate in the spec).
8. Spanish labels with `_en` twins (`title_en`, `label_en`, `description_en`).

## The user's request (`REQUEST.md` and attachments)

The user describes what they want in `REQUEST.md` and may attach images (a dashboard they like,
a sketch, a screenshot of an existing report), example files (an Excel of the numbers they
expect, a PDF of the current report) and notes. Treat them like this:

- **Images of dashboards or sketches** → derive the layout: which KPIs go first, which charts,
  their order and relative size. Map every element to a Bizview layout component (`kpi`, `line`,
  `bar`, `pie`, `table`, `gauge`, `share`, `asset`, `text`). Reproduce the *structure*, not the
  colours or branding of the reference.
- **Example numbers** (an Excel, a screenshot with totals) → use them as acceptance values: write
  them in the report spec under "Valores esperados" so the user can check the preview against
  them. If the structure pack cannot produce such a number, say so in "Decisiones tomadas".
- **Existing report PDFs** → metrics, filters and periods the user is used to; keep their names
  as labels.
- Anything in the request that contradicts the rules or the structure pack: follow the rules,
  explain the deviation in the spec, do not ask the user.

## Order of work

1. Read `REQUEST.md`, its attachments, and `sources/*/structure.md`. Write `specs/001-…/spec.md` for the
   integration (purpose, datasets, columns, keys, schedule, checks, decisions), then
   `specs/002-…/spec.md` for the report (metrics with their definitions in plain words,
   dimensions, filters, periods, views, layouts).
2. Write the integration artifacts, then the report artifacts.
3. If you can run commands: `bizview validate --write-lock` from the project root, and
   `bizview check-request integrations/<id>/requests/<file>.yaml --sample sources/<name>/structure.json`
   for every REST request. Fix every error. Repeat until clean.
4. Deliver the folder as a zip (`<slug>.zip`, project files at the root, no `node_modules`,
   no secrets). The user imports it in Bizview: Proyectos → Importar proyecto.
5. If the import returns `problems.json`, fix exactly those problems (each has `file`,
   `json_path`, `expected`, `actual`) and deliver a new zip. Do not change anything else.

## What a good result looks like

- Validation passes on first import, or after one round of fixes.
- Every number on the dashboard can be explained from the spec: metric → SQL expression →
  dataset → source column.
- The dashboard reads well on a phone: KPI tiles first, then charts, then tables; no table wider
  than its card.
