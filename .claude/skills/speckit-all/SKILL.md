---
name: "speckit-all"
description: "Run a whole feature end to end —specify, clarify, plan, tasks, analyze, implement, converge, verify— without asking, ending with a run report."
compatibility: "Requires spec-kit project structure with .specify/ directory"
metadata:
  author: "bizview"
  source: "cli/bizview_cli/workspace_template/agent_commands/en/speckit-all.md"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

`$ARGUMENTS` is `<request | spec id> [--until <stage>] [--force]`. With no spec id the request is a
brief and stage 1 creates the spec(s). `--until tasks` is the documented dry run: the run stops
after that stage (included) and writes the report.

## Outline

The stage list is fixed and identical to the product's `/speckit-all`:

```text
specify → clarify → plan → tasks → analyze → implement → converge → verify
```

1. **Resolve the target.** `.specify/scripts/bash/check-prerequisites.sh --json --paths-only` gives
   the feature directory; `.specify/feature.json` or the argument names the spec. With no spec, run
   `/speckit-specify` first and take the folder it creates.
2. **Resume.** A spec that already has `spec.md`/`plan.md`/`tasks.md` starts at the first stage its
   artifacts do not prove complete; `--force` starts at `specify`.
3. **Run each stage** with the matching skill — `/speckit-specify`, `/speckit-clarify`,
   `/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`, `/speckit-implement`,
   `/speckit-converge` — in that order, each through `.specify/scripts/bash/setup-*.sh` for paths.
   Use `TodoWrite`/the task list for the eight stages so the position is visible.
4. **Analyze fixes itself.** CRITICAL/HIGH findings go back once to the stage that owns the file;
   MEDIUM/LOW are recorded as decisions.
5. **The plan loops back.** When `converge` adds or reopens tasks, run `implement` on exactly those
   tasks and then `converge` again — at most 2 convergence rounds, then `verify`. When `verify`
   fails, run `implement` of the fixing tasks and `verify` again — at most 3 cycles. `verify` never
   starts while `tasks.md` has unticked tasks: implement first. Every re-entry is a normal stage and
   its chip names the round ("Auto · /speckit-implement 001 · round 2").
6. **Verify with the repo's own tools**: targeted `pytest`, `npm run build`, `npx vitest run`, plus
   the feature's quickstart checks. A failure goes back to `implement`/`converge`; at 3 cycles the
   run stops and the report names the failing story.
7. **Write `run-report.md`** in the spec folder: run line, stages table, decisions, verification
   table, and "Pending for the human" — only what truly needs one, never instructions.

## The autonomy contract

<!-- bizview:contrato-autonomo -->
- No questions: no stage ends by asking the human for a decision or a confirmation. A doubt is
  resolved with this precedence —constitution, the spec's text, other specs in the project, the
  authoring pack defaults— and recorded as a decision.
- Every decision is written as `- [stage] decision — why` under
  "## Decisiones tomadas (modo autónomo)" in `specs/<spec>/spec.md`. Never change any other
  line of that file.
- The stage order is fixed and only advanced with `run_command`; only the transitions above
  re-open a stage — never a jump, never a stage without the evidence the plan asks for.
- An artifact that is already written is not rewritten the same: the same stage twice produces no
  change unless its inputs changed.
- You stop only for: a constitution conflict that needs an amendment, verification still failing
  after 3 cycles, an action the contract does not allow, or a missing source or credential.
  Anything else is a decision, never a stop.
- At the end you write the report and, under "Pending for the human", only what truly needs one
  (Apply when the contract does not allow it). Never give instructions on how to continue.
<!-- /bizview:contrato-autonomo -->

A task is ticked only when it is implemented and its file exists; `/speckit-implement --only
T025,T026` implements the tasks a fix names, and no fix, fix message or other stage changes the
status of a task. In this repository `run_command` is the stage you open with the matching skill;
the product's version of the contract is enforced by product code, this one by the list of stages
above.
