🇬🇧 English · 🇪🇸 [Español](es/IMPORT.md)

# Getting a project into Bizview

Authoring happens outside Bizview ([AUTHORING.md](./AUTHORING.md)). This is the way in: a folder of
declarative files becomes a **project** the product versions, applies and runs.

**Import is the only way in.** There is no button that creates an empty project: a project is
authored with whatever tool you prefer — Claude Code, Codex, DeepSeek, an editor, or by hand — and
arrives as a zip. The folder it starts from is the **starter pack**:
**Proyectos → Nuevo proyecto → Descargar paquete inicial** (or
[bizview-starter-template.zip](../bizview-starter-template.zip), or `bizview init project "<name>"`).
The CLI validates the folder you are working on and measures it exactly as the server will, so a
project that passes on your machine imports on the server.

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
| `slug` already taken | it is the **same project**: the zip becomes a new revision of it (see below), never `-2` |
| the same slug, with **Importar como copia** | a copy is created as `<slug>-2`, and its artifact ids are renamed with it |
| a file already in the project | the re-import replaces the draft: what the zip carries is written, what it omits is removed |
| two spec folders with the same number | the whole import is rejected (422) and nothing is left behind |
| a file outside the layout | it is listed in `ignored`, never written |
| an image over its allowance, or an SVG with a script | rejected (422) with the asset named |
| too many files, or too much size, in one allowance | rejected (422) with that allowance named |
| an executable file anywhere | rejected (422) with `zip_disallowed` and the path |

The response is `{project, mode, revision, diff, ignored, validation, budgets}` — `ignored` is what
you left in the zip and the product will never store; `mode` is `created` or `reimported`.

### 5b. The second zip is a revision, not a duplicate

A project is authored outside BizView and corrected there, so the same project arrives again and
again. The `slug` in `project.yaml` is what identifies it — and when the manifest has none, the slug
the project's name derives to. An import whose slug already exists is a **re-import**, never
`<slug>-2`.

- The zip is written over the project's **draft revision** with full-replacement semantics: files
  and images the zip does not carry leave the folder. Nothing is merged.
- The project keeps its id, its slug, its shares, its grants, its dashboards, its audit history and
  the data its integration already loaded.
- A **diff** is shown before anything is written (added / changed / removed files, specs and ids,
  the two allowances). `POST /api/projects/import?dry_run=true` answers it and writes nothing.
- Nothing is applied: the previously applied revision keeps serving the dashboards until you press
  **Aplicar**.
- If you saved files in the editor since the last import, the import asks first
  (`needs_confirmation`); send `replace_draft=true` to accept.
- `copy=true` is the only way to get a second project, and the copy renames its artifact ids
  (`ventas` → `ventas-2`, and its references with them) so it can apply.
- `PROJECT_REVISIONS_KEEP` (default 20) bounds the history; the applied and the previous revision are
  never pruned.

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

An apply also marks the project's **revision**: the draft becomes `aplicada` and the one applied
before it becomes `anterior`. **Volver a la revisión anterior** (in the project page) writes that
previous revision's files as a new revision and applies it — the dashboards go back to that layout —
and the change is audited as `project_reverted`. Each revision can be downloaded as a zip with the
same shape **Exportar** produces.

An image is stored by hash, never by content (044), so a revert can recover text exactly and an image
only while the file is still on disk; the response names the ones it could not bring back.

## What import and apply do, in plain language

*Import* — 1 the zip is read in memory, the top folder stripped, executables and scripts in SVG
rejected; 2 files are mapped to the layout, unknown ones listed as `ignored`; 3 the two allowances are
checked (artifacts 400 files / 20 MB, assets 2 000 / 25 MB); 4 a slug collision becomes a new
revision (055) or a `-2` copy on request; 5 the whole tree is validated with the same validator as the
CLI (schemas, SQL statically, references between files, personal data against the spec, spec
completeness) and problems are shown per file with a fix; 6 the project is saved as a **draft**:
nothing runs, nothing is visible to users yet.

*Apply* — 1 the draft is composed with the other applied projects into a new installation
**version** and checked again (duplicate ids across projects are real errors); 2 each integration is
registered with the worker: the first run is a full load, then the schedule (`cron`) runs the
incremental window (`:window_start`/`:window_end`) or a full reload per `incremental.mode`; 3
datasets land in the warehouse schema `ds_<integration>.<dataset>` with `_run_id` and `_loaded_at`;
4 each report becomes a dashboard at `/r/<id>`, visible to the roles in `access`, with filters,
periods, comparison, PDF/CSV and share links; 5 the apply is an audit event and **Volver a la versión
anterior** rolls everything back; 6 what to look at first: **Integraciones** → last run, **Tableros**
→ the new dashboard, **Proyectos** → problems.

The same text ships inside every starter zip (`QUE-HACE-BIZVIEW.md` / `WHAT-BIZVIEW-DOES.md`) and is
the help topic *Qué pasa al importar y aplicar*.

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
| See what a re-import would change | `bizview import <zip>` (mode + diff against `projects/<slug>/`) |
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
