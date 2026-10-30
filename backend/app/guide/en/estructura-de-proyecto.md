# Project structure

## What it is for

It explains which files a project has and where each thing goes. The editor and the agent accept
only these paths.

## Who can use it

Only the **Superuser**.

## How to

A project is a folder with:

- `project.yaml`: name, identifier and description.
- `.specify/memory/constitution.md`: the project's principles, with the fixed block of
  installation rules.
- `specs/NNN-name/`: one folder per spec, numbered without reuse (`001`, `002`…), with `spec.md`,
  `plan.md` and `tasks.md`, and optional `research.md`, `data-model.md`, `quickstart.md` and
  `checklists/<name>.md`.
- `integrations/<id>/integration.yaml`, with its `queries/*.sql` queries or `requests/*.yaml`
  requests.
- `reports/<id>/report.yaml`.
- `distributions/<id>.yaml`.

## Options

- The project chat lives in the **Assistant** panel (the button in the project header or the one
  in the top bar); on phones it is the **Chat** tab.
- **Full screen** hides the menu and the top bar and gives the explorer, the editor and the chat
  the whole screen; leave it with the same button or with Esc.
- Each artifact points to its spec with the `spec:` field, for example `spec: specs/002-ventas`.
- Integration, report and distribution ids are unique across the whole installation.
- There is a maximum size per file and per project; the editor warns when it is exceeded.
- Credentials and row data are never stored in a project: sources are named, not configured here.
