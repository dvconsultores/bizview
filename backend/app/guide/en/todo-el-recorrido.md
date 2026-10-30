# The whole run with one command

## What it is for

`/speckit-all` takes one request from the idea to "ready to apply" in a single run: it walks the
eight Spec Kit stages —specify, clarify, plan, tasks, analyze, implement, converge and verify—
without asking you anything, deciding on your behalf and writing every decision down. When it ends
it writes `run-report.md` in the spec folder and shows the report as a card: stages, decisions
taken, verification per user story and "Pending for the human", which only names what truly needs a
person (usually pressing **Apply**). Every stage leaves its chip in the conversation with its
position (`Stage 4/8`), and the status bar shows the contract's spend.

## Who can use it

Only the **Superuser**, in **Auto** mode with the run contract confirmed. In Ask or Edit mode the
command does not start: it offers the "Switch to Auto" button.

## How to

- `/speckit-all <request>`: when the request names no spec, the first stage creates it (or the two
  needed: the integration and its report). When it names one (`/speckit-all 002-sales`), the run
  continues from the first missing stage and does not repeat finished work.
- Every stage is opened with the command that owns it, so it writes only its own files: the judging
  stages (analyze, verify) write nothing and, when something fails, re-open the stage that can fix
  it.
- Verification really runs: validation, one check per query or request of the integration, one
  preview and the result per user story.
- Convergence and verification rounds: when converge adds new tasks the run implements them in
  the same execution and converges again (at most two rounds); when verify fails the run implements
  what is missing and verifies again (at most three cycles). Every re-entry is a normal stage and
  its chip names the round: "Auto · /speckit-implement 001 · round 2". Verify never starts while
  tasks are unticked: the plan implements first, without asking you anything.
- Per-stage budget: each stage has a token ceiling (600 000 by default). When it is spent the
  run stops with `blocked:stage_budget`, saves its state and the report says where it stopped;
  `/speckit-all <spec>` continues there. The report lists the tokens of every stage.

## Options

- `/speckit-all <request> --until tasks`: the documented dry run. It stops after that stage
  (included) and writes the report with what exists.
- `--force`: does not trust what is done and walks the stages again from the start.
- `/speckit-all <spec>` with nothing else: resumes the run where it stopped.
- `/speckit-verify <spec>`: repeats only the verification of an implemented spec.

## Common problems

The run only stops for a constitution conflict that needs an amendment, verification still failing
after three cycles, an action the contract does not allow, or a missing source or credential; the
report says it in one line. When it stops at a contract limit, on "Stop" or on a provider error,
everything written is kept and `/speckit-all <spec>` continues at the same stage. Everything else is
decided by the agent and recorded under "Decisiones tomadas (modo autónomo)" in the spec.
