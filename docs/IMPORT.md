# Getting a project into Bizview

Authoring happens outside Bizview ([AUTHORING.md](./AUTHORING.md)). This is the way in: a folder of
declarative files becomes a **project** the product versions, applies and runs.

**Import is the only way in.** There is no button that creates an empty project: a project is
authored with whatever tool you prefer — Claude Code, Codex, DeepSeek, an editor, or by hand — and
arrives as a zip. The CLI validates the folder you are working on and measures it exactly as the
server will, so a project that passes on your machine imports on the server.

## The path

```text
author  →  validate  →  upload  →  map  →  collisions  →  validate again  →  preview  →  apply
```

### 1. Author

Write the project folder with the contract in [AUTHORING.md](./AUTHORING.md): `project.yaml`,
`specs/NNN-<name>/spec.md` with `**Status**: Approved`, and the artifacts each spec owns.

### 2. Validate before you upload

```bash
bizview validate --write-lock      # in the project folder, or in the workspace root
```

`problems.json` lists every problem with its file, JSON path, code and, when it can, the fix. Fix
them here, not in the app: the app will show the same list and refuse nothing else.

### 3. Upload

- **In the app**: **Proyectos → Importar proyecto**, choose the zip of the project folder. Before
  anything is uploaded, the page reads the archive's table of contents and shows both budgets; over
  a budget the import is refused there, naming which. The server re-checks.
- **CLI**: there is no upload command; the app owns the project file tree. `bizview import
  --dry-run <zip|folder>` prints the same two numbers the server would (`--json` for a machine).

```bash
zip -r panorama.zip projects/panorama -x '*.DS_Store'   # what the app expects: one project
```

### 4. Map

The zip's top folder is stripped when it is not a layout folder, so `panorama/`, `projects/panorama/`
and a zip of the files themselves all produce the same project. The project's `name` comes from
`project.yaml`, then from the query parameter, then from the folder name.

### 5. Collisions

| What collides | What happens |
|---|---|
| `slug` already taken | a new unique slug is suggested (`-2`, …) and the project is created with it |
| a file already in the project | impossible on import: an import always creates a new project |
| two spec folders with the same number | the whole import is rejected (422) and nothing is left behind |
| a file outside the layout | it is listed in `ignored`, never written |
| an image over its allowance, or an SVG with a script | rejected (422) with the asset named |
| too many files, or too much size, in one allowance | rejected (422) with that allowance named |
| an executable file anywhere | rejected (422) with `zip_disallowed` and the path |

The response is `{project, ignored, validation}` — `ignored` is what you left in the zip and the
product will never store.

### 6. Validate again

The import validates what it wrote and returns the result. A project that validates can be applied;
one that does not shows its problems in the editor, and **Aplicar** refuses with the same list.

### 7. Preview

**Editor** shows the project's tree, each file and its problems. There is no draft preview in
0.2.0: what you see before applying is the validation result and the files. After **Aplicar**, the
report renders at `/api/reports/<id>` — the same rendering a share link and the PDF use.

### 8. Apply

**Aplicar** composes the project with the other applied projects into a new **version**, checks the
composition again (a duplicate id or a reference into another project is real), and starts the
integration schedule. **Volver a la versión anterior** rolls back. Both are audit events.

## Export

**Exportar** downloads the project as a zip with its specs, artifacts and `assets/` — the same shape
**Importar** accepts. It is the way to take a project to a Git repository, or to move it to another
installation.

## CLI equivalents

| Step | Command |
|---|---|
| Create a workspace (once) | `bizview init workspace --name mycompany` |
| Start a project folder to author | `bizview project new "Panorama cripto"` |
| Describe a source | `bizview describe <source>` |
| Validate | `bizview validate [--write-lock] [--live]` |
| Measure a zip or a folder | `bizview import --dry-run <zip> [--json]` |
| Version | `bizview version` |

`bizview project new` writes a folder to author in — it does not create anything inside Bizview.
`bizview import --dry-run` exits `0` when the project fits, `1` when it does not (printing which
allowance and by how much), and `2` when the input cannot be read.

The CLI never talks to a running Bizview: it reads and writes files and talks to data sources.
Uploading, applying and rolling back are the app's.

## The two budgets

A project is charged to two allowances, counted apart. Before 049 they shared one, so a project that
shipped a logo set was refused with "the project exceeds the limit" — a message about a budget the
author could not act on.

| Allowance | What it pays for | Files | Per file | Total |
|---|---|---|---|---|
| **artifacts** | `project.yaml`, `specs/**`, `integrations/**`, `reports/**`, `themes/**`, `distributions/**` | 400 | 2 MB | 20 MB |
| **assets** | `assets/**` (`.png`, `.jpg`, `.webp`, `.svg`) | 2 000 | 300 KB | 25 MB |

The zip may weigh the sum of both (45 MB). Every refusal names **one** allowance, the folders it
counted and the numbers — never a combined figure.

All six numbers are settings. A super user changes them in **Administración → Proyectos → Límites de
importación** (field left empty = the deployment default, from `PROJECT_MAX_FILES`,
`PROJECT_MAX_KB`, `PROJECT_MAX_MB`, `PROJECT_ASSET_MAX_FILES`, `PROJECT_ASSET_MAX_KB`,
`PROJECT_ASSET_MAX_MB`). The change is audited (`project_limits_changed`).

## Files that are not the project

An authoring pack and the project it builds live in the same folder (043), so a zip often carries
`PROMPT.md`, `REQUEST.md`, `request/`, `sources/`, `.bizview/`, `README.md`, `.DS_Store` or
`__MACOSX/`. Those are listed under **Archivos ignorados** and the import continues — nothing from
them reaches the disk.

Executable content is the exception: a file whose extension is a program (`.js`, `.sh`, `.exe`,
`.py`, `.dll`, …) or whose bytes start like one (`ELF`, `MZ`, `#!`, Mach-O) refuses the whole import
with `zip_disallowed` and the path. Harmless noise is skipped; a program is not noise.

## What an installation needs

- `PROJECTS_DIR` writable by uid 10001 (the containers' user).
- The two budgets large enough for the project (see above).
- The sources the project names, with credentials entered in **Fuentes de datos** — never in the
  project.
