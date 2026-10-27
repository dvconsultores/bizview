# Data model: `/speckit-all` (039)

No new table and no new column (research R2). The feature adds one JSONB document inside
`assistant_command_run.result`, one generated project file and one message payload. Everything else
is derived from data that 021/028/029 already store.

## 1. Pipeline state — `assistant_command_run.result["pipeline"]`

Written on the first `speckit-all` run and copied forward, unmodified except for the fields below,
to every stage run of the same pipeline.

| Field | Type | Rules |
|---|---|---|
| `id` | int | Id of the first `speckit-all` run of this pipeline. Stable for the whole run; the resume key. |
| `stages` | string[] | Always `pipeline.STAGES` (8 values, fixed order). A stored value that differs from the code is ignored and rewritten. |
| `cursor` | int | Index in `stages` of the stage that is **next to open**. `0 ≤ cursor ≤ 8`; `8` means "pipeline finished". |
| `until` | string \| null | One of `stages`, or `null` (no early stop). Set once, from `--until`. |
| `specs` | string[] | Spec folders this pipeline owns, in execution order (integration before report, then by number). |
| `spec_index` | int | Index in `specs`. `0 ≤ spec_index < len(specs)`. |
| `round` | int | Convergence rounds spent on the current spec, `0..2`. |
| `verify_cycles` | int | Fix-and-re-verify cycles spent on the current spec, `0..3`. The cap is *enforced* by counting the spec's `speckit-verify` runs (authoritative); the field mirrors it for the report. |

Rules

- `cursor` and `spec_index` are advanced only by `pipeline.next_stage()`; the cursor of a finished
  pipeline stays at the last stage so the report can name where it stopped.
- `until` never moves the cursor backwards; a stage after `until` is refused.
- A resumed pipeline keeps `id` (the report names the original run) and keeps `specs` unless the
  request named another spec.
- `round`/`verify_cycles` reset to `0` when `spec_index` advances.

## 2. Stage record — one `assistant_command_run` row per stage

Already existing rows; the pipeline adds two facts to them:

| Fact | Where | Rule |
|---|---|---|
| Which pipeline it belongs to | `result.pipeline.id` | equal to §1 `id` |
| Position in the plan | `result.pipeline.cursor` at open time | `0..7`; equal to the index of this run's stage |

`command` is the stage's own name (`speckit-specify` … `speckit-verify`), never `speckit-all`, so
`guard.py` keeps enforcing the stage's scope. `spec`, `resolved_from`, `forced`, `files`, `tokens`
keep their 021 meaning.

## 3. Stage → command and tool scope

| # | Stage | Command run | Writes | Tools |
|---|---|---|---|---|
| 1 | specify | `speckit-specify` | `new_spec` | `propose_draft`, `edit_draft` |
| 2 | clarify | `speckit-clarify` | `spec_doc`, `req_checklist_toggle` | `edit_draft` |
| 3 | plan | `speckit-plan` | `plan_docs` | `propose_draft`, `edit_draft` |
| 4 | tasks | `speckit-tasks` | `tasks_doc` | `edit_draft` |
| 5 | analyze | `speckit-analyze` | — | — |
| 6 | implement | `speckit-implement` | `kind_artifacts`, `tasks_ticks`, `status_implemented` | `propose_draft`, `edit_draft`, `check_query`, `run_preview` |
| 7 | converge | `speckit-converge` | `tasks_append` | `edit_draft`, `check_query`, `run_preview` |
| 8 | verify | `speckit-verify` | — | `check_query`, `run_preview` |

`analyze` and `verify` are read-only by construction, so a finding is fixed by re-opening `clarify`,
`plan`, `tasks`, `implement` or `converge` — the stage that owns the file.

## 4. Completion of a stage (`pipeline.completed`)

| Stage | Proven complete when |
|---|---|
| specify | `specs/<spec>/spec.md` exists |
| clarify | `specs.stage()` ≥ `aclarada`, or `revised_by(spec.md, "speckit-clarify")`, and no `[NEEDS CLARIFICATION` remains |
| plan | `specs/<spec>/plan.md` exists |
| tasks | `specs/<spec>/tasks.md` exists |
| analyze | cursor > 4 for this spec, or a `run-report.md` records it (it writes nothing) |
| implement | `specs.stage()` ∈ {`implementada`, `aplicada`} |
| converge | `specs.converged()` is false (a converge that left open tasks is complete) |
| verify | `session.validation.valid` and the last preview for the spec's artifacts is `succeeded` |

`--force` ignores this table for every stage.

## 5. Decision — lines under `## Decisiones tomadas (modo autónomo)` in `spec.md`

```markdown
## Decisiones tomadas (modo autónomo)

- [clarify] La factura se agrupa por día y estado; el PDF usa la vista «Resumen» — es el orden que
  el spec ya usa en las historias y no añade un dataset.
```

Rules (validated by guard rule `decisions_append`)

- Only additions inside that section; the rest of `spec.md` must be byte-identical.
- The section, if present before, must be a prefix of the new one.
- One line per decision, `- [<stage>] <decision> — <why>`; `<stage>` ∈ `STAGES`.
- They are copied verbatim into the run report (§6).

## 6. Run report — `specs/<spec>/run-report.md`

    # Run report · <spec>

    **Run**: <pipeline id> · <started> → <ended> · <n> stages · <tokens> tokens
    **Result**: Listo para aplicar | Aplicado · versión N | Detenido: <stop_reason>

    ## Stages
    | # | Stage | Command run | Status | Files |
    |---|-------|-------------|--------|-------|
    | 1 | specify | 128 | completed | specs/…/spec.md |

    ## Decisiones tomadas
    <the block of §5, verbatim>

    ## Verificación
    | Check | Result | Detail |
    |-------|--------|--------|
    | validation | ok | — |
    | check_query integrations/<id>/queries/x.sql | ok | — |
    | preview | ok | 3 datasets · 412 rows |
    | US1 Independent Test | pass | 412 rows in `facturas_dia` |

    ## Pendiente para el humano
    - Aplicar (el contrato no permite `apply`).

Rules

- Written by `pipeline.write_report()` through `fs.apply_ops` under guard rule `run_report`.
- Re-writing the same stage result produces no diff (idempotent: same inputs → same bytes).
- "Pendiente para el humano" lists at most the three known items (Aplicar, a source that must be
  created, a constitution amendment); when there are none the section is omitted — that is SC-003.

## 7. Message payload — the card

The last assistant message of the pipeline carries

```json
{"run_report": {"spec": "002-ventas-facturacion", "path": "specs/002-ventas-facturacion/run-report.md",
                "result": "ready|applied|stopped", "stop_reason": null,
                "stages": [{"stage": "specify", "run_id": 128, "status": "completed"}],
                "pending": ["apply"]}}
```

built from the same data as §6 (the file is the durable copy; the payload is what the card renders).

## 8. Transitions

    idle ──/speckit-all + contract──► running(cursor=0)
    running ──run_command next stage──► running(cursor+1)
    running ──last stage done──► writing report ──► completed
    running ──limit | stop | provider code | verdict cap──► stopped(stop_reason)
    stopped ──/speckit-all <id>──► running(cursor = first incomplete stage)
    completed(ready) ──apply (028)──► reported "Aplicado · versión N" on the next run

A stage that ends `misrouted` (029) stops the pipeline: writing to another spec means the plan is
wrong, and the report names it.
