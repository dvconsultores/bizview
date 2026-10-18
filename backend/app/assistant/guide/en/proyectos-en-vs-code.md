# Projects in VS Code and Git

## What it is for

A project can also be worked on outside the app, in VS Code with the same Spec Kit commands, and
brought back or published in a Git repository.

## Who can use it

Only the **Superuser**.

## How to

1. In the project editor press **Download**: the .zip carries the project with its `.specify/`
   folder and the Spec Kit templates.
2. Open it in VS Code and work with your agent's `/speckit-…` commands.
3. Validate from the terminal with `bizview validate`. To read the sources' structure use
   `bizview describe` with a token from [Open Access tokens](app:/admin/tokens).
4. To bring it back, zip it and use **Import project** in [Open Projects](app:/proyectos).

## Options

- Git workspace: a repository with `projects/<slug>/` per project is validated and applied in
  [Open Workspace](app:/admin/espacio). A repository in the older layout is treated as the
  `principal` project.
- `bizview project new` adds a project to a Git workspace.
- `BIZVIEW_LANG` chooses the command line's language.
- A project that comes from Git is read-only in the app: it is changed in the repository.
