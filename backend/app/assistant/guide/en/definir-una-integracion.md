# Define an integration

## What it is for

It explains what `integrations/<id>/integration.yaml` holds: the file that says which data to
load, from where, how often and how to check it.

## Who can use it

Only the **Superuser**; the agent usually writes it with `/speckit-implement`.

## How to

Main fields:

- `source`: the name of the registered source.
- `schedule`: the frequency (a cron expression, for example every hour).
- `datasets`: one or more datasets; each becomes a table in `ds_<id>`. Per dataset:
  - `extract`: `query: queries/<name>.sql` (a single read-only SELECT filtered with
    `:window_start` and `:window_end`) or `request: requests/<name>.yaml` for REST or SOAP.
  - `columns`: each column with its type.
  - `primary_key`: the columns that identify each row.
  - `incremental`: `window_days` (the last N days) or `mode: full` (everything every time).
  - `checks`: checks such as `row_count`, `not_null` or `reconcile` (PostgreSQL only).
  - `transform` (optional): a SELECT over `input` that runs in Polars before storing.

## Options

- The integration's spec lists in `**Personal data**:` the personal columns included on request.
- For a full example, ask the agent for the authoring guide or download an applied project.
