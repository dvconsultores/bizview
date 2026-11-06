# What the pack contains, file by file

This zip is a **BizView project template**. It is not a finished project: the skeletons carry sample
values marked `REPLACE`. Here is what each file is, who writes it, whether it is required, and what
BizView does with it on import.

Legend: **You** = you edit it · **Your AI** = the AI writes it · **BizView** = shipped, do not edit ·
**CLI** = written by `bizview`.

| File | Required? | Written by | What BizView does with it |
|---|---|---|---|
| `project.yaml` | Yes | You (the dialog fills it) | Reads `name`, `slug` and `description`. The `slug` decides whether the zip is a new project or a revision of an existing one. |
| `bizview.yaml` | Yes, to validate | BizView | Workspace manifest. Only `bizview validate` on your machine reads it; import ignores it. |
| `REQUEST.md` | For your AI | You | Never imported. It is the brief your AI reads. |
| `REQUEST.*.md` | For your AI | You | The same, in the other language. Ignored on import. |
| `PROMPT.md` | For your AI | BizView | The project's rules. Ignored on import. |
| `PROMPT.*.md` | For your AI | BizView | The same rules in the other language. Ignored. |
| `CLAUDE.md`, `AGENTS.md` | For your AI | BizView | The same text as `PROMPT.md`, for tools that read a folder. Ignored. |
| `CLAUDE.*.md`, `AGENTS.*.md` | For your AI | BizView | The copies in the other language. Ignored. |
| `README.md` | No | BizView | The three steps. Ignored on import. |
| `README.*.md` | No | BizView | The same three steps in the other language. Ignored. |
| `CONTENIDO.md` | No | BizView | This document in Spanish. Ignored on import. |
| `CONTENTS.md` | No | BizView | This document. Ignored on import. |
| `QUE-HACE-BIZVIEW.md` | No | BizView | What happens on import and apply, in Spanish. Ignored. |
| `WHAT-BIZVIEW-DOES.md` | No | BizView | The same in English. Ignored. |
| `specs/001-<slug>/*` | Yes | Your AI | `spec.md` is required: BizView shows it in the editor and demands it to run. `plan.md` and `tasks.md` complete the record; when missing, the project is flagged as incomplete. |
| `specs/001-<slug>/spec.md` | Yes | Your AI | States the kind (`integracion` or `reporte`) and `**Status**: Approved`. Without an approved spec the project cannot be applied, and the `**Datos personales**` line is compared with the dataset's columns. |
| `specs/002-<slug>-reporte/*` | Yes | Your AI | The report's own spec: kind `reporte`, `**Status**: Approved` and the metrics the reader sees. Without it the dashboard has no owner. |
| `integrations/<id>/integration.yaml` | With an integration | Your AI | Declares what is read, how often, the key, the incremental window and the checks. On apply it becomes a worker schedule. |
| `integrations/<id>/queries/*.sql` | With an integration | Your AI | The read-only read. Validated statically (a single `SELECT`/`WITH`) and run by the worker. |
| `integrations/<id>/requests/*.yaml` | REST/SOAP sources | Your AI | Replaces the SQL when the source is not a database. Same static validation. |
| `reports/<id>/report.yaml` | Yes | Your AI | Metrics, dimensions, views, periods, filters and the web and PDF design. On apply it becomes a dashboard at `/r/<id>`. |
| `assets/**` | No | You | Images for `asset` blocks and KPI icons. They have their own budget. |
| `sources/<source>/*` | For your AI | BizView | The structure of the chosen source (`structure.md` and `structure.json`). Never imported. |
| `.bizview/schemas/*` | For your AI | BizView | The JSON Schemas BizView validates against. Never imported. |
| `.bizview/preset.yaml` | For your AI | BizView | The contract summary: which schema applies to each file, and the rules. Never imported. |
| `bizview.lock` | No | CLI | Fingerprint of an already validated tree. Informative; import ignores it. |

## Naming rules

- Spec folders are `NNN-<slug>`: three digits, consecutive **per project**, and a number is never
  reused.
- Integration, report and distribution `id`s are lowercase with dashes (`kebab-case`) and match
  their folder name.
- A report id is a URL: `/r/<id>`. Changing it changes links you already shared.
- The project `slug` is the identity: the first import creates the project and a second one with the
  same `slug` proposes a revision.

## What import ignores

- Everything that is not the project format: `PROMPT.md`, `REQUEST.md`, `README.md`, `CONTENIDO.md`,
  `CONTENTS.md`, `QUE-HACE-BIZVIEW.md`, `WHAT-BIZVIEW-DOES.md`, `CLAUDE.md`, `AGENTS.md`,
  `bizview.yaml`, `sources/`, `.bizview/`, `bizview.lock` and system files (`.DS_Store`).
- Repeated files that are not text.
- A file that looks like a program (`.js`, `.sh`, `.exe`…) **cancels** the import: that is not noise.

## Budgets

| Limit | What it counts | Files | Per file | Total |
|---|---|---|---|---|
| Artifacts | `project.yaml`, `specs/`, `integrations/`, `reports/`, `themes/`, `distributions/` | 400 | 2 MB | 20 MB |
| Images | `assets/` | 2 000 | 300 KB | 25 MB |

The two limits are counted apart and an installation may raise them. A refusal always names the limit
that was exceeded.
