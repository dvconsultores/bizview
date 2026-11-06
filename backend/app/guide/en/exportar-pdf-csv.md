# Export to PDF or CSV

## What it is for

Download a full report as PDF, or one card's data as CSV, with the filters you have applied.

## Who can use it

Anyone with access to the dashboard.

## How to

1. Apply the filters and the period you want (see Parameters and filters of the report).
2. Open **More actions** (⋯) in the report's actions row and choose **Download PDF** or
   **Download CSV**. The line under the menu reminds you that the applied selection is exported.
3. For a single card, open its menu and choose **Download CSV**.

## Options

- The applied selection is exported: unapplied changes do not count.
- The CSV uses a semicolon as separator and opens well in Excel; its format does not change.
- The export to PDF is enabled by the report's `pdf.enabled: true`.
- When the report declares `layout.pdf`, the PDF builds its blocks in the declared order: header
  with the installation's logo, indicators, charts, tables and footer. It uses the page size, the
  orientation and the margins the report declares (in millimetres); the logo comes from the
  installation's branding by its role, never by a path.
- A table that does not fit continues on the next page with its header repeated, or is cut and
  ends with a line such as "and 5 more rows" that says how many rows were left out: the report
  chooses. The footer the layout declares may carry the generation date, the page number and a
  legal line.
- Without `layout.pdf`, the PDF uses the usual template: reports that never declare one do not
  change.
- The PDF shows the same figures as the dashboard for the same filters and period, because both
  are built from the same data.

## Common problems

- "Wait for the report to finish loading.": the downloads appear once the report finished loading.
- "Couldn't generate the PDF.": try again in a moment.

## Related

- View a report
- Filters and periods
- Send by email
