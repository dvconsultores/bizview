# Workspace

## What it is for

The workspace is the set of applied projects: it defines the integrations and reports that run.
Each apply creates a new version and you can always go back to the previous one.

## Who can use it

Only the **Superuser**.

## How to

1. Open [Open Workspace](app:/admin/espacio) (it no longer has a tile in Administration: this
   address is how you reach it).
2. If the installation has a **Mounted folder** (a Git repository), press **Validate** and, if the
   result is **Valid**, **Apply** (your password is asked). The app's projects are applied from
   their own page (see Apply a project).
3. **Active version** shows what runs now and **Previous version**, the one before.
4. Before applying you see the changes: **New**, **Modified** and **Removed**.

## Options

- **Roll back to previous version** restores the previous version in seconds; the current one is
  archived.
- **Specifications** keeps each version's documents, grouped by project: open a spec and switch
  between **Specification**, **Plan** and **Tasks**.
- **Reports** shows each report's mode: **Dataset** or **Direct**.

## Common problems

- A validation error names the file and how to fix it; fix it in the repository or in the project
  and validate again.
