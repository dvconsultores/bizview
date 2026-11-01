# Getting a project into Bizview

Authoring happens outside Bizview ([AUTHORING.md](./AUTHORING.md)). This is the way in: a folder of
declarative files becomes a **project** the product versions, applies and runs.

Two front doors, the same validation: **Proyectos → Importar** in the app, and the CLI for a
workspace you keep in Git. `bizview validate` and the server run the same validator over the same
schemas, so a project that validates on your machine applies on the server.

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

- **In the app**: **Proyectos → Importar**, choose the zip of the project folder (≤ `PROJECT_MAX_MB`,
  20 MB by default), **Importar**.
- **CLI**: there is no upload command; the app owns the project file tree. From a Git workspace,
  **Aplicar** in *Espacio de trabajo* applies the validated workspace instead.

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
| an image over the limit, or an SVG with a script | rejected (422) with the asset named |

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
| Create a project | `bizview project new "Panorama cripto"` |
| Describe a source | `bizview describe <source>` |
| Validate | `bizview validate [--write-lock] [--live]` |
| Version | `bizview version` |

The CLI never talks to a running Bizview: it reads and writes files and talks to data sources.
Uploading, applying and rolling back are the app's.

## What an installation needs

- `PROJECTS_DIR` writable by uid 10001 (the containers' user).
- `PROJECT_MAX_MB` large enough for the project, images included.
- The sources the project names, with credentials entered in **Fuentes de datos** — never in the
  project.
