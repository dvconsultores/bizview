# Spec kinds

## What it is for

Each spec has a kind in its `**Type**:` line that says what it produces.

## Who can use it

Only the **Superuser**.

## How to

- **Source**: documents a data source registered in [Open Data sources](app:/admin/fuentes). It
  produces no files; it is met when the source exists and its test passes.
- **Integration**: produces `integrations/<id>/`, a scheduled load from a source into the BI
  database (see Define an integration).
- **Report**: produces `reports/<id>/report.yaml`, a dashboard. It can read integration datasets
  or, in direct mode, an existing table with no ETL (see Direct reports).
- **Distribution**: produces `distributions/<id>.yaml`, scheduled sends of a report by role and its
  link policy (see Distributions).

## Options

- A project can have a single spec: for example, one direct report over a table that already
  exists.
- For a new dashboard with data from an operational system, the usual order is source,
  integration, report and, if needed, distribution.
