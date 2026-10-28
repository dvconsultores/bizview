# Implementation Plan: `/speckit-all` hardening (040)

**Feature**: `040-speckit-all-hardening` · [spec.md](./spec.md) · [tasks.md](./tasks.md)

## Technical context

| | |
|---|---|
| Pipeline | `app/assistant/commands/pipeline.py` (cursor, `next_stage`), `app/assistant/tools.py` (`_run_command`, `_plan_position`) |
| Runs | `app/assistant/commands/runs.py` (`create`, `end_from_activity`, tick guard) |
| Guard | `app/assistant/commands/guard.py` (`tasks_ticks`, `Context`) |
| Loop | `app/assistant/service.py` (`_loop`: compression, stage context, budgets, integrity mapping) |
| Tools | `app/assistant/tools.py` (`TOOL_SPECS`, `offered_tool_specs`, groups) |
| Fixes | `cli/bizview_cli/{validate,fixops,i18n}.py`, `app/projects/fixes.py` |
| Data defects | `app/assistant/origin.py` (`check_request`), `cli/bizview_cli/validate.py`, `app/engine/extract.py` |
| Storage | no migration: the cursor, the compression key and `tokens_per_stage` ride in JSONB columns |

## Decisions

1. **`next_stage()` owns every transition.** `advance()` keeps the stored cursor shape, but the
   target is computed from evidence: the newest converge/verify run of the spec, `tasks.md` and the
   round counters. `_plan_position` asks it and refuses only what the state machine cannot reach.
2. **The compression key lives in `working_state`.** `{"run": <id>, "n": 1, "freed": [pct]}` is
   written in the same transaction as the summary message; a crash between them cannot duplicate it
   because the message is only added inside the same round commit.
3. **Stage scoping uses message ids.** A stage's context is the rows stored after its opening
   message plus the `✔ <stage> — …` line of the previous stage, which the product writes when a
   stage run ends.
4. **Tool groups are data.** `TOOL_GROUPS` maps a stage/command to the names it may be sent;
   `get_app_guide(topic)` is the only guide entry point (already true; a test locks the count).
5. **`--only` is enforced where ticks are checked**, so the flag is not advice either.
6. **Timestamp units are inferred by `check_request`** from the sample value and stored in the
   integration schema; the validator checks the declared unit against the mapped value's range.

## Constitution check

VIII: the stage scoping removes old tool results; no new input. IX: no fix edits status or
evidence; ticking stays inside implement and needs the artifact. V: no new dependency and no
migration (JSONB only).

## Rollout

1. Step 0 (integrity mapping + flush order) — smallest, unblocks the diagnosis of anything else.
2. State machine + `--only` + tick guard + fix registry.
3. Compression + stage context.
4. Tool groups + per-stage ceiling + report fields.
5. The two data defects + the CoinMarketCap fixture.
6. Docs (033 topics, repo `/speckit.all`) and CHANGELOG.
