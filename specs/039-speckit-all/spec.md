# Feature Specification: `/speckit-all` — one command runs a feature end to end

**Product**: BizView · **Feature Branch**: `039-speckit-all`

**Created**: 2026-10-26

**Status**: Implemented

**Input**: Owner, 2026-10-26: "create a spec.all to cover all steps of a spec; launch the prompt
with the command and do all tasks alone without intervention — 100% autonomous agent." A new
Asistente command, `/speckit-all <request | spec id>`, that runs specify → clarify → plan → tasks
→ analyze → implement → converge → verify (validate + preview) for one project, in one run, with
no questions, and ends ready to apply (or applied, when the run contract allows it).

**Builds on**: 021 (Spec Kit commands in the chat), 028 (modes and run contract — `/speckit-all`
is the command form of an Auto run), 029 (spec routing, `set_current_spec`, misrouted runs,
idempotence guards), 035 (provider error handling, deterministic fixes), 036 (replayable history),
037 (project isolation). **Requires** 028, 029 and 037 to be deployed first.

**Also applies to the developer workflow**: the same command exists in the repository's Spec Kit
toolchain (`/speckit.all` for the coding agent) with the same contract; this spec covers the
in-product command, and the plan ships the repo command from the same contract text.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One command, a finished report (Priority: P1) 🎯

The super user, in a project conversation, types `/speckit-all Tablero de facturas por día y
estado, actualizado cada hora, con PDF`. The run contract opens (028), they confirm with step-up,
and leave. On return the conversation shows every stage as chips, the specs (integration and
report) written, validated and converged, a successful preview, and either "Listo para aplicar"
or "Aplicado · versión N" depending on the contract's allowed stages, plus a run report.

**Independent Test**: with the fake provider replaying a recorded run and with the opt-in live
eval, the command reaches "Listo para aplicar" with zero user messages after the contract, within
the default limits.

**Acceptance Scenarios**:

1. **Given** `/speckit-all <text>` in a project with no matching spec, **When** confirmed, **Then**
   the agent creates the spec(s) needed (an integration spec and a report spec when the request
   needs both), runs every stage for each in dependency order, and never ends a stage by asking
   the human (028 FR-004b).
2. **Given** `/speckit-all 002-ventas-facturacion`, **Then** the run resumes at the first incomplete
   stage of that spec (029 stage detection) and skips completed ones unless `--force`.
3. **Given** `--until <stage>` (`clarify|plan|tasks|analyze|implement|converge|verify`), **Then** the
   run stops after that stage with the report; `--until tasks` is the documented "dry run".
4. **Given** the run ends, **Then** `run-report.md` is written in the spec folder and shown as a
   card: stages, decisions taken, validation and preview results, tokens, and "Pendiente para el
   humano" (Aplicar, if not allowed by the contract — or nothing).

---

### User Story 2 - Decisions instead of questions (Priority: P1)

**Acceptance Scenarios**:

1. **Given** any point where a stage would ask (clarify questions, ambiguous table, missing
   schedule, chart choice), **Then** the agent decides using, in order: constitution, the spec's
   text, other specs in the project, the authoring pack defaults (015/028 FR-005), and writes
   `- [stage] decision — why` under "Decisiones tomadas (modo autónomo)" in the spec.
2. **Given** the clarify stage, **Then** it generates at most 5 questions from the clarify taxonomy,
   answers them itself with the best-supported option, and applies them as `/speckit-clarify`
   would (Clarifications section + updated sections).
3. **Given** the analyze stage finds CRITICAL/HIGH inconsistencies, **Then** it fixes the artifacts
   and re-runs once; MEDIUM/LOW are recorded as accepted or fixed.
4. **Given** the converge stage finds gaps, **Then** it adds the convergence tasks and executes them
   in the same run (max 2 rounds).

---

### User Story 3 - Bounded, stoppable, resumable (Priority: P1)

**Acceptance Scenarios**:

1. **Given** the contract limits (028: tokens, previews, applies, wall clock) or the per-command
   ceiling (029), **When** reached, **Then** the run stops with the reason, everything written so
   far is kept, and `/speckit-all <id>` resumes from the same stage.
2. **Given** "Detener" or a mode switch down (028), **Then** the run stops cooperatively; nothing
   is applied afterwards.
3. **Given** a provider error, **Then** 035 rules apply (one bounded retry for transient codes,
   immediate stop for credit/key/model codes) and the report says where it stopped.
