# How a dashboard is drawn

## What it is for

Knowing what BizView does with what you wrote, so you do not guess why a figure changes with the
period, why a card is empty or why the dashboard does not match the `report.yaml`. This is the path,
from apply to drawing.

## Who can use it

Anyone who reads the dashboard; the **Superuser** is the one who fixes it.

## How to

1. Apply. On apply, BizView validates the project again and composes it with the others into a
   new version. Each `report.yaml` becomes a dashboard and its `access.roles` decides who may open
   it.
2. Context. The aliases of `uses` resolve to `ds_<integration>.<dataset>` and the column types
   come from the integration contract. No query has run yet.
3. Request. The screen sends the period, the comparison and the filters from the URL. The period
   becomes two inclusive dates in the installation's time zone, not the browser's.
4. Queries. Each view becomes one aggregation per period. The comparison is a second run over the
   previous range, paired by key. `formula` metrics are computed afterwards, and a zero base gives
   null, not an error.
5. Cache. The selection and the last load of the integrations make the key: if nothing changed,
   the answer arrives without recomputing and the screen sees it through the `ETag`.
6. Drawing. With `layout.web` each component binds to a view by its id; without a layout one card
   per view is drawn. Numbers are formatted in the browser, and the PDF uses the same payload.

## Options

- Enlarge opens a card full screen and makes it shareable as `?ampliar=<id>`.
- Auto-refresh asks for the data version and reloads when the integration brings something new.
- A report with `materialize: daily` reads the day's rollup and says so on the card.

## Common problems

- A card says "no data": the period has no rows for that view; the message names the empty
  dataset when none has data.
- A card shows a code and a reference: that view failed and the others did not; the reference
  finds its lines in the server log.
- The dashboard does not match the YAML: validation downgraded part of the layout and the notes
  above the grid say which component and why.
- The figures are old: look at the integration's last run in Data.

## Related

- Define a report
- What happens on import and apply
- Fix the problems
- [Open Projects](app:/proyectos)
