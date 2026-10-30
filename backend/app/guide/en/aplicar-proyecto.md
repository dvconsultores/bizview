# Apply a project

## What it is for

Applying puts the project to work: it creates a new workspace version with this project and the
others already applied, and from then on its integrations run and its dashboards can be seen.

## Who can use it

Only the **Superuser**. The agent never applies: it is always your action.

## How to

1. Wait until the project's status bar says **Ready to apply** (project valid, queries checked and
   a correct preview).
2. Press **Apply project** and then **Confirm**.
3. Type your password in **Confirm your password**.
4. You see "Project applied: version …".

## Options

- If you change files afterwards, the project stays in **Unapplied changes** until you apply it
  again.
- **Delete project** takes the project out of the workspace first (a new version without it) and
  then moves the folder to the bin; it is refused when another project depends on this one.
- To undo an apply use **Roll back to previous version** in
  [Open Workspace](app:/admin/espacio).
- Integration, report and distribution ids are unique across all projects.
- After applying, give access to the new dashboards in each user's page.

## Common problems

- If the button is not active, look at **Pending before applying** in the status bar: it says
  what is missing.
