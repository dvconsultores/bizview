# Validate before importing

## What it is for

Import always validates. Validating first, on your machine, only lets you see the problems without
uploading anything and fix them with the same list Bizview will show afterwards.

## Who can use it

Only the **Superuser**, and only when the CLI is installed. It is not required: step 5 of
**Import project** runs exactly the same check.

## How to

1. Install the CLI: `uv tool install bizview-cli`.
2. Unzip the project inside a workspace, under `projects/<identifier>/`.
3. Open that folder in the terminal.
4. Run `bizview validate`.
5. Fix what appears and repeat until no error is left.
6. With `--write-lock` it writes `bizview.lock`, the fingerprint of what was validated.

The CLI and the server read the same schemas, so a project that validates here applies there.

## Options

- `--describe <name>=<file.json>` checks against a structure you already downloaded, without
  connecting.
- `--live` also runs each query against the source, when the installation lets you reach it.
- `bizview import --dry-run project.zip` measures the zip against both budgets without uploading it.

## Common problems

- A `schema_error` in a YAML is usually a misspelled key or two-space indentation where four belong.
- `missing_spec` means the artifact's `spec:` does not point at a folder that exists.
- When the command cannot find `bizview.yaml`, the folder is not a workspace: the project goes
  inside `projects/`.

## Related

- Fix the problems
- Import a project
- Project structure
