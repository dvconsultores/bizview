# Click to filter

## What it is for

Reading a dashboard by pressing what interests you: a bar, a slice, a ranking row or a table cell.
The whole dashboard — KPIs included — recalculates with that value.

## Who can use it

Anyone who can see the report. Clicking does not change permissions: it only filters the data you
can already see.

## How to

1. Open a report and press a value: a bar, a pie slice, a ranking row or a dimension cell.
2. The dashboard filters. The card you pressed keeps all its values and highlights the chosen one;
   the others show only the filtered data.
3. Press the same value again to remove the filter.
4. Hold Ctrl (or Cmd on a Mac) while pressing another value of the same dimension to add it. A value
   of another dimension adds a second filter.
5. Filters appear as chips under the period line. **Clear** removes them all.

## Options

- The values are kept in the URL, so you can share the link, reload the page or export the PDF/CSV
  with the same filter.
- "Others", totals and trend points are not clickable.
- The **Filters** sheet shows the same values when the dimension is listed there.
- A dashboard can turn clicking off: if a value does not respond, the author configured it without
  interaction.

## Common problems

- The chip is missing: the filter came from the sheet, not from a click; check the Filters sheet.
- The value does not respond: that component may be non-interactive, or the value is "Others"/a
  total.
- The dashboard keeps a total after you click another card: that KPI is configured to ignore click
  filters.

## Related

- View a report
- Filters and periods
