---
description: Runs a whole spec —specify, clarify, plan, tasks, analyze, implement, converge and verify— without asking, and ends with the run report.
argument_hint: "<request or NNN-name> [--until <stage>] [--force]"
source: speckit-all
---
# /speckit-all

## Goal
Take one request (or a spec that already exists) from the idea to "ready to apply" in a single run,
with no human intervention after the contract. Every stage is a real Spec Kit command; this command
only decides the order, records the decisions and writes the report.

## Command
The `Pipeline` block in `## Command` says which stage you are in (`Stage i/8`), on which spec and
which ones remain. The next stage is **always** opened with `run_command`:

```text
specify → clarify → plan → tasks → analyze → implement → converge → verify
```

- Do not write artifacts in this stage: the stage that owns them writes them. This run only writes
  lines in "Decisiones tomadas (modo autónomo)" of `specs/<spec>/spec.md`; `run-report.md` is
  written by the product at the end.
- When the plan has two specs (integration and report), finish all eight stages of the integration
  before starting the report. Move to the other spec with `set_current_spec`.
- `--until <stage>`: the run stops after that stage (included) and writes the report.
  `--until tasks` is the documented dry run.
- `--force`: do not trust what is already done; walk the stages again from the start.
- A stage that is already complete is skipped: do not repeat finished work.

## What each stage does
- **specify**: write the complete spec (and its checklist) for what the user asks. If the request
  needs a source that does not exist, stop and say it in one line: never invent a spec with no
  source.
- **clarify**: generate at most 5 questions from the clarify taxonomy, answer them yourself with the
  best-supported option and apply them as the command would (clarifications section and texts).
- **plan**: the technical plan and the artifacts (`integrations/…`, `reports/…`).
- **tasks**: ordered, verifiable tasks.
- **analyze**: check spec/plan/tasks coherence. On CRITICAL/HIGH, go back once to the stage that
  owns the file (`run_command`); MEDIUM/LOW is recorded as a decision.
- **implement**: write the artifacts and tick the tasks.
- **converge**: if pieces are missing, append the convergence phase to `tasks.md` and execute it in
  the same run (at most 2 rounds).
- **verify**: the product already ran the checks; read them and fix what fails by going back to
  `implement`/`converge` (at most 3 cycles).

<!-- bizview:contrato-autonomo -->
- No questions: no stage ends by asking the human for a decision or a confirmation. A doubt is
  resolved with this precedence —constitution, the spec's text, other specs in the project, the
  authoring pack defaults— and recorded as a decision.
- Every decision is written as `- [stage] decision — why` under
  "## Decisiones tomadas (modo autónomo)" in `specs/<spec>/spec.md`. Never change any other
  line of that file.
- The stage order is fixed and only advanced with `run_command`; a stage is neither skipped nor
  repeated.
- An artifact that is already written is not rewritten the same: the same stage twice produces no
  change unless its inputs changed.
- You stop only for: a constitution conflict that needs an amendment, verification still failing
  after 3 cycles, an action the contract does not allow, or a missing source or credential.
  Anything else is a decision, never a stop.
- At the end you write the report and, under "Pending for the human", only what truly needs one
  (Apply when the contract does not allow it). Never give instructions on how to continue.
<!-- /bizview:contrato-autonomo -->
