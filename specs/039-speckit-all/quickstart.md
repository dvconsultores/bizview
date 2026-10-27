# Quickstart: validating `/speckit-all` (039)

Runnable scenarios that prove the feature end to end. The contract is in
[contracts/speckit-all.md](./contracts/speckit-all.md); the data shapes are in
[data-model.md](./data-model.md). Nothing here duplicates them.

## Prerequisites

```bash
# backend: DATABASE_URL_BI must point at the external test database (backend/tests/conftest.py)
cd backend && uv sync

# frontend
cd frontend && npm ci

# the fake provider replays recorded runs; no key is needed for the scenarios below
```

## 1. The command exists and is scoped (no provider call)

```bash
cd backend && uv run pytest tests/test_assistant_commands_registry.py -q
```

Expected: `speckit-all` and `speckit-verify` are in `REGISTRY` and in the `/` menu, both prompt files
exist in `es`/`en`, and `speckit-all.writes == ("run_report", "decisions_append")`.

## 2. Pipeline mechanics (no provider call)

```bash
cd backend && uv run pytest tests/test_assistant_speckit_all.py -q
```

Expected, one test each:

- `--until tasks` stops after stage 4 and writes `run-report.md` with 4 rows.
- `--until nonsense` → `422 commands.until_invalid` listing the 8 stages.
- `run_command speckit-plan` while `cursor == 0` → `pipeline.order`; after `--until tasks` →
  `pipeline.until`; `run_command speckit-all` inside a pipeline → `pipeline.no_restart`.
- resume: a spec with `spec.md` + `plan.md` starts at `tasks`; `--force` starts at `specify`.
- `decisions_append` accepts an added line, refuses a changed line and a change outside the section.
- `/speckit-all` in `ask` → `assistant.mode.offer_auto`, `command_runs` empty.

## 3. One request → both specs → "Listo para aplicar" (recorded provider)

```bash
cd backend && uv run pytest tests/test_assistant_speckit_all_run.py -q
```

Expected: from the session-18 recording, an integration spec and a report spec are created, the 8
stages run per spec in order, the preview succeeds, and the last message carries the run-report card
with **no** user message between the contract and the end (SC-002, SC-003). The same test stops the
run with `limits.tokens` at stage 5 and resumes it with `/speckit-all <id>` from stage 5 (SC-004).

## 4. Verify is real

```bash
cd backend && uv run pytest tests/test_assistant_speckit_all.py -q -k verify
```

Expected: verify runs the validation, a `check_query` per query/request file of **that** spec, one
preview, and the per-story checks; a failing view is recorded per story and the pipeline stops with
`verify:failed` when the cycle cap is reached.

## 5. The two toolchains ship the same contract

```bash
cd backend && uv run pytest tests/test_speckit_all_contract.py -q
```

Expected: the `<!-- bizview:contrato-autonomo -->` block is byte-identical in the ES prompt, the EN
prompt and `.claude/skills/speckit-all/SKILL.md`, and every stage list equals `pipeline.STAGES`
(SC-006, drift half).

## 6. Frontend surfaces

```bash
cd frontend && npx tsc --noEmit -p . && npm test -- RunReportCard CommandRunChip ModeSelector
```

Expected: the chip shows `3/8`, the status bar shows `Etapa 4/8 · analyze`, the card renders the
stages/decisions/verify table and hides "Pendiente para el humano" when it is empty.

## 7. Manual run in the app (one real provider call)

1. Open a project conversation, switch to **Auto**, type
   `/speckit-all Tablero de facturas por día y estado, actualizado cada hora, con PDF`.
2. Confirm the contract; do not answer anything else.
3. Expected: 8 chips per spec, the two spec folders, `run-report.md` in each, and
   **Listo para aplicar** (or **Aplicado · versión N** when the contract allows `apply`).
   Nothing to do for the human except pressing **Aplicar** when the contract does not.
4. With `--until tasks`: the same, stopping after the tasks chip (the documented dry run).

## 8. Opt-in live eval (SC-001, SC-002)

```bash
cd backend && AI_LIVE_TESTS=1 uv run pytest tests/live/test_speckit_all_live.py -q
```

Expected: ≥ 4 of 5 runs reach "Listo para aplicar" with 0 user messages after the contract within
the default limits.

## Regression gate before merging

```bash
cd backend  && uv run ruff check app tests alembic && uv run pytest
cd frontend && npx tsc --noEmit -p . && npm test && npm run build
```
