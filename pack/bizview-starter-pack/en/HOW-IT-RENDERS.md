# What BizView does with your `report.yaml`

When you apply the project, BizView does not turn your YAML into code: it runs it. This document is
**what it does with each file you wrote**, from apply to the dashboard a reader sees. Read it before
deciding periods, comparisons or a `layout`, because every key ends up in a query or in a card.

## 1. Apply: the YAML joins a version

Import stores the zip as a **draft**; **Apply** validates it again with the same validator
`bizview validate` runs, and composes it with the other projects into a new **version** of the
installation. Each `reports/<id>/report.yaml` becomes a dashboard row (`available`), and its
`access.roles` starts deciding who may open it. An active version never changes: that is why
everything downstream can cache against it. **Back to the previous version** undoes it all, grants
included.

## 2. Context: aliases become tables

`uses` are not free names. Each alias resolves to `ds_<integration>.<dataset>` and the column types
come from the integration contract, so a column that does not exist is caught before any SQL is
built. `date` marks the column the range filters on and the base alias of the `joins`. Nothing has
run yet.

## 3. Request: period, comparison, filters

The screen asks for the data with what is in the URL:

```text
period=mtd&compare=previous_period&filter.<dimension>=<value>
```

Only the presets in `periods.allowed` and the comparisons in `compare.allowed` are accepted. The
preset becomes two inclusive dates in the installation's time zone, not the browser's. The
**selection hash** plus the **last successful load** of the integrations make the cache key: if
nothing changed, the answer arrives without recomputing.

## 4. Views become SQL

Each view is **one aggregation per period**: FROM with the aliases and their joins, WHERE with the
date range and the filters, SELECT with each metric's `sql` fragment, and the GROUP BY / ORDER BY /
LIMIT the view type asks for. `formula` metrics are computed afterwards, over the aggregates; a zero
base gives null, not an error.

The comparison is a **second run** over the previous range, paired by key; `previous` and `change`
come from there. With `materialize: daily` the daily rollup is read instead of the dataset — faster
and without touching the source — and the card says which day the figures are from.

A view that fails is **that card only**: the others still draw. An empty view says so instead of
looking broken.

## 5. Render: layout, cards, formats

With `layout.web`, each component binds to a view **by id** (`view`), and `metric`, `x`/`series`,
`category`/`value` choose what it reads. The grid is twelve columns wide and `span` decides how many
a card takes. Without a layout, one card per view is drawn in payload order.

Numbers are formatted in the browser with `format:` and the installation's currency; the PDF applies
the same rules to the same payload, so paper and screen agree.

## 6. Freshness: when the numbers change

| What you see | What happened |
|---|---|
| "Datos actualizados …" | the last successful load of the integrations it reads |
| the page refreshed by itself | auto-refresh found another data version |
| figures from yesterday, labelled | `materialize: daily` read that day's snapshot |
| a stale warning | a direct report could not reach its source |

## What each key controls

| Key | What it decides |
|---|---|
| `date` | the column the range filters on, and the base alias of the joins |
| `periods` | which presets are accepted, and which one opens the report |
| `compare` | whether a second range runs, and which one |
| `filters` | which `filter.<dimension>` are read, and the `IN` list |
| `metrics.sql` / `metrics.formula` | what is aggregated and what is computed afterwards |
| `views.limit` | how many rows a ranking or a table returns |
| `layout.web.span` | how many of the twelve columns a card takes |
| `materialize` | whether the daily rollup or the dataset is read |
| `access` | who may open the dashboard |

## Where to look when it does not draw

- **"No data"**: the range is empty for that view; the message names the empty datasets when none
  has rows.
- **A card with a code and a reference**: that view failed; the reference ties it to the server log.
- **The dashboard does not match the YAML**: validation downgraded part of the layout; the notes
  above the grid say which component and why.
- **The numbers are old**: look at the integration's last run.

The complete version, with the code behind each step, is `docs/RENDERING.md` in the product and in
the app's help (**Create with your AI → How a dashboard is drawn**).

## Related

- `WHAT-BIZVIEW-DOES.md` — what happens on import and apply.
- `CONTENTS.md` — what each file of the zip is.
- `PROMPT.md` — the rules your AI must follow.
