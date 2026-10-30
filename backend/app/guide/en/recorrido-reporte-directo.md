# A direct report step by step

## What it is for

It creates a dashboard over a table that already exists (for example `bi_ventas`, prepared every
night by another process), with no integration or ETL.

## Who can use it

Only the **Superuser**.

## How to

1. If the table is in a PostgreSQL source, open the source in
   [Open Data sources](app:/admin/fuentes), tick **Allow direct reports** and save (your password
   is asked). If it is in this installation's BI database, use the `bi` source.
2. In [Open Projects](app:/proyectos) press **New project**, name it and press
   **Create project**; its chat opens.
3. Type `/speckit-specify Direct report over the bi_ventas table, no ETL` and add what you want to
   see (metrics, dimensions, period). The agent creates the **Report** spec with the
   `**Modo**: directo`, `**Fuente**:` and `**Tablas**:` lines and asks any missing questions.
4. Run `/speckit-plan` and then `/speckit-tasks`.
5. Run `/speckit-implement`. Answer "yes" if it asks to approve the spec. The agent writes
   `reports/<id>/report.yaml`, checks the query and runs the preview.
6. Review the preview (and its PDF) in the editor.
7. When it says **Ready to apply**, press **Apply project**, **Confirm** and type your password.
8. In [Open Users](app:/admin/usuarios), give **Dashboard access** to whoever should see it.
9. Open the dashboard: it reads "Live data · … · viewed …".

## Common problems

- If the query fails because a column does not exist, the table's structure changed: ask the agent
  to review the spec with `/speckit-clarify` or update the report.
