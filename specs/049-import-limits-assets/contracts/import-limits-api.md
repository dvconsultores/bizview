# Contract — import limits API

All routes require a super user (the whole Projects area does), and a recent re-authentication for the
ones that change something. Every response is JSON; errors use the product's standard body
`{"error": {"code", "message", "key", "params"}}`.

---

## `GET /api/projects/limits`

The effective allowances — the DB row already resolved over the deployment defaults, so the browser
never has to know what a NULL means.

```json
{
  "artifacts": {"name": "artifacts", "max_files": 400, "max_kb": 2048, "max_mb": 20,
                "label": "project.yaml, specs/, integrations/, reports/, themes/, distributions/"},
  "assets":    {"name": "assets", "max_files": 2000, "max_kb": 300, "max_mb": 25,
                "label": "assets/"},
  "zip_max_mb": 45,
  "stored": {"artifact_max_files": null, "artifact_max_kb": null, "artifact_max_mb": null,
             "asset_max_files": null, "asset_max_kb": null, "asset_max_mb": null}
}
```

- `zip_max_mb` is the sum of both totals, so the client does not add them.
- `stored` is the raw row: `null` where the installation inherits. The editor uses it to show
  "predeterminado (400)" next to an empty field.

Errors: `401` not signed in, `403` not a super user.

---

## `PUT /api/projects/limits`

Whole-row replacement. A field sent as `null` clears the override and restores the inherited value.

```json
{"artifact_max_files": 600, "artifact_max_kb": null, "artifact_max_mb": 40,
 "asset_max_files": 3000, "asset_max_kb": null, "asset_max_mb": null}
```

- Body validation mirrors the table: each value `>= 1`; `*_max_kb <= *_max_mb * 1024`.
- `200` with the same shape as `GET`.
- `422` with `fields` naming the offending field (`{"asset_max_kb": "greater_than_total"}`).
- `403` without a recent re-authentication (`reauth_required`), like every other settings write.
- Audits `project_limits_changed` with `{before, after}`.

---

## `POST /api/projects/import` — unchanged, plus the budgets

Request: raw `application/zip` body, query `name`, `slug`, `themes` (`skip|replace|rename`).

`201` body gains one key:

```json
{
  "project": {…},
  "ignored": ["PROMPT.md", "REQUEST.md", "README.md", "sources/ventas/structure.md"],
  "themes": [],
  "validation": {"valid": true, "errors": [], "warnings": []},
  "budgets": {"artifacts": {"files": 41, "bytes": 51234},
              "assets":    {"files": 483, "bytes": 1887436}}
}
```

Refusals — each names **one** budget (FR-003), never a combined figure:

| Status | `code` | Message (Spanish; English in `en.py`) |
|---|---|---|
| 413 | `too_large` | `el zip supera el límite (45 MB)` |
| 422 | `artifacts_over_files` | `El proyecto supera el límite de artefactos: 401 archivos (máximo 400), contados en project.yaml, specs/, integrations/, reports/, themes/, distributions/` |
| 422 | `artifacts_over_bytes` | `El proyecto supera el límite de artefactos: 24 MB en project.yaml, specs/, integrations/, reports/ (máximo 20 MB)` |
| 422 | `artifacts_file_too_large` | `specs/001-ventas/plan.md ocupa 3 MB; el máximo por archivo es 2 MB` |
| 422 | `assets_over_files` | `El proyecto supera el límite de imágenes: 2 150 archivos en assets/ (máximo 2 000)` |
| 422 | `assets_over_bytes` | `El proyecto supera el límite de imágenes: 26 MB en assets/ (máximo 25 MB)` |
| 422 | `assets_file_too_large` | `assets/coins/BTC.png ocupa 420 KB; el máximo por imagen es 300 KB` |
| 422 | `zip_disallowed` | `El zip contiene un archivo que BizView no importa: build/pack.js` |
| 422 | `zip_invalid` | format / path / symlink / ratio / entries — unchanged |

The existing `project_too_large` code and its message are **retired**: a refusal that names "the
project" without saying which allowance was exceeded is the defect this contract removes.

---

## `POST /api/projects` — refused on purpose

The manual-creation endpoint is kept and documented, and creates nothing:

```http
POST /api/projects
{"name": "X"}
```
```json
{"error": {"code": "project_creation_removed",
           "message": "Los proyectos se crean fuera de BizView y se importan: Proyectos → Importar proyecto.",
           "key": "projects.creation_removed", "params": {}}}
```

Status: **410 Gone**. Constant in `projects.py`, referenced from `docs/IMPORT.md` and the guide topic, so
a client author reads the reason instead of guessing.

---

## `GET /api/projects/slug` — removed

It existed only to fill the create form. It is gone; a caller gets `404`. `project_service.suggest_slug()`
stays (the importer uses it for a colliding slug).
