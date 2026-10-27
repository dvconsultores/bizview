# Tasks: `/speckit-all` — one command runs a feature end to end (039)

**Feature**: `039-speckit-all` · [spec.md](./spec.md) · [plan.md](./plan.md) ·
[data-model.md](./data-model.md) · [contracts/speckit-all.md](./contracts/speckit-all.md) ·
[research.md](./research.md) · [quickstart.md](./quickstart.md)

**Tests**: requested by the spec itself (SC-001…SC-006 are automated checks), so every story ships
with its tests. Backend tests run on `DATABASE_URL_BI` inside a temporary schema
(`backend/tests/conftest.py`).

**Path conventions**: `backend/app/...`, `backend/tests/...`, `frontend/src/...`,
`cli/bizview_cli/workspace_template/...`, `.claude/skills/...`.

---

## Phase 1 — Setup (shared scaffolding)

**Purpose**: the empty shapes every later task fills; no behaviour yet.

- [X] T001 Create `backend/app/assistant/commands/pipeline.py` with the module docstring and
      `STAGES = ("specify", "clarify", "plan", "tasks", "analyze", "implement", "converge",
      "verify")` plus `STAGE_COMMANDS` mapping each stage to its registry name
      (`speckit-specify`, …, `speckit-verify`); order is fixed and never reordered at runtime.
- [X] T002 [P] Add prompt skeletons with front matter (`description`, `argument_hint`, `source`)
      in `cli/bizview_cli/workspace_template/agent_commands/es/speckit-all.md`,
      `.../es/speckit-verify.md`, and the `en/` pair.
- [X] T003 [P] Add empty i18n namespaces `pipeline.*` and `commands.speckit_all_*` to
      `backend/app/i18n/es.py`, `backend/app/i18n/en.py`, `frontend/src/i18n/es.ts`,
      `frontend/src/i18n/en.ts` (no unused key left at the end: T045 fills them).

---

## Phase 2 — Foundational (blocks every story)

**Purpose**: the command exists, is scoped, parses its arguments and knows where it is in the plan.

- [X] T004 `backend/app/assistant/commands/registry.py`: register `speckit-all` — `needs_spec=False`,
      `needs_args=True`, `interactive=False`, `provider=True`, `tools={"edit_draft"}`,
      `writes=("run_report", "decisions_append")`, `reads=("constitution", *_ALL_DOCS)`,
      `prereqs=()`; place it first in the menu (`REGISTRY` order).
- [X] T005 `backend/app/assistant/commands/registry.py`: register `speckit-verify` — `needs_spec=True`,
      `needs_args=False`, `interactive=False`, `provider=True`,
      `tools={"check_query", "run_preview"}`, `writes=()`, `prereqs=("spec", "plan", "tasks")`.
- [X] T006 [P] `backend/app/assistant/commands/guard.py`: add rule `run_report` — only
      `op == "write"` on `specs/<spec>/run-report.md`, refused when `ctx.spec` is None; add its
      `hints()` line.
- [X] T007 [P] `backend/app/assistant/commands/guard.py`: add rule `decisions_append` — only
      `specs/<spec>/spec.md`, only inside `## Decisiones tomadas (modo autónomo)`: compare both
      texts with that section removed (must be identical) and require the new section to extend the
      old one; each added line matches `- \[<stage>\] … — …` with `<stage>` in `STAGES`
      (data-model §5).
- [X] T008 `backend/app/assistant/commands/runs.py`: carry the pipeline forward —
      `create(..., pipeline: dict | None = None)` stores `pipeline.PIPELINE_KEY` in `result`, which
      is what `pipeline.state_of` reads back on the next stage (an interrupted run keeps its
      cursor).
- [X] T009 `backend/app/assistant/commands/pipeline.py`: `PipelineArgs` + `parse_args(arguments)` —
      strip `--force` with `resolve.strip_force`, read `--until <stage>` (case-insensitive, value in
      `STAGES`, the named stage is **included**), and raise
      `ApiError(422, "until_invalid", …)` for anything else, listing the eight stages
      (contract §1).
