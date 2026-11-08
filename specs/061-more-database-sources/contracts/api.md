# API contracts — More database sources (061)

Only one response shape changes, and only additively: `GET /api/sources/types` gains two keys per
kind. Everything else already existed and now answers for nine kinds instead of four.

## `GET /api/sources/types` (super user)

Field definitions for **Nueva fuente**, in the language of the request (022).

```json
{
  "mysql": {
    "label": "MySQL / MariaDB",
    "http_allowed": true,
    "available": true,
    "reason": "",
    "fields": [
      {"name": "host", "label": "Servidor", "type": "string", "required": true, "default": null,
       "help": "", "options": [], "min": null, "max": null, "secret": false},
      {"name": "port", "label": "Puerto", "type": "integer", "default": 3306, "...": "..."},
      {"name": "sslmode", "label": "Cifrado (TLS)", "type": "enum", "default": "require",
       "options": ["require", "verify-full", "prefer", "disable"], "...": "..."}
    ]
  },
  "mssql":    {"available": false, "reason": "Falta el controlador de este tipo…", "...": "..."},
  "sqlite":   "…"
}
```

- `available` / `reason` are new (FR-017). A kind whose driver is not installed is **listed** with
  `available: false` and the reason, never a 500.
- `sqlite` is **omitted** when `SOURCES_FILES_DIR` is not configured (spec US2, research R10): an
  installation with no folder of origin files does not offer the kind at all.
- `files` is a new field `type` (SQLite's `path`): the client renders a picker fed by
  `GET /api/sources/files`; the value is one file name, never a path.

## `GET /api/sources/files` (super user) — new

```json
{"items": [{"name": "export-2026-11.sqlite3", "size": 48234567}]}
```

Files inside `SOURCES_FILES_DIR` with an accepted extension, newest names last, at most 200. Empty
list when the folder is not configured. No path, no permission, no directory listing outside it.

## `POST /api/sources` / `PATCH /api/sources/{id}`

`kind` accepts the nine values. Validation errors keep their shape (`{"settings.host": "required"}`)
and gain:

| Error | When |
|---|---|
| `settings.path: "sources.sqlite.outside"` | the path resolves outside `SOURCES_FILES_DIR` |
| `settings.path: "sources.sqlite.missing"` | no such file |
| `settings.path: "sources.sqlite.extension"` | not `.sqlite/.sqlite3/.db/.db3` |
| `settings.path: "sources.sqlite.too_large"` | larger than 4 GB |
| `settings.host: "blocked_address"` | `netguard` refuses the address (all network kinds) |
| `settings.sslmode: "not_allowed_in_profile"` | plaintext under the `internet` profile |

## `POST /api/sources/{id}/test`

Unchanged shape (`TestResult.to_json()`); the codes are the ones the kinds can return:
`ok`, `unreachable`, `timeout`, `tls_error`, `auth_failed`, `not_found`, `invalid_response`,
`not_read_only`, `busy`, `unavailable`, `error`. New: `unavailable` (driver or folder missing) and
`not_read_only` (the driver refused the read-only session). `warnings` may carry `not_read_only`
(a MySQL/SQL Server/BigQuery credential that can write).

## `GET /api/sources/{name}/structure?format=json|md&mode=pack|scan`

Unchanged shape. For the new SQL kinds the body is the PostgreSQL shape plus `dialect`:

```json
{"kind": "mysql", "truncated": false, "quote": "`",
 "dialect": {"kind": "mysql", "quote": "`", "limit": "LIMIT", "identifier_case": "sensitive",
             "notes": "Backtick identifiers; …"},
 "tables": [{"schema": "erp", "name": "ventas", "kind": "table",
             "columns": [{"name": "marca", "type": "varchar", "nullable": false}]}]}
```

For Google Sheets a worksheet is a table:

```json
{"kind": "sheets", "truncated": false,
 "tables": [{"schema": "sheets", "name": "Ventas", "kind": "table", "rows": 1999,
             "columns": [{"name": "marca", "type": "string", "nullable": true}]}]}
```

Never a row value, never the host, the project id or the spreadsheet id beyond the source's name.

## The starter zip (057, FR-014)

`GET /api/projects/starter?source=<name>` now accepts any kind: when a source is chosen, the zip
carries `sources/<name>/structure.md` + `structure.json` for it, dialect notes included, so the AI
writes the right syntax for MySQL, SQL Server, SQLite, BigQuery or Sheets without a second prompt.
