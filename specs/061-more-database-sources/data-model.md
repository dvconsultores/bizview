# Data model — More database sources (061)

No new table and no new column: a source kind is a value of `data_source.kind`, whose CHECK widens.
What this feature adds is the *content* of `data_source.settings` and of the encrypted
`data_source.secrets` for five more kinds, and the registry that decides which of those shapes is
valid.

## `data_source.kind`

| Value | Label (ES / EN) | SQL | Tables | Files | API | Origin session |
|---|---|---|---|---|---|---|
| `postgresql` | PostgreSQL | ✔ | ✔ | — | — | ✔ (native COPY) |
| `supabase` | Supabase | — | — | — | ✔ | — |
| `rest` | API REST | — | — | — | ✔ | — |
| `soap` | SOAP (SAP y otros) | — | — | — | ✔ | — |
| `sqlite` | SQLite (archivo) | ✔ | ✔ | ✔ | — | ✔ |
| `mysql` | MySQL / MariaDB | ✔ | ✔ | — | — | ✔ |
| `mssql` | SQL Server | ✔ | ✔ | — | — | ✔ |
| `bigquery` | Google BigQuery | ✔ | ✔ | — | — | — |
| `sheets` | Google Sheets | — | ✔ | — | ✔ | — |

`backend/app/models.py` mirrors this list (`SOURCE_KINDS`) only so the constraint and the model
agree; the product reads `connectors/registry.py`.

## Fields per kind (`data_source.settings`)

Every kind keeps the two shared fields: `timeout_seconds` (default 15) and `max_connections` (the
060 ceiling; default 1, 2 for the Google kinds and BigQuery).

| Kind | Settings | Secrets (encrypted, write-only) |
|---|---|---|
| `sqlite` | `path` (a file name inside `SOURCES_FILES_DIR`), `timeout_seconds`, `max_connections` | — |
| `mysql` | `host`, `port` (3306), `database`, `username`, `sslmode` (`require`/`verify-full`/`prefer`/`disable`), `ca_certificate`, `timeout_seconds`, `max_connections` | `password` |
| `mssql` | `host`, `port` (1433), `database`, `username`, `encrypt` (`yes`/`optional`), `ca_certificate`, `timeout_seconds`, `max_connections` | `password` |
| `bigquery` | `project`, `location`, `datasets` (comma separated allow-list), `max_bytes_billed` (default 1 GB), `timeout_seconds`, `max_connections` | `service_account` (JSON) |
| `sheets` | `url` (spreadsheet link or id), `header_row` (default 1), `sample_rows` (default 200), `timeout_seconds`, `max_connections` | `service_account` (JSON) |

Validation rules that are new or per kind:

- `host`/`port` are dialled through `netguard.resolve_checked` with the kind's **default port**
  (`DEFAULT_PORTS`), and the security profile forbids plaintext under `internet` exactly as before.
- `sqlite.path` is resolved against `SOURCES_FILES_DIR` on save: outside it, missing, a wrong
  extension, larger than 4 GB or a symlink resolving out of the folder → an error naming the reason
  (`sources.sqlite.*`), and the source is not stored.
- `service_account` must be JSON with `client_email` and `private_key`; the address is the only part
  ever read back (to show it in the form and in a "share the sheet with this address" failure).

## The registry (`app/sources/connectors/registry.py`)

```python
@dataclass(frozen=True)
class Capabilities:
    sql: bool = False            # an integration's query is SQL this kind runs
    tables: bool = False         # it has schemas/tables/columns the structure reader lists
    files: bool = False          # it reads a local file instead of a network address
    api: bool = False            # it answers HTTP requests rather than SQL
    session: bool = False        # it opens a real session, so the 060 ceiling applies
    native_copy: bool = False    # PostgreSQL: COPY (query) TO STDOUT

@dataclass(frozen=True)
class Spec:
    kind: str
    module: str                  # app.sources.connectors.<module>
    capabilities: Capabilities
    fields: Callable[[], tuple]  # lazily from app.sources.schemas.FIELDS
    drivers: tuple[str, ...] = ()
```

The module a kind names must export `kind`, `label`, `test()`, `describe()`, `dialect_notes()`;
plus `session()`/`rows()` when `sql`, `request_rows()` when `api` with request extraction, and
optionally `available(app)`, `is_busy(error)`, `classify(error)`.

## State machine of a source (unchanged)

`draft → tested → described → enabled`; `enabled → disabled`. New kinds add no transition. What the
verdict card can now answer per kind:

| Verdict | PostgreSQL | SQLite | MySQL | SQL Server | BigQuery | Sheets |
|---|---|---|---|---|---|---|
| reachable | connect | file opens | connect | connect | dry run | `spreadsheets.get` |
| auth | role | — | user/password | login | service account | service account |
| read-only | session + write probe | `mode=ro` | `READ ONLY` + `SHOW GRANTS` | statement rule + `IS_MEMBER('db_datawriter')` | role list | read-only scopes |
| TLS | `sslmode` | — | `sslmode` + CA | `encrypt` + `sys.dm_exec_connections` | HTTPS | HTTPS |
| busy | SQLSTATE 53300 | `database is locked` | 1040/1203/1129 | 17809 | quota | HTTP 429/quota |

## Migration

`alembic/versions/0056_more_source_kinds.py` — drops and recreates `ck_data_source_kind` with the
nine values. Downgrade refuses while any of the five new kinds exists (as `0010` did for Supabase):
dropping the constraint would leave rows the old CHECK forbids.
