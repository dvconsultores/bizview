# Research — 060-source-connection-limits

Phase 0 of [plan.md](./plan.md). Each decision names what was chosen, why, and what else was
considered. Line references are to the code as it stands on `main` at 2026-11-07.

## R1 — How a connection-slot refusal is recognised

**Decision.** One classifier in `backend/app/engine/extract.py`, next to `_pg_connect` (the single
funnel every origin connection goes through):

- SQLSTATE in `{53300 too_many_connections, 53200 out_of_memory, 57P03 cannot_connect_now,
  08001 sqlclient_unable_to_establish_sqlconnection, 08006 connection_failure}` →
  `SourceBusy(sqlstate, detail)`.
- When psycopg reports no SQLSTATE (a pooler in front often answers plain text before PostgreSQL
  speaks), the first line is matched against the wordings that stand for the same condition, in the
  languages the codebase already matches for auth failures (`AUTH_WORDS` in
  `app/sources/connectors/postgresql.py` is the precedent): `too many clients`,
  `demasiados clientes`, `trop de clients`, `zu viele clients`, `no more connections allowed`
  (PgBouncer), `server_login_retry` (PgBouncer), `remaining connection slots are reserved`.
- Only a *connect* failure or a failure raised while opening the session is classified: a
  `QueryCanceled`, a permission error or a data error after the connection was made keeps today's
  `ExtractError` path. Implemented by classifying inside `_pg_connect` only.
- The stored `detail` is `_first_line(e)` once the secrets and the host have been redacted with the
  runner's existing `_redactor(secrets)`; the host string is added to the redaction list. No port, no
  user, no password.

**Why.** The SQLSTATE is authoritative when present and cheap; the wording fallback is what actually
fires behind a pooler, which is one of the four remedies the feature recommends, so it must not defeat
the classification.

