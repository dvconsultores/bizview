# Contracts — 060-source-connection-limits

Only shapes the frontend consumes are listed; nothing in the project file format changes (no YAML
key, no schema, no CLI change), so `cli/bizview_cli/schemas/` is untouched.

## 1. `GET /api/integrations` (unchanged route, additive fields)

Each integration object gains `busy`:

```json
{
  "id": "ventas-medicalvet",
  "source": "erp-medicalvet",
  "busy": {
    "busy_today": 4,
    "quiet_hour": 3,
    "ceiling": 1
  }
}
```

| Field | Type | Meaning |
|---|---|---|
| `busy_today` | int | `skipped_busy` runs of this integration since local midnight. |
| `quiet_hour` | int \| null | Hour (installation time zone) with the fewest busy runs of the last 7 days; null when `busy_today < 3` or fewer than two hours show data. |
| `ceiling` | int | The effective simultaneous-connection ceiling of its source, so the integration page can say it without a second request. |

## 2. `IntegrationRun` (additive field)

`run_json` (`backend/app/api/workspace.py`) gains `busy`:

```json
{
  "id": 9021,
  "status": "skipped_busy",
  "message": "La fuente no admite más conexiones ahora (4 intentos, 5 min). El origen respondió: FATAL: lo siento, ya tenemos demasiados clientes",
  "busy": {"sqlstate": "53300", "attempts": 4, "waited_s": 285,
           "detail": "FATAL: lo siento, ya tenemos demasiados clientes"}
}
```

Rules the UI relies on:

- `status` is one of `running | succeeded | failed | skipped | stopped | skipped_busy`.
- `busy` is always present (`{}` when the run never saw a busy origin).
- `message` is already rendered in the request language by `render_stored`; when `busy.attempts > 1`
  the message names the attempts and the wait.
- No host, port, user or password ever appears in `message` or `busy.detail`.

## 3. `GET /api/sources/types`

The PostgreSQL and Supabase field lists gain one entry, served from `app/sources/schemas.py`:

```json
{"name": "max_connections", "label": "Conexiones simultáneas", "type": "integer",
 "required": false, "default": 1, "min": 1, "max": 20,
 "help": "Cuántas conexiones puede abrir BizView a la vez en esta fuente"}
```

`label` and `help` come from `app/i18n` (`sources.postgresql.max_connections`), so both languages work
with no frontend change beyond the existing generic renderer.

## 4. `POST /api/sources/{id}/test` — details

PostgreSQL result, success path:

```json
{
  "ok": true, "latency_ms": 42, "warnings": [],
  "details": {
    "server_version": "PostgreSQL 16.3",
    "tls": true,
    "max_connections": 100,
    "clients": 97,
    "clients_visible": true
  }
}
```

- `max_connections` / `clients` only when `pg_settings` and `pg_stat_activity` are readable.
- `clients_visible: false` otherwise: the test still reports `ok: true` and the UI says
  «sin permiso para verlo» / "no permission to see it" (FR-020).
- A busy origin during a *test* is not retried (an HTTP request must answer fast) but is reported with
  the new code `busy`, whose message is the same «La fuente no admite más conexiones ahora», plus a
  `details.sqlstate`.

## 5. Retry/backoff configuration (installation, not project)

| Variable | Default | Meaning |
|---|---|---|
| `SOURCE_CONNECT_RETRIES` | 4 | Connection attempts per run on a busy origin (1 = no retry). |
| `SOURCE_CONNECT_BACKOFF_S` | 15 | Base delay of the exponential backoff; attempt *n* waits `base · 3^(n-1)` with ±20 % jitter. |

Both documented in `.env.example` and `docs/INSTALL.md`; neither appears in a project file, so a
customer project stays portable (constitution III/VII).

## 6. UI strings (contract with the translator)

| Key | ES | EN |
|---|---|---|
| `integrations.runBadge.busy` | La fuente no admite más conexiones ahora | The source has no free connection slots |
| `integrations.run.busyAttempts` | {n} intentos, {wait} | {n} attempts, {wait} |
| `integrations.run.whatToDo` | Qué hacer | What to do |
| `integrations.run.waitingTurn` | Esperando turno en la fuente | Waiting for a turn on the source |
| `integrations.run.quietHour` | El origen estuvo lleno a esta hora: prueba a las {hour} | The origin was full at this hour: try {hour} |
| `sources.postgresql.max_connections` | Conexiones simultáneas | Simultaneous connections |
| `sourceTest.maxConnections` | Conexiones máximas del origen | Origin's maximum connections |
| `sourceTest.clients` | Clientes ahora | Clients now |
| `sourceTest.noPermission` | Sin permiso para verlo | No permission to see it |
| `sourceTest.busy` | La fuente no admite más conexiones ahora | The source has no free connection slots |
