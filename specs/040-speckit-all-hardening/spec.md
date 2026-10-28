# Feature Specification: `/speckit-all` hardening — rounds, honest fixes, bounded context

**Product**: BizView · **Feature Branch**: `040-speckit-all-hardening`

**Created**: 2026-10-28

**Status**: Draft

**Input**: Owner, 2026-10-28, production run of `/speckit-all 001-mercado-cripto` on the project
`coinmarketcap` (14 327 159 tokens, 626 tool calls, three context compressions in one run and an
`IntegrityError` at the end). Five defects, one per section:

- **A** the pipeline is a one-way index: after `converge` added tasks T025–T028 it demanded
  `/speckit-verify` and told the human to "open it in that order", never going back to implement.
- **B** the validator offered a *fake* fix for unchecked tasks ("mark every task as `- [X]`"),
  which changes evidence, not content.
- **C** compression ran three times in one run, thrashing the context and ending in an
  `IntegrityError` instead of continuing (or stopping with a reason).
- **D** 626 tool calls and 14 M tokens for one integration: nothing bounds a stage, and nothing
  records what a stage cost.
- **E** two data defects reached the preview: a timestamp mapping in the wrong unit
  (`date/time field value out of range`) and `fields` written without checking the response shape
  (`columnas o campos que no coinciden`).

