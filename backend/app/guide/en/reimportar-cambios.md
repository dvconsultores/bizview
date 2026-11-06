# Re-import changes

## What it is for

When your AI returns a second version of the same project, you import it again and it becomes a new
revision: the project is the same, with its history and its dashboards.

## Who can use it

Only the **Superuser**.

## How to

1. Ask your AI for the specific change, on the same pack.
2. Open [Proyectos](app:/proyectos) and press **Import project**.
3. Choose the zip. Bizview recognises the identifier and warns that it is a revision of the project
   that already exists.
4. Review the summary: how many files are added, changed or removed, and which identifiers move.
5. Import. The project stays a draft with those changes.
6. Press **Apply project** when it is ready.

If you prefer a separate project, tick the copy box: it is created under another identifier with new
artifact identifiers.

## Options

- Everything stays in the history: one revision can be compared with another and sent back.
- When the draft holds editor changes, Bizview asks for confirmation before replacing it.
- It works without the CLI too: import validates the same way.

## Common problems

- A zip with another identifier creates a new project instead of a revision: check `project.yaml`.
- A change that renames a report changes its `/r/<id>` URL; links you already shared stop working.

## Related

- Re-import a project
- Project history
- Fix the problems
