---
description: "Validate the Bizview workspace and write bizview.lock"
---

# Validate the workspace (no spec, no run)

1. Run `bizview validate --write-lock` from the workspace root.
2. If it reports errors, fix them in the artifacts **or** update the spec (and its plan/tasks)
   when the spec is what changed — never make artifacts diverge from their spec. Re-run until it
   passes.
3. When it passes, confirm that every task in the feature's `tasks.md` is `[X]` and that
   `**Status**:` in `spec.md` is `Implemented`, then run `bizview validate --write-lock` again.
4. Report the result: integrations and reports validated, and the reminder to commit and push the
   workspace so the installation can apply it (*Administración → Espacio de trabajo*).
