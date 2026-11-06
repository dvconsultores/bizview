# Quickstart — 055-project-reimport

## The bug, reproduced

1. **Proyectos → Importar** a zip of `ventas-marca` → project `ventas-marca`, revision 1.
2. Change `reports/<id>/report.yaml` in the folder, zip it again, import → **before** this feature the
   list shows `ventas-marca` and `ventas-marca-2`; **after**, one row, `rev 2 · borrador`.

## Automated gates

```bash
cd backend
.venv/bin/python -m pytest tests/test_project_reimport.py -q
.venv/bin/python -m pytest tests/test_migrations.py tests/test_guide.py -q

cd ../frontend
npx tsc -b && npx vitest run && npm run build
npx playwright test tests/e2e/project-reimport.spec.ts --project=chromium-375

cd ../cli
uv run pytest tests/ -q
```

## Manual checks

1. **Same zip twice.** Import `ventas.zip`; import it again. One project in the list, and the project
   page's chip reads `rev 2 · borrador` next to `rev 1 · aplicada` once it was applied.
2. **The diff is honest.** Choose a zip whose folder lost a file and gained a spec: the pre-flight card
   lists it as removed/added *before* the import is sent, with the two allowances (049).
3. **Nothing applies itself.** After the re-import, the dashboard still shows the previous revision's
   layout until **Aplicar**.
4. **Apply.** **Aplicar** → the chip becomes `rev 2 · aplicada`, the dashboard shows the new layout, and
   **Auditoría** has `project_applied` with both revision numbers.
5. **Revert.** **Volver a la revisión anterior** → types the password (step-up) → the old layout is back,
   a new revision `rev 3 · aplicada` exists and `project_reverted` is in the audit.
6. **Copy.** Tick **Importar como copia** → a second project `<slug>-2` whose artifact ids end in `-2`;
   **Aplicar** on it works (no id collision).
7. **Draft conflict.** Edit a file in the editor (do not apply), then import the same zip: the page asks
   **Reemplazar borrador / Cancelar**; canceling leaves the editor revision intact.
8. **Download.** **Descargar** on a revision downloads a zip with that revision's files; unzip it and
   check `project.yaml` and the report are the older ones.
9. **Retention.** Lower `PROJECT_REVISIONS_KEEP=3` in `.env`, restart, import three more times: the list
   keeps three, and the applied and previous ones are always among them.
10. **CLI.** In a workspace folder that holds `projects/<slug>/`: `bizview import ventas.zip` prints
    `reimported` and the diff; `bizview import ventas.zip --dry-run` prints the diff only.

## What must not change

- Every refusal of 043/049 keeps its code: an executable in the zip (`zip_disallowed`), an over-limit
  project (the allowance named), two spec folders with the same number (`spec_number_duplicate`), a
  `git` project (`git_project`).
- A project's shares, dashboard grants, audit rows and loaded datasets survive a re-import.
- The worker keeps reading applied workspace versions: a draft revision runs nothing.
