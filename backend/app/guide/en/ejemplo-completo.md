# A complete example: sales by brand

## What it is for

It is the whole path with a small case: a source with the sales, a dashboard grouped by brand and a
person opening it on a phone. It shows what is written at each step.

## Who can use it

Only the **Superuser**, who walks the five steps. At the end, the role in `access` sees it.

## How to

1. Source: in [Open Data sources](app:/admin/fuentes), a read-only PostgreSQL connection to the sales database.
   Test it and it is registered as `Origen ventas`.
2. Structure: in **Structure**, generate the source's document. It shows the table
   `reporting.ventas` with `fecha`, `marca`, `comprobante_id` and `monto_total`.
3. Pack: in **Projects** → **New project**, name "Ventas por marca", source `Origen ventas`, Spanish,
   first spec "Integración y reporte".
4. Request: `REQUEST.md` says "how much we sell per brand this month, for the sales manager, on a
   phone, with a brand filter and a 7-day default period".
5. Your AI: hand it `PROMPT.md`, `REQUEST.md` and `structure.md`; it returns a zip with
   `project.yaml`, `specs/001-ventas-por-marca`, `specs/002-ventas-por-marca-reporte`,
   `integrations/ventas-por-marca` and `reports/ventas-por-marca`.
6. Import: **Import project** with that zip. No problems: the project stays a draft.
7. Apply: **Apply project**. The integration runs once and the dashboard appears at
   `/r/ventas-por-marca`.
8. Share: open the dashboard and share a link, or schedule an email to a role.

Open [Proyectos](app:/proyectos) · Open [Fuentes de datos](app:/admin/fuentes).

## Options

- The same story with a direct report: when `reporting.v_ventas_dia` already exists and the source
  allows direct reports, step 3 chooses "Reporte directo" and there is no integration.
- It can all be repeated with the CLI: `bizview init project "Ventas por marca" --source "Origen
  ventas"` and `bizview validate`.

## Common problems

- When the dashboard shows zeros, look at the last run in **Integrations**: the query may filter by
  a date the data does not have.
- When the import lists ignored files, they are the pack's (`PROMPT.md`, `sources/`), not the
  project's.

## Related

- The five steps
- Import a project
- What happens on import and apply
