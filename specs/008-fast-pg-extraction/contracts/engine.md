# Engine contract: PostgreSQL bulk extraction

Internal contract between `backend/app/engine/extract.py` and `backend/app/engine/runner.py`.
No HTTP or workspace artifact changes.

## `extract.pg_copy(...)`

```python
class BulkUnsupported(Exception):
    """Origin refused COPY (query) TO STDOUT before any data was sent."""
    reason: str            # SQLSTATE class name, e.g. "FeatureNotSupported"

def pg_copy(settings: dict, secrets: dict, app: Settings, query: str, params: dict, *,
            columns: list[str], timezone: str, time_limit_s: int, deadline: float,
            write: Callable[[bytes], None]) -> int   # blocks written
```

1. Opens the origin with `_pg_connect` (read-only, statement timeout, time zone, application
   name) and sets `DateStyle=ISO, MDY`, `IntervalStyle=postgres`, `extra_float_digits=3`,
   `bytea_output=hex` for the session. If a SET is refused with `FeatureNotSupported`,
   `UndefinedObject`, `InvalidParameterValue`, or `CantChangeRuntimeParam`, pg_copy raises
   `BulkUnsupported(reason)` before any data is sent; any other psycopg error raises
   `ExtractError("la extracción falló: <first line>")`.
2. Renders `to_psycopg(query)` with `ClientCursor.mogrify(q, params)`.
3. Probes `SELECT * FROM (<rendered>\n) AS q LIMIT 0` (query closed on a new line so a trailing
   `--` comment works); column names ≠ `columns` (as sets, same length) → `ExtractError` with
   today's message. A probe failure never raises `BulkUnsupported` and never falls back (even
   for `SyntaxError` or `FeatureNotSupported`): `QueryCanceled` raises the time-limit
   `ExtractError` and any other psycopg error raises `ExtractError("la extracción falló:
   <first line>")`.
4. Runs `COPY (SELECT <columns quoted> FROM (<rendered>\n) AS q) TO STDOUT (FORMAT text)`,
   calling `write(block)` for each block; checks `time.monotonic() > deadline` between blocks →
   `ExtractError("se superó el tiempo máximo de la integración")`.
5. COPY errors `FeatureNotSupported`, `InsufficientPrivilege`, `SyntaxError`,
   `UndefinedFunction` raise `BulkUnsupported(reason)` only while zero blocks have been
   written; after the first write they become `ExtractError` (no fallback). `QueryCanceled`
   raises the time-limit `ExtractError`; errors raised by `write` propagate unchanged; other
   psycopg errors raise `ExtractError` with the first line of the message.

## Runner

`runner._extract` for a `query` dataset:

```text
plan.path = "bulk"
write = closure that opens COPY <staging> (<columns>) FROM STDIN (FORMAT text) on the FIRST block
        (lazy: a refusal before any data leaves the installation transaction usable for the fallback)
extract.pg_copy(..., write=write)
plan.extracted = destination cursor rowcount after its COPY ends (0 when no block arrived)
on BulkUnsupported(reason): plan.path = "rows"; plan.fallback = reason; run the current path
on DataError (during a write or when the COPY ends): ExtractError("los datos no cumplen el contrato: …")
```

`_finish` writes `path` (and `fallback` when set) into `integration_run.rows[<dataset>]`.
REST/SOAP datasets keep the current path and record `"path": "rows"`.
