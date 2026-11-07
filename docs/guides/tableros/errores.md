🇬🇧 English · 🇪🇸 [Español](../../es/guides/tableros/errores.md)

# Errors when a dashboard draws

A report can fail **after** validating: the preview that no longer exists, a dataset that
disappeared, a join that cannot be built, a metric that divides by zero, a block the PDF cannot
draw. All of that used to end in "An unexpected error occurred (reference …)", which says nothing
and cannot be acted on. Now every failure has a **code** and **the piece that failed**.

It came from a real incident (2026-10-26, project `coinmarketcap`, version 22 just applied): the
**Preview** section kept offering `panorama-cripto` when the application had already dropped the
preview schemas, so pressing it pointed the query at tables that did not exist.

## Where you see it

- **One card per piece**: the card that cannot be drawn shows the message and, under "Technical
  details", the code, the reference, the report and the identifiers that failed (dataset, column,
  joins and key, metric, view, component, block, reason). The rest of the dashboard keeps drawing,
  and so does the PDF.
- **A state, not a failure**: a period with no data draws "No data" and the details show
  `empty_dataset` with the datasets that have no rows.
- **The log link**: the card carries the command that finds the server line, with the same reference
  that was recorded when the answer was built:
  `docker logs --tail 500 bizview-backend | grep -n "<reference>" -A 60`.

## Codes

| Code | What it means | What to do |
|---|---|---|
| `preview_expired` | The preview no longer exists: the version was applied (its schemas were dropped) or the cleanup ran. | Run the preview again. If you already applied, open the published dashboard (`/r/<id>`): the page stops offering the preview links and says which version replaced it. |
| `dataset_missing` | The dataset is missing (its table, or a column the report uses). | Check the integration: the dataset and the column travel on the card. Run the integration again if the table was lost. |
| `join_failed` | The datasets could not be joined: a join is not declared, two joins repeat the same datasets, or the column is ambiguous. | Declare `joins` between every dataset the report uses, by the column they share (for example `assets.snapshot_at = altseason.snapshot_at`). Validation reports it as `unjoined_sets`. |
| `empty_dataset` | The period has no rows (or the dataset has none at all). | That is not a code error: check the period window and the integration's load. The card says "No data". |
| `metric_error` | The metric could not be computed: division by zero, a value that does not fit the type, or an invalid expression. | Guard the division in the spec (`nullif`/`case`) or fix the column's type. Only that metric fails: the rest of the row and of the dashboard still draws. |
| `format_unknown` | A metric's `format` is not in the catalogue (`number`, `integer`, `currency`, `percent`, `text`). | Change the `format` in `report.yaml`. The card names the metric and the format. |
| `layout_component_unknown` | A `layout.web` component or a `layout.pdf` block uses a type outside the catalogue. | Use a type from the catalogue (026) or remove the component. In the PDF the block is replaced by its card; on the web, by the component's card. |
| `pdf_render` | ReportLab could not draw a PDF block. | The block and its type travel on the card; the rest of the document is generated. The server log has the trace with the same reference. |

## Preview and applied version

- When you **apply** a project, its preview becomes `replaced` with the applied version: the page no
  longer offers the links and shows "Preview replaced by version N" next to the published dashboard.
- If the preview schemas disappeared without applying (the 24 h cleanup), the first read answers
  `preview_expired` and **retires** the preview: the links stop appearing on their own.
- Neither answer is a 500: there is always a code, a message and a reference.

## What is never recorded

A row value never travels, neither on the card nor in the log. The detail is assembled from
identifiers and fixed reasons (`division_by_zero`, `invalid_value`, `numeric_overflow`, `ambiguous`,
`disconnected`, `unjoined`, `repeated`), because PostgreSQL's text may quote the value that broke a
conversion.
