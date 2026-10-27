# Implementation Plan: `/speckit-all` — one command runs a feature end to end (039)

**Feature**: `039-speckit-all` · [spec.md](./spec.md) · [tasks.md](./tasks.md) ·
[research.md](./research.md) · [data-model.md](./data-model.md) ·
[contracts/speckit-all.md](./contracts/speckit-all.md) · [quickstart.md](./quickstart.md)

## Technical context

| | |
|---|---|
| Backend | FastAPI + SQLAlchemy. Command registry `app/assistant/commands/registry.py`, guard `guard.py`, run lifecycle `runs.py`, provider loop `app/assistant/service.py`, tools `tools.py`, contract `auto.py` |
| Storage | **No migration**: the pipeline cursor rides in `assistant_command_run.result` (JSONB); `command ~ '^(speckit-[a-z]+|ayuda)$'` already accepts `speckit-all` and `speckit-verify` (0023) |
| Stage detection | `app/projects/specs.py` `stage()`/`list_specs()` (especificada → aclarada → planificada → tareas → implementada → aplicada) + `revised_by()` + `converged()` |
| Verify | `origin.check_query`, `assistant/preview.run_draft_preview`, `assistant/readiness.py`, `session.validation` |
| Frontend | React 19 + Tailwind: `CommandRunChip.tsx`, `ModeSelector.tsx`, `AssistantChat.tsx`, `api/types.ts`, `i18n/{es,en}.ts` |
| Prompts | `cli/bizview_cli/workspace_template/agent_commands/{es,en}/speckit-all.md` and `speckit-verify.md` (product); `.claude/skills/speckit-all/SKILL.md` (repo toolchain) |
| Tests | pytest (`test_assistant_commands_*`, new `test_assistant_speckit_all*`), vitest (chip/status bar), opt-in `tests/live` for SC-001/SC-002 |

## Baseline (what already exists — do not rebuild)

- **021**: `REGISTRY`, front-matter-driven `/` menu, per-command tool and write scopes
  (`guard.py`), gates (`runs.preflight`), chips (`CommandRunChip`), `finish_command`.
- **028**: mode (`ask|edit|auto`), `RunContract` (stages/limits/sources), `run_command` switching
  the turn to a stage without a nested provider loop, `assistant.auto.next_stage` hint, Auto
  answering gates (`_approve_without_asking`), `auto.limit_refusal`.
- **029**: `resolve.resolve` + `resolve.strip_force` (argument > number > title > current),
  `set_current_spec`, `_idempotence`, `misrouted` runs, `guard.path_other_spec`.
- **035/036/037/038**: provider error codes and deterministic fixes, replayable history,
  project isolation (`fs.ProjectPathError`, per-project advisory lock), render/validation codes.

## Constitution check

- **IV (separated concerns)** — the pipeline is one module (`app/assistant/commands/pipeline.py`)
  plus prompt files; the repo toolchain command lives in `.claude/skills/`; no logic in `deploy/`
  or `cli/` beyond the prompt data it already owns. **PASS**.
- **V (fixed stack)** — no new dependency; no new provider input. **PASS**.
- **VIII (AI optional and private)** — the pipeline sends exactly what 021/028 already send
  (documents inside untrusted-data blocks, source *profiles* through the authoring tools). The
  decision log and the run report are written by product code from identifiers and fixed reason
  tokens; no value from a query result is added. **PASS**.
- **IX (spec-driven reporting)** — every stage still writes a complete spec through the existing
  command scopes; nothing is loaded, run or shown without validation; the apply still goes through
  the contract (028), so the human authorises once, up front. **PASS**.
- **Constraints** — no new column (no Alembic revision needed); worker untouched; origin stays
  read-only (`check_query`/preview are the existing read-only paths). **PASS**.

Verdict: **PASS**, no amendment, no complexity tracking.

## Decisions

1. **The command is a stage driver, not a new engine.** `speckit-all` is a `CommandDef` whose
   write scope is only the report and the decision log; every stage it runs is a *real* command
   run created through `_run_command` (028 FR-004), so the audit trail, the per-stage guard, the
   chip and the token ceiling are the ones 021 already enforces. Its own prompt states the plan;
   product code enforces the order.
