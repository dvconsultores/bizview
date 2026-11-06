# Projects

## What it is for

A BI project is a folder with its specs, integrations, reports and distributions. It is authored
outside Bizview with whatever tool you prefer; here you import it, download it and see its status.

## Who can use it

Only the **Superuser**.

## How to

1. Open [Open Projects](app:/proyectos).
2. Press **Import project** and choose the .zip (you are asked to confirm your password). Bizview
   reads what the zip carries before uploading it and shows both limits: artifacts (the project's
   own files) and images (the ones in `assets/`). If one is over, it is not uploaded and the reason
   names which.
3. The project is created with what the zip brought and its editor opens. There is no button to
   create an empty project: a project always enters by import.

## Options

- Each project shows its specs and its status: **Draft** (never applied),
  **Applied**, **Unapplied changes** or **Withdrawn**.
- **Download** gets the project as a .zip.
- **Delete project** (only when not applied) moves it to the trash for 30 days.
- After upgrading BizView, what was already applied appears as the `principal` project.
- The **Identifier** cannot change after the project is applied.
- Type in **Search projects** to filter the list by name, identifier or description (case and
  accents are ignored); the counter says how many match.

## Related

- Import a project
- Project editor
- Apply a project
- Project structure