4. **Given** the run stops only for: a constitution conflict that needs an amendment, verification
   still failing after 3 fix cycles, an action the contract does not allow, or a missing
   source/credential, **Then** the report names the condition in one line; everything else is a
   decision, never a stop.

---

### User Story 4 - Verify means real checks (Priority: P2)

**Acceptance Scenarios**:

1. **Given** the verify stage, **Then** it runs validation, `check_query`/`check_request` on every
   query, and the preview (within the contract's preview limit), and evaluates each user story's
   Independent Test from the spec as far as it can be executed without a human (row counts,
   rendered views, PDF generated), recording pass/fail per story in the report.
2. **Given** a failure, **Then** the agent fixes and re-runs that step (max 3 cycles), using
   deterministic fixes (035 C) before AI edits.

### Edge Cases

- `/speckit-all` in mode Ask or Edit: the command replies with the "Pasar a Auto" chip and does
  not start (028: text never switches the mode).
- Request needs a source that does not exist: stop at specify with "crea la fuente primero"; no
  spec is written for it.
- Two specs where the report depends on the integration: integration stages run first through
  implement + verify, then the report; the current spec is moved with `set_current_spec` (029).
- The request matches an existing integration: reuse it (014 US1/AC4); the run creates only the
  report spec.
- Re-running on an applied spec: nothing to do → one-line report; with `--force` a new draft on the
  current active version (014 US3/AC3).
- Project isolation (037): the command runs only in the conversation's project; any path outside
  it is refused.
- Idempotent file writes: the same stage twice produces no diff unless inputs changed.

## Requirements *(mandatory)*

- **FR-001**: New command `/speckit-all <request | spec-id> [--until <stage>] [--force]`
  registered with the other 021 commands; available only in mode Auto with a confirmed contract;
  in other modes it offers the "Pasar a Auto" chip.
- **FR-002**: The run is an ordinary 028 Auto run whose plan is the fixed stage list; each stage is
  executed through `run_command(spec, command)` (028 FR-004) so every stage is an audited command
  run with 029 routing and idempotence guards.
- **FR-003**: The autonomy contract (no questions, decisions recorded, stop conditions, idempotence,
  no manual steps except "Pendiente para el humano") is part of the command's system prompt and
  of the authoring pack, as data; the stop conditions are enforced by product code (contract
  limits, allowed stages, provider codes), not only by the prompt.
- **FR-004**: `run-report.md` is written in the spec folder and attached to the conversation as a
  card; its "Decisiones tomadas" mirrors the spec section.
- **FR-005**: `--until` and `--force` parsed by the command runner; `--until tasks` documented as
  the dry run in the in-app guide (033).
- **FR-006**: Every stage transition is a chip ("Auto · /speckit-plan 002-ventas-facturacion ✔")
  and the status bar shows `stage i/8`.
- **FR-007**: The repository Spec Kit toolchain gains the equivalent `/speckit.all` command (same
  stages, same contract text, repo scripts instead of product tools), installed with the other
  commands and covered by a smoke test; the plan ships both from one source of truth for the
  contract wording.

## Success Criteria *(mandatory)*

- **SC-001**: Live eval (015 SC-001 request): `/speckit-all` reaches "Listo para aplicar" with 0
  user messages after the contract in ≥ 4 of 5 runs, within the default contract limits.
- **SC-002**: Session-18 replay (integration + report from one request) completes under
  `/speckit-all` with both specs implemented, verified, and applied in one version (028 SC-008).
- **SC-003**: 0 runs end with an instruction to the human other than the "Pendiente para el
  humano" list (automated check on the final message of each fixture run).
- **SC-004**: Resume: a run stopped at any stage by a limit resumes from that stage without
  repeating completed stages (fixture per stage).
- **SC-005**: Every assumption in the fixtures appears in both the spec's "Decisiones tomadas" and
  the run report.
- **SC-006**: The repo `/speckit.all --until tasks` smoke test produces spec, checklist, plan and
  tasks that pass the requirements checklist.

## Constitution check

- VIII: same data boundary as 014/015; no new inputs to the provider.
- IX: every stage writes complete specs; nothing runs without validation; apply still goes
  through the contract (028) — the human approves once, up front.
- Constraints: step-up on `internet` for the contract; Alembic for any new columns; worker
  idempotent.

→ PASS, no amendment. Deviation already justified in 028 (per-run step-up).

## Assumptions

- 028, 029 and 037 are deployed; without 029 the stage detection and routing this command relies
  on do not exist.
- The stage list is fixed; project-specific extra stages (e.g. a security review) are added by a
  later feature as optional hooks, not by editing the command.