- [X] T010 `backend/app/assistant/commands/pipeline.py`: `state_of(runs)` reads the newest
      `assistant_command_run` whose `result.pipeline` exists; validate it against the invariants
      `0 ≤ cursor ≤ 8`, `until ∈ STAGES ∪ {None}`, `0 ≤ spec_index < len(specs)`, `0 ≤ round ≤ 2`,
      `0 ≤ verify_cycles ≤ 3`; a stored `stages` that differs from `STAGES` is rewritten.
- [X] T011 `backend/app/assistant/commands/pipeline.py`: `completed(spec, …)` per data-model §4 —
      `specify` = `spec.md` exists; `clarify` = `specs.stage()` ≥ `aclarada` or
      `revised_by(spec.md, "speckit-clarify")` and no `[NEEDS CLARIFICATION` remains; `plan` =
      `plan.md`; `tasks` = `tasks.md`; `analyze` = cursor > 4 or recorded in the report;
      `implement` = stage ∈ {`implementada`, `aplicada`}; `converge` = `specs.converged()` is false;
      `verify` = `session.validation.valid` and the last preview for the spec is `succeeded`.
- [X] T012 `backend/app/assistant/commands/pipeline.py`: `next_position(...)`/`open_stage(...)`/`detect(...)` — order
      specs by kind (`integracion` before `reporte`) then number; skip completed stages unless
      `force`; stop at `until`; return `None` when the plan is done.
- [X] T013 `backend/app/assistant/tools.py` `_run_command`: add `speckit-verify` to the `command`
      enum; refuse a stage that is not `cursor` (`pipeline.order`), a stage after `until`
      (`pipeline.until`) and `speckit-all` inside a pipeline (`pipeline.no_restart`); write the
      advanced `pipeline` into the **new** run before finishing the current one; add
      `speckit-verify` to `_STAGE_OF_COMMAND`.
- [X] T014 `backend/app/assistant/service.py` `_command_turn`: deterministic mode gate — when
      `definition.name == "speckit-all"` and `auto.mode_of(session) != "auto"`, return
      `assistant.mode.offer_auto` plus `_suggestion("speckit-all", …)` and create **no** run.
- [X] T015 `backend/app/assistant/service.py`: reserve the spec number for `speckit-all` like
      `speckit-specify` (`reserved_number=view.next_spec()`) and seed
      `result.pipeline = {"id": None, "stages": list(STAGES), "cursor": 0, "until": args.until,
      "specs": [], "spec_index": 0, "round": 0, "verify_cycles": 0}` with `id` set to the run id
      after flush.
- [X] T016 `backend/app/assistant/service.py` `_run_json`: expose
      `"pipeline": {"id","cursor","total","stage","until","spec","spec_index"}` (contract §6).
- [X] T017 `backend/app/assistant/service.py` (`mode_block`/`state_text`): add the pipeline block —
      `Etapa {i}/8 · {stage}`, the remaining stages and `until` — so the model knows where it is
      without re-reading the plan.
- [X] T018 `backend/tests/test_assistant_commands_registry.py`: assert both prompts exist in `es`
      and `en` with front matter, `speckit-all`/`speckit-verify` are in `REGISTRY` and in the menu
      order, and `speckit-all.writes == ("run_report", "decisions_append")`.

**Checkpoint**: `/speckit-all` is accepted, scoped and positioned; stages cannot be skipped.

---

## Phase 3 — User Story 1: one command, a finished report (P1) 🎯 MVP

**Goal**: `/speckit-all <request>` runs the eight stages for the spec(s) it creates and ends with a
run report and "Listo para aplicar", with no question after the contract.

**Independent Test**: `backend/tests/test_assistant_speckit_all_run.py` replays the session-18
recording and reaches "Listo para aplicar" with zero user messages after the contract.

- [X] T019 [US1] `cli/bizview_cli/workspace_template/agent_commands/es/speckit-all.md`: write the
      stage plan, the "advance with `run_command`, never ask" rule, `--until`/`--force` semantics
      and the autonomy block between `<!-- bizview:contrato-autonomo -->` markers (contract §4).
- [X] T020 [P] [US1] `.../agent_commands/en/speckit-all.md`: the same content in English, with the
      block byte-identical to T019.
