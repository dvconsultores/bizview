# Contract — starter pack

## `GET /api/projects/starter`

Superuser. Session cookie (an `<a download>` works, as with `export.zip`).

| Query | Required | Values |
|---|---|---|
| `name` | yes | 1–80 chars; the project name |
| `source` | no | the name of a registered source |
| `lang` | no | `es` (default) / `en` |
| `kind` | no | `integration` (default) / `direct` |

**200** — `application/zip`,
`Content-Disposition: attachment; filename="bizview-starter-<slug>.zip"`.
Header `X-Bizview-Structure: included` or `unavailable` says whether the source's structure made it.

**404** — `not_found` when `source` names a source this installation does not have.

**413** — `too_large` (with the refusal code as `code`) when the rendered project exceeds an import
allowance (049). Nothing is served.

**422** — `slug_invalid` when the name yields no usable slug.

## `GET /api/projects/starter-template`

Superuser. **200** `application/zip`, `filename="bizview-starter-template.zip"`. Never 404: when the
committed file is absent the template is rendered in memory.

## `bizview init project <name> [--source <s>] [--lang es|en] [--kind integration|direct] [--dir PATH]`

Writes the rendered pack into `<dir>/<slug>/` (default: `projects/<slug>/` when the current folder
has a `bizview.yaml`, else `./<slug>/`). Prints the path and the next step. Exit 2 on a bad name or a
folder that is not empty.

## `bizview init workspace --name <name>`

Unchanged shape (root files, `projects/`), but `projects/` now starts empty: the per-project pack
comes from `init project`. A workspace remains the container the validator expects.

## `make starter-template`

Writes `bizview-starter-template.zip` at the repository root. Deterministic: two runs produce the
same bytes. Fails when the pack is missing.

## Rendered zip — required entries

```text
PROMPT.md                        (+ PROMPT.<other>.md)
REQUEST.md                       (+ REQUEST.<other>.md)
README.md                        (+ README.<other>.md)
CLAUDE.md, AGENTS.md             (+ <other> copies)
project.yaml
bizview.yaml
specs/001-<slug>/spec.md
specs/001-<slug>/plan.md
specs/001-<slug>/tasks.md
integrations/<slug>/integration.yaml        (kind=integration)
integrations/<slug>/queries/example.sql     (kind=integration)
reports/<slug>/report.yaml
sources/<source>/structure.md               (when a source is chosen)
sources/<source>/structure.json             (when a source is chosen)
.bizview/schemas/*.json
.bizview/preset.yaml
CONTENIDO.md, CONTENTS.md
QUE-HACE-BIZVIEW.md, WHAT-BIZVIEW-DOES.md
```
