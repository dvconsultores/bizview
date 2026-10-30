# Commands to plan

## What it is for

These commands turn a spec into a technical plan and a task list, and check their quality.

## Who can use it

Only the **Superuser**. They all work on the **Current spec**.

## How to

- `/speckit-plan`: writes `plan.md` and, when needed, `research.md`, `data-model.md` and
  `quickstart.md`. It uses the sources' real structure (tables and columns) to decide the design.
  It needs `spec.md`.
- `/speckit-tasks`: writes `tasks.md` with numbered tasks by phases. It needs `plan.md`. If the
  spec has unresolved questions, it asks first whether you want to go on.
- `/speckit-analyze`: compares spec, plan and tasks and gives a report of inconsistencies. It
  changes no file.
- `/speckit-checklist <topic>`: creates or extends a `checklists/<topic>.md` list that evaluates
  the quality of what is written (not the implementation). New items stay unchecked.

## Common problems

- "plan.md is missing; run /speckit-plan first.": the chat offers an **Insert** button with the
  missing command.
