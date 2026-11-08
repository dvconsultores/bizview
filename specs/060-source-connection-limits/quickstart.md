# Quickstart — 060-source-connection-limits

How to prove the feature end to end. Prerequisites: the backend venv (`backend/.venv`), `DATABASE_URL_BI`
in `.env` (the tests build their own `app_test_*` schema), Node for the frontend suite.

## 1. Unit and backend tests

```sh
cd backend && .venv/bin/pytest tests/test_source_busy.py tests/test_source_slots.py \
    tests/test_run_skipped_busy.py -q
```

Expected: the classifier recognises every SQLSTATE and pooler wording; the retry schedule is
`15 s, 45 s, 2 min, 5 min` with the base from settings; a run that exhausts them ends `skipped_busy`
with the datasets and `data_version` untouched; the third consecutive one writes exactly one
`integration_busy` audit event.

```sh
cd backend && .venv/bin/pytest tests/test_run_integration.py -q      # no regression on the happy path
```

## 2. The ceiling

```sh
cd backend && .venv/bin/pytest tests/test_source_slots.py -q
```

Proves: two tasks on one source with `max_connections: 1` never overlap; a `describe` waits for the
permit; a cancelled waiter releases it; the advisory slot is released on every exit path.

## 3. Session options and naming

```sh
cd backend && .venv/bin/pytest tests/test_extract_session.py -q
```

Proves: `application_name` is `bizview-engine:<integration>`; the idle timeouts are present when the
server accepts them and the connection still works when it does not; `connect_timeout` is 10 s.

## 4. Frontend

```sh
cd frontend && npx tsc --noEmit && npx vitest run tests/unit/integration-busy.test.tsx
```

Proves: the amber badge, «4 intentos, 7 min», the «Qué hacer» link to the help topic, the quiet-hour
hint, and the two test-connection counts (including "sin permiso para verlo").

## 5. Documentation gates

```sh
python3 scripts/check_docs_parity.py     # the new help topic pair and INSTALL/es/INSTALL stay in step
sh scripts/gates/all.sh                  # vocabulary, dead code, routes, settings, version, markdown
```

## 6. Manual proof against a real origin (optional, ten minutes)

On a scratch PostgreSQL origin:

```sql
-- as a superuser
ALTER SYSTEM SET max_connections = 3;   -- restart
```

1. Open three `psql` sessions and keep them idle. They now hold every slot except the reserved ones.
2. In Bizview, run the integration whose source is that origin.
3. Expected: the run waits, retries, and ends **amber** with «La fuente no admite más conexiones
   ahora» and «4 intentos, 7 min»; the dashboard keeps its numbers and its previous "Datos
   actualizados" time.
4. On the origin: `SELECT application_name, state FROM pg_stat_activity;` shows no Bizview session
   while the run waits, and `bizview-engine:<integration>` while it works.
5. Close one `psql` session and press **Ejecutar ahora**: the run succeeds and the amber run stays in
   the history.

## 7. What a reviewer should refuse to accept

- A `skipped_busy` run that changed `data_version` or replaced rows.
- A message that names the origin's host, port or user.
- A retry schedule that ignores a stop request for more than a couple of seconds.
- Two simultaneous Bizview sessions on a source whose ceiling is one.
- A notification on the fourth consecutive busy run of the same streak.