**Alternatives considered.** Matching wording only (fragile and localised, as the existing
`AUTH_WORDS` shows); a `psycopg.OperationalError` check with no content (would catch "network
unreachable" too, which the spec says must stay a failure).

## R2 — Where the retry lives

**Decision.** In `backend/app/engine/runner.py`, around the origin read of each dataset
(`_extract` / `_run_checks`), not inside `_pg_connect`:

```
for attempt in range(1, retries + 1):
    try:
        <origin read>
        break
    except extract.SourceBusy as e:
        busy = e
        if attempt == retries or not _wait(backoff(attempt)): raise
```

`_wait` sleeps in 0.5 s slices, checking the run's `StopFlag` (raises `RunStopped`) and the run's
deadline (stops retrying), so an operator's stop or the integration's own time limit interrupts the
backoff. The delays are `base * 3 ** (attempt - 1)` with ±20 % jitter, base from
`SOURCE_CONNECT_BACKOFF_S` (default 15 → ~15 s, 45 s, 2 min, 5 min for four attempts).

**Why.** The retry must re-run the *read* (staging is created fresh per attempt) and only the runner
knows the stop flag, the deadline and the run row it must report to. `_pg_connect` has none of them
and is also used by `describe`, where a 5-minute backoff would hang an HTTP request.

**Alternatives considered.** Retrying inside `_pg_connect` (drags stop/deadline into a low-level
function, and would make the structure scan hang); retrying the whole run from the worker (loses the
run row, duplicates the integration lock dance, and the next tick is already that fallback).

**Testability.** `sends.sleep`-style seams: the module reads the delays from a single function
`busy.delays(attempts, base)` and the runner takes `sleep=` in a keyword-only argument so a test
asserts the schedule without waiting minutes.

## R3 — The per-source ceiling, across threads and processes

**Decision.** A new module `backend/app/engine/source_slots.py`:

- `limit_of(source) -> int` — `settings["max_connections"]`, else `DEFAULTS[kind]`
  (`postgresql: 1`, `supabase: 2`, `rest`/`soap`: 4, they are HTTP calls, not sessions);
- `turn(key, limit, *, deadline, check, poll=0.5)` — a context manager holding a
  process-wide `threading.BoundedSemaphore((key, limit))` **and**, when a product-database connection
  is supplied by the caller, a cross-process advisory slot
  (`pg_try_advisory_lock(hashtextextended('source:' || key, 0))`, polled, released in `finally`);
- the same registry serves `runner`, `describe`, structure generation and `direct._permit`.

For runs the advisory slot is taken on the connection `run_integration` already opens for the
integration lock (`runner.py:667`), so a run holds **no extra** product connection. `describe` takes
the local semaphore only (an HTTP request that waits on a worker's slot would be worse than the
small overshoot).

**Why.** The reported incident is the origin running out of slots; a ceiling that only holds inside
one process would be a false promise the moment the API answers a describe while a run extracts. The
advisory lock is the pattern already used for integration locks and for direct-read slots
(`direct.py:487`), so it is the codebase's own idiom.

**Alternatives considered.** `psycopg_pool` per source (the pool bounds open connections, not
concurrent work, and the origin must stay read-only and short-lived); `MAX_PARALLEL` alone (per
installation, not per source — two integrations on the same ERP would still take two slots);
a global worker semaphore (same problem, and it would slow unrelated sources).

**Honest limit.** With more than one API replica the local semaphore is per replica. Documented in
`docs/INSTALL.md`; the run path (the one that caused the incident) is exact because of the advisory
lock.

## R4 — One origin connection per run, reused across datasets

**Decision.** `pg_copy`, `pg_rows` and `pg_all` gain an optional `conn=` keyword. When given they use
it and do not close it; when absent they open one through `_pg_connect` exactly as today. The runner
opens the run's connection once per attempt (inside the retry), tracks it with `cancel.track`, and
passes it to every dataset of the integration plus the reconcile check.

**Why.** Six datasets on one integration means six connect/disconnect cycles today; with a ceiling of
one per source each cycle is a chance to lose the lane to the ERP.

**Alternatives considered.** A connection pool per source (a pool keeps connections *open*, which is
the opposite of what an origin with a slot shortage wants); a module-level cache (leaks slots).

## R5 — Session options

**Decision.** In `_pg_connect`, the `options` string becomes

```
-c default_transaction_read_only=on
-c statement_timeout=<ms>
-c TimeZone=<tz>
-c idle_in_transaction_session_timeout=30000
-c idle_session_timeout=60000
```

`connect_timeout` is clamped to `min(current, 10)`. When the server rejects the options with
`InvalidParameterValue` / `CantChangeRuntimeParam` (PostgreSQL < 14 does not know
`idle_session_timeout`), the connection is retried once without the idle pair — the same
"tolerated when unsupported" shape `pg_copy` already uses for `BULK_SESSION`. `application_name`
becomes `bizview-engine:<integration id>` (or `bizview-engine:describe`), truncated to PostgreSQL's
63-byte `NAMEDATALEN` limit.

**Why.** A session that idles inside a transaction holds its slot all night — the exact "never hold a
slot it does not need" the constitution now says. `application_name` is the only attribution channel a
DBA has without granting extra privileges.

**Alternatives considered.** `ALTER ROLE … SET` (a change to the origin — forbidden by principle
III); no options at all (the current behaviour, which is what left sessions holding slots).

## R6 — The `skipped_busy` state and its record

**Decision.** `RUN_STATUSES` gains `"skipped_busy"`; migration `0055_source_connection_limits`
rewrites the CHECK constraint and adds `integration_run.busy JSONB NOT NULL DEFAULT '{}'` holding
`{"sqlstate": "53300", "attempts": 4, "waited_s": 285, "detail": "<redacted first line>"}`. The run's
message is the i18n key `run.busy` («La fuente no admite más conexiones ahora»), with the attempts and
the wait passed as parameters so the stored message renders in the reader's language — the same
mechanism `run.check_failed` already uses (`message_key` / `message_params`).

**Why a new state rather than reusing `skipped`.** `skipped` means "there was nothing to do" (source
disabled, already running); the concurrency of a busy origin is a different fact, and the run list
(badge, filter, the notification streak) needs to tell them apart. A column rather than reusing
`checks` because the retry schedule is not a check result and must survive independently.

**Alternatives considered.** `message_key = run.busy` with status `failed` (fails the amber/red
distinction the spec asks for and every monitoring query keeps counting a healthy hour as an error);
a separate `integration_busy` table (more rows for the same fact; the run already exists).

## R7 — Notification channel and throttle

**Decision.** `backend/app/engine/busy.py`:

- `streak(db, integration_id) -> int` — consecutive `skipped_busy` runs, newest first, stopping at
  the first run that is not;
- `notify_if_due(db, run, integration_id) -> bool` — when the streak reaches 3 and no
  `integration_busy` audit event exists after the streak's first run, send **one** Telegram message
  to every super user with a `TelegramLink` (the bot from `app/telegram`, no new dependency, no new
  setting) and record the audit event `integration_busy` with
  `{integration, streak, attempts, sqlstate}`. When the bot is not enabled or nobody is linked, the
  audit event is still recorded — the trail is the record, and the run list already shows the amber
  state.
- The streak resets on the next run of that integration that is not `skipped_busy` (success *or*
  failure), so a genuine defect does not get mistaken for congestion.

**Why Telegram.** It is the only outbound channel the product owns today with a per-person address
(`telegram_link`), and 013 never shipped a notification setting — inventing a mail path here would
mean a new mail purpose, a new template and a new opt-in, all outside this feature's scope. The
spec's Assumptions record the choice.

**Alternatives considered.** The 058 mail queue (needs a recipient policy and a purpose, and one
notification per streak per installation is not a mailing); a banner in the UI (no push, so it does
not meet "reaches the operators"); `smtplib` to `SMTP_FROM` (an installation may have no mail server,
which the product treats as normal).

## R8 — The quietest-hour hint

**Decision.** `busy.hint(db, integration_id)` returns `{"busy_today": n, "quiet_hour": h | null}` from
`integration_run.started_at` of the last 7 days: `busy_today` counts `skipped_busy` runs since local
midnight; `quiet_hour` is the hour (in the installation time zone) with the fewest `skipped_busy`
runs, and is only offered when `busy_today >= 3` and there are at least 2 distinct busy hours — a
single busy hour cannot rank the rest. Expressed through the existing `run_json` shape, so no new
endpoint.

**Why.** The owner's brief says "the quietest hour observed (from run history)"; the only observed
congestion signal the product has is when its own runs were refused.

**Alternatives considered.** Parsing the origin's activity history (privileges, cost, and a permission
the remedy section says the role may not have); a static suggestion ("run at 03:00") — a guess dressed
as data.
