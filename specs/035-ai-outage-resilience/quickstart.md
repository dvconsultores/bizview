# Quickstart: proving an AI outage is survivable

Prerequisites: the backend suite's environment (`.env` with the test database), `backend/.venv`,
`cd cli && uv sync`, `cd frontend && npm ci`. **No live AI provider is contacted by anything here.**

## 1. Codes and texts (backend, fast)

```bash
cd backend && .venv/bin/python -m pytest tests/test_ai.py tests/test_i18n_core.py -q
```

Expected: the mapping table test walks every code of `contracts/provider-errors.md` against the
recorded bodies (DeepSeek 402/400, Anthropic 429 with `retry-after`, OpenAI 500) and asserts a
translated text and the right `action` for each; `test_ai.py` also asserts the provider's message is
redacted and capped at 300 characters.

## 2. AI status and health

```bash
cd backend && .venv/bin/python -m pytest tests/test_ai_status.py tests/test_health_ai.py -q
curl -s localhost:8000/api/health | jq .ai     # with the app running
```

Expected: after a recorded 402 the block reads `last_error_code: "no_credit"` and `last_ok_at`
older (or null); after a success it reads `last_ok_at` newer and `last_error_code: null`; the key
never appears. The Administración home pill shows the same state (vitest:
`tests/unit/admin-home.test.tsx`).

## 3. Auto does not knock on a dead door

```bash
cd backend && .venv/bin/python -m pytest tests/test_assistant_ai_outage.py -q
```

Expected: with a `MockTransport` spy — a contract confirmation while `no_credit` is recorded makes
**0** provider calls and answers the refusal; a run that fails twice with the same code stops with
`stop_reason == "blocked:ai_no_credit"`, keeps `working_state` and the draft on disk; a single
`rate_limited` is retried once (2 calls) and a second one stops; a message «continua» while blocked
makes 0 calls.

## 4. The session-23 fix with the AI down

```bash
cd cli && uv run pytest tests/test_validate.py -q -k "fix or join"
cd backend && .venv/bin/python -m pytest tests/test_project_fixes.py -q
```

Expected: the fixture report without `joins` publishes an `unjoined_sets` problem with `fix_data`
(append `/joins`); `POST /api/projects/coinmarketcap/fix` applies it, validation goes **1 → 0**, the
response carries the diff and the new validation, and the provider is never called. A stale
`base_sha256` answers `409 fix_stale` and writes nothing.

## 5. Interface

```bash
cd frontend && npx vitest run tests/unit/provider-error.test.tsx tests/unit/problems-fix.test.tsx \
  tests/unit/admin-ai.test.tsx
```

Expected: the error bubble shows code, provider text, provider/model, the action and a collapsible
**Detalles técnicos** with the log command and the timestamp; the problems panel shows
**Aplicar arreglo** only for problems with `fix_data`, and **Aplicar todos los arreglos** when there
are two or more.

## 6. Manual end-to-end (one installation)

1. Point `AI_BASE_URL` at a stub that answers 402 (or set `AI_PROVIDER=fake` and force the code).
2. Send a message: the bubble names `no_credit` and links to Administración → IA; the composer pill
   shows the same.
3. Press **Probar**: the card shows the code, the provider's answer, the details block and — with an
   OpenAI-compatible endpoint — the models list with the configured one marked.
4. Open a project with a fixable problem, press **Aplicar arreglo**: the diff appears, the problem
   disappears, and **Aplicar** becomes available. Nothing above needed the provider.
