# Appearance

## What it is for

It manages the installation's themes: the five the product ships, the ones you upload and the ones a
project brought. A theme decides the colours of every report that does not declare its own:
numerals, chart series, change badges and the PDF.

## Who can use it

Only the **Superuser**.

## How to

1. Open [Open Appearance](app:/admin/apariencia).
2. The library previews every theme in light and dark. The one **in use** carries the ring and cannot
   be applied again.
3. **Use in this installation** makes that theme the one for every report that declares none.
4. **Upload theme** opens the dialog: paste the theme's YAML or choose the file. It is validated
   before it is stored and, if something is wrong, you will see every problem with its path.

## Options

- **From the product**: Impacto, Clásico, Monocromo, Contraste alto and Daltónico. They can be
  neither replaced nor deleted; **Duplicate** opens a copy to edit.
- **Uploaded**: what you uploaded. It can be replaced (with a confirmation) or deleted.
- **From a project**: it arrived with an imported project and leaves with it.
- **Download** returns the file exactly as it was uploaded.
- **Delete** is refused while a report uses the theme, and the message names the reports.

## Common problems

- "A theme with the id already exists": the identifier is taken. Confirm the replacement or change
  the file's `id`.
- "That theme cannot be used": each line names the token and the measurement, for example
  `light.text vs light.surface: 3.9:1 (needs 4.5:1)`. Lighten or darken that colour.
- The brand primary still drives buttons and links; chart series always come from the theme.
- A report may declare its own theme in its definition (`layout.theme.id`); that value wins over the
  installation's.