- [X] T021 [US1] `backend/app/assistant/commands/pipeline.py` `write_report()`: render
      `specs/<spec>/run-report.md` exactly as data-model §6 (run line, stages table, decisions,
      verification table, pending for the human — section omitted when empty); the same inputs
      produce identical bytes.
- [X] T022 [US1] `backend/app/assistant/tools.py` (`finish_command` and the end-of-turn path):
      when the pipeline's cursor is 8 or `until` was reached, write the report through
      `fs.apply_ops` under rule `run_report` and attach
      `tool_payload={"run_report": {...}}` (data-model §7) to the last assistant message.
- [X] T023 [US1] `backend/app/assistant/commands/pipeline.py` + `tools.py`: `set_current_spec` to the
      next spec when a spec's stage 8 completes, advancing `spec_index` and resetting
      `round`/`verify_cycles` to 0 (data-model §1).
- [X] T024 [P] [US1] `frontend/src/api/types.ts`: add `Pipeline` and `RunReport` types matching
      `_run_json` and the card payload.
- [X] T025 [P] [US1] `frontend/src/components/assistant/RunReportCard.tsx`: the report card
      (stages, decisions, verification, tokens, pending); hide "Pendiente para el humano" when the
      list is empty. Wire it in `AssistantChat.tsx` from `tool_payload.run_report`.
- [X] T026 [P] [US1] `frontend/src/components/assistant/CommandRunChip.tsx`: show `i/8` from
      `run.pipeline` on a pipeline stage chip (`Auto · /speckit-plan 002-… ✔ · 3/8`).
- [X] T027 [P] [US1] `frontend/src/components/assistant/ModeSelector.tsx`: show
      `Etapa i/8 · <stage>` next to the contract counters while a pipeline is running.
- [X] T028 [P] [US1] `frontend/src/i18n/es.ts` and `en.ts`: `assistant.pipeline.*` and
      `assistant.runReport.*` strings; `frontend/src/components/assistant/__tests__/RunReportCard.test.tsx`
      covering the populated and empty-pending cases.
- [X] T029 [US1] `backend/tests/test_assistant_speckit_all_run.py`: recorded provider — a brief that
      needs an integration and a report produces both specs, the stages run in order, the preview
      succeeds, the last message carries the card and no user message is posted after the contract
      (SC-002, SC-003).
- [X] T030 [US1] `backend/tests/test_assistant_speckit_all.py`: `--until tasks` stops after stage 4
      and the report has 4 stage rows; `--until nonsense` → `422 commands.until_invalid` listing the
      eight stages; in `ask` the command returns `assistant.mode.offer_auto` with no run created.

**Checkpoint**: the MVP — one request in, a report and "Listo para aplicar" out.

---

## Phase 4 — User Story 2: decisions instead of questions (P1)

**Goal**: every point where 021 would ask becomes a recorded decision, and analyze/converge close
their gaps in the same run.

**Independent Test**: a fixture run whose clarify stage would ask answers itself, and both the
spec's section and the report list the same decisions (SC-005).

- [X] T031 [US2] `agent_commands/{es,en}/speckit-all.md`: the precedence list (constitution → spec
      text → other specs → authoring-pack defaults) and the `- [stage] decision — why` format.
- [X] T032 [US2] `backend/app/assistant/commands/pipeline.py` `decisions_block()`: read the section
      from `specs/<spec>/spec.md`, validate each line's stage token, and return the verbatim block
      the report embeds (data-model §5, §6).
- [X] T033 [US2] `backend/tests/test_assistant_speckit_all.py`: `decisions_append` accepts an added
      line, refuses a changed existing line, refuses any change outside the section, and refuses a
      line whose stage token is not in `STAGES`.
- [X] T034 [US2] `agent_commands/{es,en}/speckit-clarify.md`: in an Auto run, generate at most 5
      questions from the clarify taxonomy, answer each with the best-supported option and apply the
      answers as the command does today (Clarifications section + updated sections).
- [X] T035 [US2] `backend/app/assistant/commands/pipeline.py`: analyze findings — CRITICAL/HIGH
      re-open the owning stage once (`MAX_ANALYZE_ROUNDS` (the rewind count)), MEDIUM/LOW are recorded
      as accepted or fixed in the decisions block; analyze never writes (its `writes=()` stands).
