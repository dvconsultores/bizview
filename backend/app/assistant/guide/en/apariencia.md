# Appearance

## What it is for

It chooses the colour palette of every report in the installation: numerals, chart series, change
badges and the PDF.

## Who can use it

Only the **Superuser**.

## How to

1. Open [Open Appearance](app:/admin/apariencia).
2. Each card previews a **Palette** in the light and dark theme. Pick one and press **Save**.
3. From then on every report that does not declare its own palette uses it, on screen and in the
   PDF.

## Options

- **Impact** (default): saturated colours, large numerals and stronger card relief in dark mode.
- **Classic**: the look you know.
- **Monochrome**: eight shades of the brand colour.
- **High contrast**: AA+ for TVs and projectors.
- **Colour-blind safe**: a categorical set safe for colour blindness.

## Common problems

- The brand primary still drives buttons and links; chart series always come from the chosen
  palette.
- A report may declare its own palette in its definition (`layout.theme.palette`); that value wins
  over the installation's and travels with the workspace version.
