# The Spec Kit method

## What it is for

In BizView nothing runs without a spec: every source, integration, report and distribution is a
numbered specification of the project that goes through fixed stages.

## Who can use it

Only the **Superuser** works on projects.

## How to

A spec's flow, with each step's command:

1. `/speckit-specify <description>`: creates the `NNN-name` spec with its **Type**.
2. `/speckit-clarify`: resolves the open questions.
3. `/speckit-plan`: writes the technical plan.
4. `/speckit-tasks`: splits the plan into tasks.
5. `/speckit-analyze` and `/speckit-checklist` (optional): check consistency and quality.
6. `/speckit-implement`: writes the artifacts until the project is **Ready to apply**.
7. `/speckit-converge`: compares what was asked with what was done and adds tasks if something is
   missing.
8. **Apply project**: you do it.

## Options

- The stages you see in the explorer are **Specified**, **Clarified**, **Planned**, **Tasks**,
  **Implemented** and **Applied**, plus **Converged** when converge found nothing pending.
- `/speckit-constitution` sets the project's principles; the installation's rules cannot be
  removed.
- What next? Type `/ayuda` in the chat: it shows each spec's next command.
