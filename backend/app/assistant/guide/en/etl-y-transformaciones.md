# ETL and transformations

## What it is for

It explains what BizView does when an integration runs, to understand its timings and errors.

## Who can use it

Only the **Superuser**.

## How to

Each run follows these steps:

1. Extraction: PostgreSQL is read with COPY (fast); REST, SOAP and Supabase with the requests
   defined in `requests/*.yaml`.
2. Window: an incremental load reads only the last days (`window_days`, with `:window_start` and
   `:window_end` in the query); `mode: full` reads everything every time.
3. Transformation (optional): if the integration defines `transform`, data goes through Polars
   (by batches or full) before being stored. `TRANSFORM_MAX_ROWS` limits how many rows it can
   transform at once.
4. Load: data is stored in the `ds_<integration>` schema by its primary key, so repeating a run
   does not duplicate rows.
5. Checks: if a check fails, the load is discarded and the previous data is kept.

## Common problems

- A **Skipped** run found nothing to do or the source was unavailable; check the **History** in
  [Open Integrations](app:/admin/integraciones).
