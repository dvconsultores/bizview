# Fix the problems

## What it is for

A problem says which file, which line or key, what is wrong and, almost always, how to fix it. You
fix the file and check again; there is no need to start over.

## Who can use it

Only the **Superuser**, in the project's editor or on their own machine.

## How to

1. Open [Proyectos](app:/proyectos) and go into the project: problems appear under the editor.
2. Read the whole row: file, message and the how-to-fix column.
3. Fix the file in the editor, or ask your AI to fix it with that message copied in.
4. Press **Check again** to see the updated list.
5. When no error is left, press **Apply project**.

Some problems carry a proposed correction and are fixed with a button; others, like an unticked
task, need someone to decide.

## Options

- Warnings do not stop an apply; errors do. A report without filters is an apply error, not a
  validation one.
- When the problem is in another project the notice names it, and it is not fixed from here.
- You can send the project back to an earlier revision from its history when a fix makes things
  worse.

## Common problems

- `unknown_column`: the report uses a column its dataset does not declare. Add it to the dataset or
  use another one.
- `open_tasks`: an `- [ ]` task is left in `tasks.md`. Tick it when it is done.
- `spec_not_approved`: `spec.md` does not say `**Status**: Approved`.
- `personal_data_undeclared`: a column looks like personal data and the spec does not list it.

## Related

- Validate before importing
- Project editor
- Apply a project
