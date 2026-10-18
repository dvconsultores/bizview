# Direct reports

## What it is for

A direct report reads a table live, with no integration or ETL: from a PostgreSQL source that
allows it or from this installation's BI database (the `bi` source).

## Who can use it

The **Superuser** sets it up. Whoever views the report (any **User** with access) sees that it is
direct by the live data mark.

## How to

1. If the table is in a PostgreSQL source, open the source in
   [Open Data sources](app:/admin/fuentes) and tick **Allow direct reports** (your password is
   asked). The installation's BI database already allows it.
2. Write a `reporte` spec in direct mode and let the agent implement it (see A direct report step
   by step).
3. When viewed, the report reads "Live data · … · viewed …".

## Options

Direct or integration?

- **Direct**: another process already prepares the data (for example a nightly close or a view),
  the table has an index on the date, the volume is moderate and you want to see it right away.
- **Integration**: you need to keep history, load in parts from operational systems, transform or
  join data, or the source is REST, SOAP or Supabase.

Also:

- BizView's internal tables can never be read directly.
- Answers are cached for a few minutes (the report's `cache_seconds`).

## Common problems

- "Data from …; the source didn't respond": the last saved data is shown.
- "The source is busy": too many queries are running; try again.
- If the table's structure changed, the report shows the error and the spec must be updated.
