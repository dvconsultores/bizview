# The five steps

## What it is for

It is the whole path, from a data source to a shared dashboard. There are no shortcuts: the five
steps are the same for a newcomer and for someone with five projects already.

## Who can use it

Only the **Superuser**. Steps 1 and 2 touch credentials; steps 3 to 5, the project. Once the
dashboard is applied, every role in its `access` sees it without doing anything.

## How to

1. Add the source in [Open Data sources](app:/admin/fuentes) and press **Test**.
2. Generate its structure in **Structure**: that is what your AI reads instead of connecting.
3. Download the starter pack in **Projects** → **New project**.
4. Fill in `REQUEST.md` and hand the folder to your AI (or paste `PROMPT.md` into the chat).
5. Import the zip it returns in **Import project** and press **Apply**.

Open [Fuentes de datos](app:/admin/fuentes) · Open [Proyectos](app:/proyectos).

## Options

- No AI is fine too: the files are YAML and SQL, and can be written by hand.
- When the source already has a table prepared by another process, step 1 is skipped and the pack
  asks for a direct report.

## Related

- Download the starter pack
- Hand it to your AI
- Import a project