2. **One stage list, in code** (`pipeline.STAGES`): `specify · clarify · plan · tasks · analyze ·
   implement · converge · verify`. The prompt, the `--until` parser, the status bar and the repo
   skill all read it; a test fails if the prompt files and `STAGES` disagree.
3. **`verify` is a stage, not a prompt-only step** (`speckit-verify`, new registry entry). It owns
   `check_query` + `run_preview` and no writer, so its work is deterministic: validation,
   `check_query`/`check_request` on every query and request of the spec's integrations, one preview
   (charged to the contract), and the per-story checks of US4. It is also usable alone to re-check
   a spec. Fixing a failure is `run_command` back to `implement`/`converge`; the loop is capped at
   3 cycles in `pipeline` state, not in the prompt.
4. **No schema change.** The pipeline cursor (`{"id","stages","cursor","until","specs",
   "spec_index","round","verify_cycles"}`) lives in `assistant_command_run.result.pipeline` and is
   copied forward by every stage run. `_run_json` exposes `pipeline` so the status bar renders
   `Etapa i/8` without another endpoint. Resume is "read the newest run with a `pipeline` block".
5. **Resume is stage detection first, cursor second.** A `/speckit-all <id>` without a previous
   pipeline derives the first incomplete stage from `specs.stage()`/`revised_by`/`converged`
   (029), so a spec built by hand resumes too; when a cursor exists it wins only for the stages the
   artifacts cannot prove (analyze writes nothing). `--force` reopens every stage.
6. **Two specs run in dependency order**: integration specs (`kind: integracion`) through
   implement + verify, then report specs; `session.current_spec` follows with the existing
   `set_current_spec` path (029). A brief that only needs a report reuses a matching integration
   (014) and creates one spec (`MAX_NEW_SPECS = 3` already allows a two-spec brief in one
   `speckit-specify` run).
7. **Order is enforced, not suggested.** `_run_command` refuses (tool error, one line) a stage that
   is not the pipeline's next one, a stage after `--until`, and any stage once the contract's
   `draft` permission is gone. The model can never "jump" a stage or restart the pipeline with
   `run_command speckit-all`.
8. **Decisions are append-only data.** Guard rule `decisions_append`: the diff may only add lines
   to the `## Decisiones tomadas (modo autónomo)` section of `specs/<spec>/spec.md` (both texts
   compared with that section removed, and the new section must extend the old one). Format
   `- [stage] decision — why`. The same lines go to the report.
9. **The report is product-written.** `pipeline.write_report()` renders
   `specs/<spec>/run-report.md` from the runs, the decisions and the verify result at the moment
   the pipeline ends (stop, `--until`, or apply), through `fs.apply_ops` under guard rule
   `run_report`; the card is `tool_payload={"run_report": {...}}` on the last assistant message.
   Because the model never writes it, SC-003 and SC-005 are checkable on a fixture.
10. **Stop conditions are code, not prompt text**: contract limits (`auto.limit_refusal`), stage
    permission, provider codes (035 map in `_provider_error`), verify cycle cap, and the two
    content conditions the product can prove — a specify that needs a source that is not enabled
    (014/037) and a constitution conflict raised by the guard. Each writes one `stop_reason` line
    and the report.
11. **Mode gate is deterministic**: `/speckit-all` in `ask`/`edit` returns the existing
    `assistant.mode.offer_auto` ("Pasar a Auto") reply with a suggestion chip and creates no run
    (text never switches the mode — 028). In `auto`, `ensure_auto_contract` opens the contract as
    today; there is no extra confirmation.
12. **One source of truth for the contract wording**: the autonomy block lives between
    `<!-- bizview:contrato-autonomo -->` markers in the ES and EN prompt files and in
    `.claude/skills/speckit-all/SKILL.md`. Wording is per locale; what the drift test
    (`test_speckit_all_contract.py`) enforces is the same markers, the same six rules, the same
    byte-identical stage line (also present in this contract) and the same decision heading.

## File map

Backend

- `app/assistant/commands/pipeline.py` (new) — `STAGES`, `parse_args`, `remaining`, `next_stage`,
  `completed`, `state_of`/`record`, `verify`, `decisions_block`, `write_report`, `stop_reason`.
