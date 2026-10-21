# Quickstart — validating autonomous mode

A run guide, not an implementation guide. Each scenario names the success criterion it proves. Run it
against a throwaway installation: the scenarios create workspace versions.

## Prerequisites

- PostgreSQL reachable from the backend, `DATABASE_URL_BI` pointing at a database the app may write.
- `SUPER_USER_EMAIL` / `SUPER_USER_PASSWORD` in `.env` (the Asistente is super-user only).
- For the live scenario only: `AI_PROVIDER=openai_compatible` (DeepSeek), `AI_API_KEY`, and
  `AI_LIVE_TESTS=1` for the opt-in pytest eval. Every other scenario runs with `AI_PROVIDER=fake` or
  `none`; nothing here needs a paid call.
- `SECURITY_PROFILE=private` unless a scenario says otherwise.

```bash
python starter.py                  # installs, migrates (0024 included), runs backend + frontend
# open http://localhost:5173, sign in as the super user, open a project, open the Asistente
```

## Scenario 1 — One request, one applied version (US1, SC-001, SC-004, SC-008)

1. Composer chip (bottom right, next to the send arrow) → **Auto**. That is the whole authorisation:
   the run contract is created with the documented defaults (stages up to apply, every configured
   source, nothing existing modified, `auto_rollback`, no extra visibility).
2. Write: "dashboard de facturas por día y estado, actualizado cada hora, con PDF".
3. Send the message and do not touch anything else.

Expected: the transcript shows the contract line, then `Auto · /speckit-specify …`,
`/speckit-plan …`, `/speckit-tasks …`, `/speckit-implement …`, the preview and the apply as chips;
the status bar shows stage, tokens, previews/applies and elapsed time; the run ends with a summary
(version number, integration and report ids, schedule, decisions taken, preview rows, tokens) and
the pill reads **Auto · sin contrato**. `Administración → Workspace` lists the new version with
`source = chat:<id>:auto`.

Two-spec request (integration + report): repeat with "…y además un reporte de facturas por marca";
both specs must be implemented and applied in the same version (SC-008).

## Scenario 2 — Up to preview only (US3/AC1)

Contract with stage **hasta vista previa**. Expected: the run stops right after a successful preview,
the summary says so, nothing is applied, and the normal "Aplicar" button still works (014 US2).

## Scenario 3 — Stop and mode brake (US2, SC-002)

Start an Auto run, then either press **Detener** or switch the selector to **Editar**.
Expected: the current tool call ends, no apply happens afterwards, the draft and working state are
kept, the pill changes immediately, and `assistant_auto_run.stop_reason` is `stopped:user` or
`stopped:mode`.

## Scenario 4 — Limits (US2/AC2)

A run has no cap by default, so create the contract through the API with an explicit limit, e.g.
`POST /api/assistant/sessions/{id}/contract` with
`{"contract": {"goal": "…", "stages": ["draft","preview"], "limits": {"previews": 0}}}`.
Expected: the run stops with `limit:previews`, the summary lists what it reached, and the draft is
intact. The same holds for `tokens`, `applies` and `wall_clock_seconds`.

## Scenario 5 — Ask writes nothing (US6, SC-007)

Selector → **Preguntar**, then ask "crea un reporte de ventas". Expected: the refusal chip "Modo
Preguntar: cambia a Editar para escribir", no draft panel, and an answer describing what it would do.
`check_query` without a draft still works; `propose_draft`, `edit_draft`, `run_preview`,
`apply_draft` and any `/speckit-*` that writes are refused.

## Scenario 6 — Visibility (US4/AC3, FR-009)

After Scenario 1, open **Administración → Usuarios** for a `user`-role account: the new dashboard is
not in their list (`dashboard_access` has no row). Add it by hand — the normal 018 flow — and it
appears.

## Scenario 7 — Auto rollback (US4/AC1, SC-005)

Contract with `auto_rollback: true`, then break the first scheduled run on purpose (pause the source,
or seed a failing check in the integration's `checks`). Expected: within one scheduler cycle the
conversation receives a system message, the previous version is active again, and the audit has
`assistant_run_rolled_back`; `assistant_auto_run.watch_state = 'rolled_back'`.

## Scenario 8 — Automated suites

```bash
cd backend  && uv run ruff check app tests alembic && uv run pytest
cd cli      && uv run ruff check . && uv run pytest
cd frontend && npx tsc --noEmit -p . && npm test && npm run build && npm run check:compat
cd frontend && npx playwright install && npm run e2e
```

Focused checks while working on this feature:

```bash
cd backend && uv run pytest tests/test_assistant_auto_mode.py tests/test_assistant_auto_contract.py \
    tests/test_assistant_auto_loop.py tests/test_assistant_auto_apply.py -q
cd frontend && npx vitest run tests/unit/modeSelector.test.ts tests/unit/runContract.test.ts
cd backend && AI_LIVE_TESTS=1 uv run pytest tests/test_live_auto_run.py -q   # SC-001, opt-in
```

Expected: no test needs a live provider; the fake provider replays the recorded runs, including the
session-18 fixture (integration 001 + report 002) under Auto, and the adversarial suite proves 0 tool
calls outside the contract succeed (SC-003).

## Troubleshooting

- **The contract is not created** — `contract_invalid` names the offending field. With
  `AI_AUTO_REQUIRE_STEP_UP=1`, `step_up_failed` means a wrong password or TOTP and the
  `/auth/reauth` throttling and lockout apply.
- **`contract_required` from `run_preview`/`apply_draft`** — the contract is spent (a previous run
  used it); confirm a new one, which is the intended one-contract-per-run rule.
- **The run ends `blocked:spec_not_found`** — the request names no spec and none exists yet; give the
  id/number in the message or expect `/speckit-specify` to create it first.
- **Nothing applied although preview passed** — check the contract stages (`apply` must be allowed)
  and `limits.applies` if a profile set one.
