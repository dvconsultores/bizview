# Import a project

## What it is for

A project enters Bizview one way only: it is authored outside (with Claude Code, Codex, DeepSeek, an
editor, or by hand) and imported as a `.zip`. There is no button that creates an empty project.

## Who can use it

Only the **Superuser**, and your password is asked to confirm.

## How to

1. Prepare the project folder with its `project.yaml`, specs and reports, and compress it:
   `zip -r project.zip project/`.
2. Open [Open Projects](app:/proyectos) and press **Import project**.
3. Choose the `.zip`. Before uploading it, Bizview reads its contents and shows **Artifacts** and
   **Images** with what they carry and their limit. If one is over, **Import now** is disabled and
   the notice says which one and why.
4. Type your password and the project is created with what the zip brought; its editor opens.

The two limits are counted apart, so a logo set does not spend the room the specs need:

| Limit | What it counts | Files | Per file | Total |
|---|---|---|---|---|
| Artifacts | `project.yaml`, `specs/`, `integrations/`, `reports/`, `themes/`, `distributions/` | 400 | 2 MB | 20 MB |
| Images | `assets/` | 2 000 | 300 KB | 25 MB |

The zip may weigh the sum of both (45 MB). A refusal always names one limit, its folders and its
numbers.

## Options

- **Ignored files (outside the project format)**: what is not part of the project (`PROMPT.md`, `REQUEST.md`, `request/`,
  `sources/`, `.bizview/`, `README.md`, `.DS_Store`) is not stored and is listed at the end. The
  project imports anyway.
- A file that looks like a program (`.js`, `.sh`, `.exe`…) cancels the import and is named: that is
  not noise.
- **Import limits**: at the foot of the Projects card, the super user may change them. An empty field
  means the installation's default. The change is audited.
- If a limit was too tight and the installation's was raised, choose the zip again: the reading uses
  the limits in force.
- `bizview validate` and `bizview import --dry-run project.zip` print the same numbers from your
  machine, without uploading anything.