- [X] T036 [US2] `backend/app/assistant/commands/pipeline.py`: converge gaps — appended tasks are
      executed in the same run, at most 2 rounds (at most `MAX_ROUNDS` converge runs per spec), then the run continues to verify.
- [X] T037 [US2] `backend/tests/test_assistant_speckit_all.py`: a fixture run with one assumption
      produces the same decision line in `spec.md` and `run-report.md` (SC-005), and converge's
      second round stops at 2 with the report naming it.

---

## Phase 5 — User Story 3: bounded, stoppable, resumable (P1)

**Goal**: the run stops only for the eight code-enforced reasons, keeps what it wrote, and resumes
at the same stage.

**Independent Test**: a run stopped by a limit at each stage resumes from that stage without
repeating a completed one (SC-004).

- [X] T038 [US3] `backend/app/assistant/commands/pipeline.py`: `stop_reason(kind, detail)` + the
      mapping of contract §5 (`limit:<name>`, `stopped:user`, `provider:<code>`, `verify:failed`,
      `constitution:conflict`, `source:missing`, `contract:<stage>`), capped at
      `MAX_STOP_REASON = 120` like `AssistantAutoRun.stop_reason`.
- [X] T039 [US3] `backend/app/assistant/tools.py` `_run_command`: call `auto.limit_refusal` before
      opening a stage; on a refusal, finish the pipeline (no new run), keep `cursor`, and let T022
      write the report.
- [X] T040 [US3] `backend/app/assistant/service.py` `stop()` and the mode-down path: the pipeline
      ends `interrupted` with `stopped:user`, the report is written there (`_report_on_stop`), and
      the cursor is rewound to the stage whose run did not finish (`pipeline.rewind`), so a resume
      repeats it instead of skipping to the next one.
