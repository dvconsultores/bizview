# Research: `/speckit-all` (039)

Phase 0 resolves what the plan needed to know about the seams that already exist. Every finding
below was read from the code, not assumed.

## R1 — Who drives the stage transitions?

**Decision**: the model, through the existing `run_command` tool; product code only refuses
transitions that break the plan.

**Rationale**: 028 FR-004 already turns `run_command` into a real `assistant_command_run` for the
stage (same scope, same audit, same ceiling) and the provider loop is never nested. Two drivers
would double-advance a stage (the model's call plus a product hook), and a product-only driver
would have to synthesise the stage's prompt outside the loop that 028 built.

**Alternatives**: (a) product loop calling the provider once per stage — rejected: new engine,
contradicts 028 FR-004 and FR-002 of this spec; (b) prompt-only order — rejected: FR-003 requires
code to enforce it.

## R2 — Is a migration needed?

**Decision**: no.

**Rationale**: `assistant_command_run.result` is JSONB and already carries command-specific data
(`converge` stores `revisions` there); the `command` CHECK (`0023`) is
`^(speckit-[a-z]+|ayuda)$`, which accepts `speckit-all` and `speckit-verify`. `run.result` is the
natural home for the cursor, and `_run_json` is the single place the transcript reads it.

**Alternatives**: `assistant_auto_run.step/steps` columns — rejected: the auto run is per contract,
not per pipeline, and a second pipeline could legitimately start under the same contract
(`--force`). A new `assistant_pipeline` table — rejected for the same reason plus a migration and a
cascade to maintain.

## R3 — How does `verify` produce real checks?

**Decision**: `speckit-verify` is a registry entry with `writes=()` and
`tools={"check_query","run_preview"}`; its results are computed by the product
(`pipeline.verify`) and handed to the model as the stage's tool results, which then reports pass/
fail per user story.

**Rationale**: the checks are the ones 014/017/035 already own (`session.validation`,
`origin.check_query`, `preview.run_draft_preview`, `readiness`). Making verify a stage keeps one
driver (R1), gives it a chip and an audit row, and lets `--until verify` mean exactly what it says.
`previews` stays counted by the contract, so US3 AC1 still stops the run.

**Alternatives**: folding verify into `speckit-implement` — rejected: no chip, no `--until verify`,
and it hides which cycle failed. A product-only hook after implement — rejected: the cycle cap and
the fix path would live outside the stage that can fix.

## R4 — How is "already done" detected on resume?

**Decision**: `projects/specs.py` first (`stage()`, `revised_by()`, `converged()`), the persisted
cursor second, and only for stages the artifacts cannot prove.

**Rationale**: the artifact is the truth (IX). `stage()` already maps spec → aclarada → planificada
→ tareas → implementada → aplicada; `revised_by(..., "speckit-clarify")` covers a spec clarified
without losing its `[NEEDS CLARIFICATION]` markers; `converged()` distinguishes a converge that
left open tasks. `analyze` writes nothing (`writes=()`), so it is the one stage whose completion
only the cursor or the report can prove — hence the cursor is kept, not replaced.

**Alternatives**: cursor-only resume — rejected: a spec built by hand (`/speckit-specify` +
`/speckit-plan`) would redo specify and clarify. Artifacts-only — rejected: analyze would re-run
forever.

## R5 — Where can the decision log live without widening a scope?

**Decision**: a dedicated guard rule (`decisions_append`) scoped to
`specs/<spec>/spec.md`, append-only inside `## Decisiones tomadas (modo autónomo)`.

**Rationale**: `guard.py` is the only place that can widen a write safely, and its rules are
already shape-based (`tasks_ticks`, `status_implemented`, `req_checklist_toggle`). Adding a rule
whose allowed diff is "lines added to one section" keeps the property that a refused op leaves the
project untouched.

**Alternatives**: letting `speckit-all` hold every stage's write rule — rejected: it would let one
run write outside the stage it is in, which is exactly what 029's `path_not_allowed` and
`path_other_spec` messages were added to prevent.

## R6 — What does the repo toolchain command run?

**Decision**: `.claude/skills/speckit-all/SKILL.md`, the same stage list and the same autonomy
block, with the repo's own tools: `.specify/scripts/bash/setup-*.sh`,
`/speckit-specify|clarify|plan|tasks|analyze|implement|converge` skills, and `pytest` +
`npm run build` + `npx vitest run` for verify.

**Rationale**: FR-007 asks for the same contract with repo scripts instead of product tools. The
repo's agent toolchain is `.claude/skills/` (that is what `/speckit-…` resolves to here), and the
contract block can be byte-identical only if it is one data block copied by a test.

**Alternatives**: a shell script — rejected: the repo toolchain is skill-based; a script would not
be picked up by the agent. Generating both from `.specify/templates/` — rejected: the product
prompt is packaged data of `bizview_cli`, and 021 already made the prompt file the single source.

## R7 — Dependency check (spec "Requires 028, 029, 037")

**Decision**: proceed; verify at implementation time.

**Rationale**: `auto.py` (028), `resolve.resolve`/`set_current_spec`/`_idempotence`/`misrouted`
(029) and the project-scoped `fs`/`ProjectPathError` paths (037) are present in `backend/app`. 029
has no folder under `specs/` in this working copy while its code is deployed; the implementation
gates are therefore the tests of those features, not their spec folders.
