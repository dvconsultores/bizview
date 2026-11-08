# Data model — 060-source-connection-limits

Only the product schema changes. The origin database is read and nothing is written to it (constitution
III).

## 1. `integration_run.status` — one value added

| Status | Meaning | Colour | Changes data? |
|---|---|---|---|
| `running` | in progress | blue | — |
| `succeeded` | loaded | green | yes |
| `failed` | a defect (query, contract, checks, timeout, unreachable) | red | no (rolled back) |
| `skipped` | nothing to do: source disabled/missing, already running | amber | no |
| `stopped` | an operator stopped it | grey | no (rolled back) |
| **`skipped_busy`** | **the origin had no free connection slots after every retry** | **amber** | **no** |

Rules:

- `skipped_busy` is produced only by a `SourceBusy` that survived every retry (FR-004).
- It never rolls back a *load* — it happens before one starts — and it leaves `data_version` and the
  datasets untouched (FR-005).
- A run that retried and then failed another way is `failed`, with `busy.attempts > 0` (FR-008).
- The next tick is unaffected: nothing is paused, nothing is disabled (FR-003/SC-001).
- Existing rows are untouched; the new value widens the CHECK, never narrows it.

Migration: `0055_source_connection_limits` drops and recreates the `status` CHECK on
`integration_run` with the six values.

## 2. `integration_run.busy` — the retry record

New column, `JSONB NOT NULL DEFAULT '{}'`.

```json
{
  "sqlstate": "53300",
  "attempts": 4,
  "waited_s": 285,
  "detail": "FATAL: lo siento, ya tenemos demasiados clientes"
}
```

| Field | Type | Notes |
|---|---|---|
| `sqlstate` | string \| null | The origin's SQLSTATE when it gave one; null for a pooler's plain-text refusal. |
| `attempts` | int | How many connection attempts the run made (1 = no retry). |
| `waited_s` | int | Total seconds spent in backoff. |
| `detail` | string \| null | First line of the origin's own message, **redacted** of secrets, host and port, at most 300 characters. |

Empty `{}` for every run that never saw a busy origin. Serialised as `busy` in `run_json`, so the run
list can say «4 intentos, 7 min» without parsing the message (FR-019).

Migration: the same `0055` revision adds the column.

## 3. Source connection ceiling

Not a new table: `data_source.settings` already holds per-kind values validated by
`app/sources/schemas.py`. A new field joins the PostgreSQL and Supabase field lists:

| Source kind | Field | Default | Range |
|---|---|---|---|
| `postgresql` | `max_connections` — «Conexiones simultáneas» | 1 | 1–20 |
| `supabase` | `max_connections` | 2 | 1–20 |
| `rest`, `soap` | *(no field; HTTP calls, default 4 in code)* | 4 | — |

Behaviour:

- The effective ceiling is `settings["max_connections"]` when present and valid, else the kind's
  default (`source_slots.limit_of`). An invalid stored value falls back to the default instead of
  raising: a source must never become unusable because a number went bad.
- Every reader respects it: scheduled run, manual run, `describe`, structure generation, direct read
  (FR-009).
- Values outside 1–20 are refused at save time by the existing generic integer validation, with the
  field's label and range in the message (FR-020).

## 4. Busy streak (derived, not stored)

`streak(integration_id)` = number of consecutive `integration_run` rows, newest first, whose status is
`skipped_busy`; it stops at the first row that is anything else. A `stopped` run neither extends nor
resets it — it is skipped by the scan, not counted (spec Assumptions).

The notification is throttled by the audit trail rather than a new table:

- an `integration_busy` audit event is written when the notification is sent;
- `notify_if_due` sends only when the streak is ≥ 3 **and** no `integration_busy` event exists with
  `occurred_at >=` the streak's first run, so the fourth, fifth and hundredth busy run of the same
  streak stay silent (FR-007/SC-006);
- a run that is not `skipped_busy` ends the streak, and the next streak of three notifies again.

## 5. New audit kind

`AUDIT_KINDS` gains `integration_busy`, with detail
`{"integration": "<id>", "streak": 3, "attempts": 4, "sqlstate": "53300"}` — no host, no credential,
no address (the audit writer already asserts no secret-like keys). Migration `0055` extends the
`kind` CHECK on `audit_event`.

## 6. Integration hint (derived)

`busy.hint(db, integration_id)` → `{"busy_today": int, "quiet_hour": int | null}` (R8), carried by the
existing `GET /api/integrations` payload. `quiet_hour` is null unless `busy_today >= 3` and at least
two distinct hours show busy runs in the last 7 days.

## 7. Test-connection details (no storage change)

`data_source.last_test` already stores whatever `TestResult.details` returns; PostgreSQL's `test()`
adds two keys when the role may read them:

```json
{"server_version": "PostgreSQL 16.3", "tls": true,
 "max_connections": 100, "clients": 97, "clients_visible": true}
```

`clients_visible: false` when `pg_stat_activity` is not readable — the connection is still a success
(FR-020).

## State transitions of a run

```text
                        ┌────────────── busy, attempts left ──────────────┐
                        ▼                                                │
  (start) ──▶ running ──▶ connect ──(53300)──▶ backoff 15s/45s/2m/5m ────┘
                 │              │
                 │              └──(busy, no attempts left)──▶ skipped_busy
                 │
                 ├──(data loaded)──▶ succeeded
                 ├──(defect)───────▶ failed
                 └──(stop)─────────▶ stopped
```

`skipped_busy` is terminal for that run; the *integration* keeps its schedule.
