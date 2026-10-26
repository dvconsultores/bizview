# Prompt for DeepSeek — bug: "Ocurrió un error inesperado" when opening the preview of panorama-cripto

Paste everything below the line into DeepSeek (VS Code), with the repository open and SSH access
to the server (or the backend log pasted next to this prompt).

---

You are working on the BizView repository. Read `.specify/memory/constitution.md` and keep every
principle. Fix the defect below end to end (backend/worker, frontend, tests, CHANGELOG) as feature
`038-report-render-errors`. Do not ask me questions.

## Evidence (production, 2026-10-26 15:15, `/proyectos/coinmarketcap`)

- Project **CoinmarketCap**, version 22 applied 15:15, status "Válido · Listo para aplicar ·
  Aplicado", "Sin problemas de validación".
- Spec `001-mercado-cripto` (Integración, Aplicada) with four datasets: `assets`,
  `global_metrics`, `fear_greed`, `altcoin_season`. Report `panorama-cripto` uses them (joins on
  `snapshot_at` were added in the previous fix).
- "Tableros del proyecto: panorama-cripto" is listed. Under **Vista previa**, pressing
  `panorama-cripto` or `PDF de vista previa: panorama-cripto` shows:
  `Ocurrió un error inesperado (referencia e8c808976283). Si vuelve a pasar, pásale esa referencia
  a soporte: el registro del servidor tiene el detalle.`
- Validation passed, so the failure is at **render time** (report engine, preview schema
  resolution, layout renderer or PDF renderer), not in the spec.

## Step 1 — find the cause from the reference

```bash
docker logs --since 2h bizview-backend 2>&1 | grep -n "e8c808976283" -A 60
docker logs --since 2h bizview-worker  2>&1 | grep -niE "panorama|preview|coinmarketcap" | tail -80
```

Read the full traceback. Candidate causes to check, in order of likelihood for this report:

1. **Preview schema resolution**: the preview tables for the four datasets are in
   `preview_<session>` but the report engine resolves one of them (or the joined ones) in `ds_*`
   or the wrong schema, or the preview schema was already dropped (cleanup after apply/archive —
   version 22 was applied at 15:15 and the preview may have been cleaned a moment before the
   page asked for it).
2. **Join over multiple datasets**: `uses` with four sets joined on `snapshot_at` produces a
   query the engine builds incorrectly (ambiguous column, cartesian product, timestamp type
   mismatch between datasets, `snapshot_at` present in one set only).
3. **Empty snapshot**: a dataset with zero rows in the preview window → division by zero in a
   metric (`paid_rate`-style ratios, dominance percentages), `max()` of nothing, or a KPI delta
   over a missing comparison period.
4. **Layout renderer**: a component (`gauge`, `index`, `share`, `asset` tiles from spec 034)
   referenced by `layout.web`/`layout.pdf` that the renderer does not implement yet, or a
   `format` the formatter does not know (compact numbers, percentages of percentages).
5. **PDF renderer**: ReportLab failing on a layout block (page size, missing font, chart with no
   data) — the PDF link fails with the same reference, so it may be the shared data step, but
   confirm separately.

## Step 2 — fix the root cause and make every render error specific

### A. Root cause
- Reproduce with a fixture built from this project (export the project zip, anonymise nothing —
  it is generic market data — and add it under `tests/fixtures/projects/coinmarketcap/`).
- Fix the failing code path; add the regression test that renders `panorama-cripto` from the
  preview schema and from an applied version, in JSON and PDF, with (a) full data, (b) one empty
  dataset, (c) the comparison period absent.

### B. No more "error inesperado" in report rendering
- Replace the generic handler in the report data and PDF routes with typed errors and codes shown
  to the user (es/en), each with the failing piece named:
  `preview_expired` ("La vista previa ya no existe; vuelve a ejecutarla"), `dataset_missing`
  (dataset id), `join_failed` (sets and key), `empty_dataset` (dataset id — render the tile with
  "Sin datos" instead of failing), `metric_error` (metric id and the arithmetic problem),
  `layout_component_unknown` (component id and type), `format_unknown` (format id), `pdf_render`
  (block id). Keep the reference id and the log line for anything truly unknown.
- Tiles/blocks fail **individually**: a metric or component that cannot render shows an error
  card with its code; the rest of the dashboard and the PDF still render (026 FR-006 already says
  "never a blank dashboard" for unknown components — extend it to data errors).
- After apply, the "Vista previa" section must point to the **applied** dashboard (`/r/<id>`)
  instead of the preview schema, and the preview links disappear with a line "Vista previa
  reemplazada por la versión 22"; if the preview schema is already dropped, the links are not
  shown at all (fixes cause 1 structurally).

### C. Observability
- The error card's "Detalles técnicos" shows code, reference, report id, dataset/component id and
  the backend log command (035 D). Log at ERROR with the same fields; never row values.

## Tests
- Regression fixture above, JSON + PDF, three data conditions.
- Each typed error has a unit test that triggers it and asserts code, message and that the rest of
  the report still renders.
- Preview-after-apply: links switch to the applied dashboard; expired preview yields
  `preview_expired`, never a 500.
- Multi-dataset join: engine query builder tests for 2, 3 and 4 sets joined on one key, including a
  set missing the key (validation error, not runtime).
- Frontend unit: error card per tile; e2e: open preview → error in one tile → other tiles visible.

## Deliverables
- Root-cause fix + regression fixture; typed errors in engine, routes and PDF renderer; per-tile
  error cards; preview-section behaviour after apply; `es.ts`/`en.ts`; CHANGELOG under Unreleased;
  a line in `docs/guides/tableros/errores.md` per code.
- Constitution check in the plan: II/VI (engine reads optimized/preview models only), VIII (no row
  values in logs or errors), IX unchanged.
- Push, `./deploy.sh`, confirm on production that `panorama-cripto` renders (applied and PDF) and
  paste the resolved traceback cause in the PR description.

Commits: (1) root cause + fixture + regression tests, (2) typed render errors + per-tile cards,
(3) preview-after-apply behaviour, (4) docs + CHANGELOG.