- [X] T041 [US3] `backend/app/assistant/service.py` `_provider_error`: for a pipeline run, translate
      the 035 code into `provider:<code>` in the report and stop (one bounded retry for transient
      codes stays 035's).
- [X] T042 [US3] `backend/app/assistant/commands/pipeline.py`: resume — `/speckit-all <id>` with a
      stored pipeline continues at `cursor`; without one it starts at the first incomplete stage of
      `completed()`; `--force` ignores `completed()` and starts at `specify`.
- [X] T043 [US3] `backend/tests/test_assistant_speckit_all.py`: parametrised resume fixture per
      stage (8 cases) — stopped at stage N, resumed at N, stages < N not re-run (SC-004).
- [X] T044 [US3] `backend/tests/test_assistant_speckit_all_run.py`: a reply whose usage alone blows
      the contract's 10 000-token minimum stops the plan with `limit:tokens`; every file stays, the
      report says so, and the cursor rewinds to the stage that was cut short (analyze).
- [X] T045 [US3] `backend/app/i18n/es.py` and `en.py`: fill `pipeline.*`, `commands.speckit_all_*`,
      `commands.until_invalid`, and one line per stop reason shown in the report card.

---

## Phase 6 — User Story 4: verify means real checks (P2)

**Goal**: the verify stage proves the spec with the checks the product already owns, per user story,
and fixes before giving up after 3 cycles.

**Independent Test**: `backend/tests/test_assistant_speckit_all_verify.py` shows validation, one
`check_query` per query/request, one preview, per-story results, and `verify:failed` after 3 cycles.

- [X] T046 [US4] `agent_commands/{es,en}/speckit-verify.md`: the stage runs validation, one
      `check_query`/`check_request` per file, one preview (charged to the contract) and the per-story
      Independent Tests (row counts, rendered views, PDF generated), then reports pass/fail per story.
- [X] T047 [US4] `backend/app/assistant/commands/pipeline.py` `verify()`: compose `session.validation`,
      `origin.check_query` for every query/request file of the spec's integrations, one
      `preview.run_draft_preview` (respecting `limits.previews`) and the per-story results; return
      `{ok, checks, failures}` matching data-model §6's verification table.
- [X] T048 [US4] `backend/app/assistant/commands/pipeline.py`: the 3-cycle loop — a failure re-opens
      `implement` (or `converge`), preferring 035's deterministic fixes over AI edits, incrementing
      `verify_cycles`; at 3 the pipeline stops with `verify:failed` naming the failing story.
- [X] T049 [US4] `backend/tests/test_assistant_speckit_all_verify.py`: a failing view yields
      `verify:failed` after 3 cycles with the story named; a passing run records one row per check
      and per story.
- [X] T050 [US4] `frontend/src/components/assistant/RunReportCard.tsx`: render the verification table
      with pass/fail per story (extends T025).

---

## Phase 7 — Polish and cross-cutting concerns

- [X] T051 `.claude/skills/speckit-all/SKILL.md` (new): the same eight stages and the same autonomy
      block, with repo tools — the `/speckit-*` skills and `.specify/scripts/bash/setup-*.sh` for
      the stages, `pytest`, `npm run build` and `npx vitest run` for verify; `--until tasks` is the
      documented dry run (FR-007).
- [X] T052 `backend/tests/test_speckit_all_contract.py`: the
      `<!-- bizview:contrato-autonomo -->` block is byte-identical in the ES prompt, the EN prompt
      and the repo skill, and every stage list equals `pipeline.STAGES` (SC-006, drift half).
- [X] T053 `backend/app/assistant/guide/index.yaml` + `guide/es/` and `guide/en/`: one topic for the
      command (id `todo-el-recorrido`, section `agente`) documenting `--until`/`--force` and
      `--until tasks` as the dry run; update `backend/tests/test_guide.py` and
      `backend/tests/test_guide_answers.py` (they iterate `REGISTRY`, so both new commands need an
      answer).
- [X] T054 `CHANGELOG.md` under Unreleased (user-visible: one command for a whole feature), and
      `docs/VIBE-REPORTING.md` command table gains `/speckit-all` and `/speckit-verify`.
- [X] T055 `backend/tests/live/test_speckit_all_live.py` (opt-in, `AI_LIVE_TESTS=1`): SC-001 (≥ 4 of
      5 runs reach "Listo para aplicar" with 0 user messages after the contract) and SC-002.
- [X] T056 Regression gate: `cd backend && uv run ruff check app tests alembic && uv run pytest`;
      `cd frontend && npx tsc --noEmit -p . && npm test && npm run build`.

---

## Dependencies

```text
Phase 1 (T001–T003)
   └─► Phase 2 (T004–T018)  ← blocks every story
         ├─► Phase 3 US1 (T019–T030)  ── MVP
         │      ├─► Phase 4 US2 (T031–T037)
         │      ├─► Phase 5 US3 (T038–T045)
         │      └─► Phase 6 US4 (T046–T050)
         └─► Phase 7 (T051–T056) after US1; T052 needs T019/T020/T051, T056 last
```

- US2, US3 and US4 all build on US1's runner, report and chips, and are independent of each other.
- T013 (order enforcement) and T042 (resume) share `next_stage`; T042 may start from T012's API.
- T021/T022 (report) precede T032/T037 (decisions in the report) and T050 (verification table).

## Parallel opportunities

- **Phase 1**: T002 and T003 (`[P]`).
- **Phase 2**: T006 and T007 (different rules in one file) and T018 can run beside T009–T012.
- **US1**: T020 with T019 (English after Spanish); T024–T028 are one frontend branch that does not
  touch the backend; T030 can be written before T029's recording exists.
- **US2/US3/US4**: three independent workstreams after US1 (prompts/decisions, stops/resume,
  verify), each with its own test file.

## Implementation strategy

1. **MVP first** — Phases 1–3: `/speckit-all <request>` reaches "Listo para aplicar" with the report
   card. That already satisfies US1 and FR-001/002/004/006.
2. **Then the constraints** — Phase 5 (US3) before Phase 4/6 if the first live run shows a runaway:
   stops and resume are what make the command safe to leave unattended.
3. **Then decisions and verify** — US2 and US4 make the run trustworthy (SC-003/SC-005) and the
   checks real (US4).
4. **Polish last** — the repo skill (FR-007), the guide, the changelog and the live eval.

## Format validation

Every task carries a checkbox, a sequential `T0NN` id, `[P]` only where the file set is disjoint, a
`[USn]` label in Phases 3–6 only, and an explicit path.
