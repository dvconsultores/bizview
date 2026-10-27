# Commands to build

## What it is for

These commands write the spec's artifacts (integration, report or distribution) and check that the
project meets what was asked.

## Who can use it

Only the **Superuser**, on the **Current spec**.

## How to

- `/speckit-implement`: follows `tasks.md` and writes the artifacts of the spec's kind: for an
  integration, `integrations/<id>/integration.yaml` and its queries or requests; for a report,
  `reports/<id>/report.yaml`; for a distribution, `distributions/<id>.yaml`. It checks each query,
  runs the preview, ticks the finished tasks and at the end sets the spec's status to
  `Implemented`. It never applies the project.
- `/speckit-converge`: compares what spec, plan and tasks ask for with the artifacts and, if
  something is missing, appends a phase of new tasks at the end of `tasks.md`. It changes nothing
  else.

## Options

- Before implementing, the chat asks if there are checklists with unchecked items or if the spec
  is not approved yet; your "yes" approves the spec.
- If a command is interrupted (you stop it or the budget runs out), what was done is kept; running
  the same command again continues from there.

## Common problems

- If it is not **Ready to apply** at the end, look at **Pending before applying** or run
  `/speckit-converge`.
- `/fix <what to change>`: corrects an artifact that already exists (a report, a query, a
  distribution) without writing a new spec. Validation and the preview still gate it.