- `app/assistant/commands/registry.py` — `speckit-all` and `speckit-verify` definitions, menu order.
- `app/assistant/commands/guard.py` — rules `run_report` and `decisions_append` (+ hints).
- `app/assistant/commands/runs.py` — carry `pipeline` through `create`/`resume_info`.
- `app/assistant/tools.py` — `run_command` enum + pipeline order check; `_STAGE_OF_COMMAND` gains
  `speckit-verify`; `finish_command` on a pipeline run writes the report.
- `app/assistant/service.py` — `/speckit-all` mode gate, `reserved_number` for the pipeline's
  specify, pipeline block in the state text, `_run_json` pipeline, `_NEXT_AFTER` untouched.
- `app/assistant/auto.py` — `next_stage` hint carries `i/8`; no contract change.
- `app/i18n/{es,en}.py` — `commands.speckit_all_*`, `pipeline.*`, `commands.until_invalid`.
- `cli/bizview_cli/workspace_template/agent_commands/{es,en}/speckit-all.md`, `speckit-verify.md`.

Frontend

- `src/components/assistant/CommandRunChip.tsx` — stage position on a pipeline chip.
- `src/components/assistant/ModeSelector.tsx` — `Etapa i/8` next to the contract counters.
- `src/components/assistant/RunReportCard.tsx` (new) — the report card (stages, decisions,
  verify, tokens, pending for the human).
- `src/api/types.ts`, `src/i18n/{es,en}.ts`.

Repo toolchain

- `.claude/skills/speckit-all/SKILL.md` (new) — same stages and contract, `.specify/scripts/bash/*`
  plus `pytest`/`npm run build` for verify instead of product tools.

Tests

- `backend/tests/test_assistant_speckit_all.py` — parse (`--until`, `--force`), order enforcement,
  decisions guard, report contents, resume per stage (SC-004), verify's checks and per-story
  verdicts.
- `backend/tests/test_assistant_speckit_all_run.py` — recorded provider: the plan through the dry
  run, "0 user messages" after the contract, the report card, and the analyze repair rewind.
- `backend/tests/test_speckit_all_contract.py` — the shared contract and stage list (SC-006).
- `backend/tests/test_assistant_commands_registry.py` — both prompts exist in ES/EN, front matter,
  menu order.
- `backend/tests/test_speckit_all_contract.py` — contract block identical across ES/EN/skill and
  stage list equal to `STAGES` (SC-006's drift half).
- `frontend/src/components/assistant/__tests__/RunReportCard.test.tsx`, chip/status bar specs.
- `backend/tests/live/test_speckit_all_live.py` (opt-in) — SC-001 (≥4/5) and SC-002.

## Notes for implementation (found while reading the code)

1. **`RUNS_IN_SESSION = 20`** (`commands/runs.py`) is smaller than a two-spec pipeline
   (`2 × 8` stage runs + the opening run + gate runs). `_command_json` must keep every run of the
   current `pipeline.id` even past the window, or the chips of the first spec vanish mid-run.
2. **`_run_command` finishes the current run** before creating the stage run. For a pipeline that
   is `speckit-all`'s own run → stage 1; the cursor must be written to the **new** run before the
   finish, and the parent keeps its copy so `/speckit-all <id>` can still read it.
3. **`speckit-verify` must be in `run_command`'s enum** and in `_STAGE_OF_COMMAND`, or the stage
   cannot be opened and the auto run's `stage` column stays at the previous value (028 shows it in
   `run_json`).
4. **`specs.stage()` is cached nowhere**: `list_specs` reads every `.md` of the project per call.
   The pipeline reads it once per transition (`remaining`), not per tool call, as `_spec_rows` does.
5. **Dependency check** (research R7): 028, 029 and 037 are in the tree; 029 has no folder under
   `specs/` although its code is deployed. The gates are their tests, not their spec folders.

## Out of scope

- Extra or project-specific stages (hooks); the list is fixed (spec Assumptions).
- Any change to the apply path, the readiness gate or the preview engine.
- Parallel stage execution, or running two specs of one pipeline in one stage run.
- Auto-editing the constitution: a constitution conflict stops the run (US3 AC4).