**Builds on**: 021 (commands), 028 (Auto mode and the run contract), 029 (routing and guards), 033
(app guide), 035 (deterministic fixes and provider errors), 036 (replayable history), 039
(`/speckit-all`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The plan loops back by itself (Priority: P1) 🎯

The owner types `/speckit-all 001-mercado-cripto` and leaves. Converge finds four gaps, adds the
tasks and **implements them in the same run**; then it converges again, verifies, and only then
ends. Nobody is told to "open a stage in that order".

**Acceptance Scenarios**:

1. **Given** `converge` added or reopened tasks, **When** the stage ends, **Then** the plan's next
   stage is `implement` (round 2), and after it `converge` again — at most 2 convergence rounds.
2. **Given** `verify` fails, **Then** the next stage is `implement` of the fixing tasks, then
   `verify` again — at most 3 verify cycles.
3. **Given** `tasks.md` still has unchecked tasks when `verify` is next, **Then** `verify` is not
   opened: the plan routes to `implement`. The run never fails nor asks for that reason.
4. **Given** any re-entry, **Then** it is an ordinary `run_command` whose chip carries the round
   ("Auto · /speckit-implement 001 · ronda 2").
5. **Given** the plan's cursor is read from any cursor position, **Then** `next_stage(state)` is
   the only place that decides where it goes — there is no "stage 8/8" hard check.

### User Story 2 - No fix may fake evidence (Priority: P1)

The problems panel offers honest actions only.

**Acceptance Scenarios**:

1. **Given** a spec with unchecked tasks, **When** validation runs, **Then** the problem carries
   the honest action ("Implementar tareas pendientes", `/speckit-implement <spec> --only T…`) and
   **no** fix that marks tasks.
2. **Given** every registered deterministic fix, **Then** a test enumerates them and asserts none
   touches a `- [ ]`/`- [X]` box or a `**Status**:` line.
3. **Given** a task is ticked, **Then** the write is accepted only inside `/speckit-implement`,
   only for a task whose referenced artifact exists, and only for the tasks named by `--only`
   when that flag was given. Any other tool writing `tasks.md` ticks is refused with
   "las tareas se marcan al implementarlas".

### User Story 3 - Bounded context, named stops (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a round would exceed the model's context minus the margin, **Then** the history is
   compressed **once** for that run; the compression writes one `working_state` update and one
   summary message in the round's own transaction, with the idempotency key
   `(session_id, run_id, compression_n)`.
2. **Given** a compression freed less than 20 % (or a second one is needed again), **Then** the
   run stops with `blocked:context_exhausted`, the state saved, and `/speckit-all <spec>` resumes.
3. **Given** a stage ends, **Then** its tool results are not sent again: the stage summary line
   (`✔ <stage> — …`) replaces them.
4. **Given** a `/speckit-all` run, **Then** each stage is sent its own provider context: system
   prompt + working state + the current stage's messages + the previous stage's summary line.

### User Story 4 - A stage has a budget and a tool group (Priority: P1)

**Acceptance Scenarios**:

1. **Given** any provider round, **Then** the model receives at most 25 tools: the ones of the
   current stage's group (`specify`, `plan`, `implement`, `verify`, …). App guide topics are
   reached through the single `get_app_guide(topic)` tool.
2. **Given** a stage spends more than `ai_stage_token_budget` (default 600 000), **Then** the
   stage stops with `blocked:stage_budget`, the state is saved and the report says so.
3. **Given** the run report, **Then** it carries `tokens_per_stage`, and "Detalles técnicos" shows
   the tool count and the prompt size of every round.

### User Story 5 - The two data defects cannot repeat (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an integration request with `fields`, **When** `/speckit-implement` writes them
   **Then** `check_request` ran first and every field exists in the returned shape; a missing one
   is an error that names the actual keys.
2. **Given** a mapped time field, **Then** the integration schema records
   `timestamp_unit: seconds|milliseconds|iso8601`, inferred by `check_request` from the sample
   value and validated at preview within 1990–2100; a mismatch is `timestamp_unit_mismatch` with a
   deterministic fix (a *content* fix).

### Edge Cases

- A run that stops on `blocked:context_exhausted` or `blocked:stage_budget` writes the report and
  keeps every file already written; resuming continues at the stage that was cut short.
- Two convergence rounds with no progress (the second converge adds nothing) ends the loops and
  goes to verify instead of a third round.
- `--only` naming a task that does not exist is refused before the run starts.
- A conversation without `/speckit-all` keeps its single context: the stage scoping only applies
  inside a plan.

## Requirements *(mandatory)*

- **FR-001 (A)**: `pipeline.next_stage()` is a state machine over `(spec, stage, round,
  verify_cycles, evidence)`; the transitions of US1 are product code, not prompt text.
- **FR-002 (A)**: a re-entry opens a normal command run whose chip shows the round.
- **FR-003 (A)**: `verify` routes to `implement` while `tasks.md` has unchecked tasks.
- **FR-004 (B)**: no registered fix or fix message may change task status or `**Status**:`.
- **FR-005 (B)**: `--only T025,T026` exists on `/speckit-implement`; the guard enforces it.
- **FR-006 (B)**: the unchecked-tasks problem offers "Implementar tareas pendientes".
- **FR-007 (C)**: at most one compression per run, idempotent by
  `(session_id, run_id, compression_n)`; thrash stops with `blocked:context_exhausted`.
- **FR-008 (C)**: stage-scoped provider context inside a plan.
- **FR-009 (D)**: per-stage tool groups, ≤ 25 tools per round; app topics behind one tool.
- **FR-010 (D)**: `ai_stage_token_budget` per stage → `blocked:stage_budget`;
  `tokens_per_stage` in the report; tool count and prompt size logged per round.
- **FR-011 (E)**: `check_request` before `fields`, with the actual keys in the error.
- **FR-012 (E)**: `timestamp_unit` per mapped time field, inferred and validated, with a
  deterministic fix.
- **FR-013 (Step 0)**: an `IntegrityError` in the loop maps to `loop_state_conflict:<constraint>`,
  never to "error inesperado", and the run keeps its cursor.

## Success Criteria *(mandatory)*

- **SC-001**: the recorded CoinMarketCap fixture completes `/speckit-all` in one run with both
  specs, 0 compressions, 0 `IntegrityError`, under 1.5 M tokens.
- **SC-002**: a fixture from this run (T025–T028 unchecked after converge) reaches `verify` through
  `implement` without a human message.
- **SC-003**: 0 fixes in the registry change status or evidence (automated).
- **SC-004**: ≤ 25 tools per round and a per-stage ceiling, asserted at the provider transport.
- **SC-005**: the two data defects are caught before the preview, with deterministic fixes.

## Constitution check

- VIII: no new provider input; the stage scoping *reduces* what is sent, never adds.
- IX: task status is evidence, never editable by a fix; every stage still writes and validates.
- V: no new dependency, no migration needed (the cursor and the run report carry the new keys).

→ PASS, no amendment.

## Assumptions

- 039 is deployed; its stage list, report and cursor are reused unchanged.
- The per-stage budget is a setting, so an installation can raise it without a release.
