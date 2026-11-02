# Contract — CLI tallies and dry run

Two commands report the same numbers the server would, from the same module
(`cli/bizview_cli/budgets.py`). Nothing here uploads anything.

---

## `bizview validate` (unchanged command, one new block)

`--json` output gains a `budgets` object beside the existing `ok` / `issues` / `lock`:

```json
{
  "ok": false,
  "issues": [{"file": "projects/ventas", "code": "assets_over_files", "message": "…"}],
  "budgets": {
    "projects/ventas": {
      "artifacts": {"files": 41, "bytes": 51234, "max_files": 400, "max_mb": 20, "over": []},
      "assets":    {"files": 2150, "bytes": 18874360, "max_files": 2000, "max_mb": 25,
                    "over": ["files"]},
      "ignored": ["PROMPT.md", "request/logo.png", "sources/ventas/structure.json"]
    }
  }
}
```

- A project over a budget gets an **issue** whose code is the same one the server would answer
  (`assets_over_files`, `artifacts_over_bytes`, …), with `file` set to the project key so the author sees
  it in the same list as every other problem.
- `ignored` is the list `_ignored_files()` already computes, now reported instead of being computed and
  dropped.
- Exit code: `1` when any issue exists (unchanged), `0` when none — a project over budget is an issue, so
  it exits `1`.

**Human output** gains two lines per project:

```text
ventas   artefactos 41/400 archivos, 50 KB/20 MB   imágenes 483/2 000 archivos, 1,8 MB/25 MB
         ignorados: PROMPT.md, README.md, sources/ventas/structure.json
```

---

## `bizview import --dry-run <zip|folder>`

New subcommand. It reads a **zip** (the thing the app accepts) or a **folder**, applies exactly the rules
the server applies — classification, per-file size, counts, totals, disallowed content — and prints what
would happen. It never writes to a project and never talks to a server.

```bash
bizview import --dry-run panorama.zip
bizview import --dry-run panorama/ --json
```

Human output:

```text
panorama.zip
  proyecto      panorama  (carpeta superior omitida)
  artefactos    41 archivos, 50 KB  — límite 400 / 20 MB      OK
  imágenes      483 archivos, 1,8 MB — límite 2 000 / 25 MB    OK
  ignorados     4: PROMPT.md, REQUEST.md, README.md, sources/ventas/structure.md
  resultado     importable
```

```text
logos.zip
  artefactos    38 archivos, 46 KB   — límite 400 / 20 MB      OK
  imágenes      2 150 archivos, 18 MB — límite 2 000 / 25 MB    EXCEDIDO (archivos)
  resultado     no importable
  motivo        El proyecto supera el límite de imágenes: 2 150 archivos en assets/ (máximo 2 000)
```

`--json` prints the same object `bizview validate --json` puts under `budgets`, plus
`{"importable": bool, "reason": str|null, "ignored": [...], "slug": "panorama"}`.

**Exit codes**: `0` importable, `1` over a budget or disallowed content, `2` unreadable input (not a zip,
missing folder) — the CLI's existing convention for "could not run".

---

## Parity rule

For the same bytes, these must be equal, and a test asserts it (SC-005):

| | server | CLI |
|---|---|---|
| files/bytes per budget | `zip.import_zip` → `budgets.json()` | `import --dry-run --json` |
| ignored paths | response `ignored` | `--json` → `ignored` |
| refusal code | `error.code` | `issues[0].code` |

The comparison is a test against one fixture zip, not a runtime call: the CLI has no server to ask.
