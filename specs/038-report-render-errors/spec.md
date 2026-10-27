# Feature Specification: Report render errors — a failing tile says which piece failed, and a preview that expired says so

**Feature Branch**: `038-report-render-errors`

**Created**: 2026-10-26

**Status**: Implemented

**Input**: Production, 2026-10-26 15:15, project `coinmarketcap` (version 22 just applied): pressing
`panorama-cripto` under **Vista previa** (and `PDF de vista previa: panorama-cripto`) answered
`Ocurrió un error inesperado (referencia e8c808976283)`. Validation had passed, so the failure was
at render time — and nothing on screen named the piece that failed.

**Builds on**: 005 (report engine, PDF), 014/020 (draft preview into `preview_<session>` schemas,
projects), 026 (declarative layouts, per-component error cards, FR-006 "never a blank dashboard"),
030 (preview PDF that names its report), 035 (specific codes and technical details on screen),
037 (project isolation).

## Problem

1. **The preview outlived its data.** Applying a version drops the session's preview schemas
   (`apply_project` → `drop_for_session`) but left `project.preview` as `succeeded`, so the
   workspace page kept the «Vista previa» links. Pressing one ran a report query against schemas
   that no longer existed and the generic handler answered 500 with a reference nobody can act on.
2. **One bad piece took the whole dashboard.** `run_views` computed every view in one batch and let
   the first exception out: a missing table, a metric that divides by zero or an unknown format
   produced the same anonymous 500 for the entire report — and for the PDF, which shares the payload.
3. **The codes existed in the log only.** `pg_errors.UndefinedTable`, `DivisionByZero`, an unknown
   join or an unmapped PDF block were logged (or swallowed, for an unknown PDF block type) and
   reached the reader as «error inesperado».

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The tile that cannot render says which piece failed (Priority: P1) 🎯

A metric divides by zero, a dataset table is gone, a format is not in the catalogue. The tile (or
PDF block) shows an error card with the code, the report, the dataset/metric/component/block and the
reference; every other tile of the dashboard and the whole PDF still render.

**Acceptance**: `metric_error`, `dataset_missing`, `format_unknown`, `layout_component_unknown` and
`pdf_render` each produce a card naming their ids; the rest of the payload has no `error`.

### User Story 2 - A preview that no longer exists says so and stops being offered (Priority: P1) 🎯

After an apply the preview schemas are gone. The «Vista previa» links disappear and a line says
which version replaced them; a stale tab that asks anyway receives `preview_expired` (409), never a
500. If the schemas disappeared without the apply (cleanup), the first read retires the preview.

**Acceptance**: `project.preview.status == "replaced"` with the applied version after an apply;
`GET …/preview/report/<id>/data` → 409 `preview_expired`; the page shows the applied dashboard.

### User Story 3 - An empty period is a state, not a failure (Priority: P2)

A dataset with no rows (a preview window before the extract, a quiet period) renders the tile with
«Sin datos» and, in the technical details, `empty_dataset` naming the datasets without rows.

### User Story 4 - Multi-dataset reports render (Priority: P2)

A report that joins two, three or four datasets on one key renders from the preview schema and from
an applied version, in JSON and PDF; a join that cannot be built is a typed error (sets and key),
never a runtime 500.

## Functional requirements

- **FR-001** The engine keeps a catalogue of render codes: `preview_expired`, `dataset_missing`,
  `join_failed`, `empty_dataset`, `metric_error`, `layout_component_unknown`, `format_unknown`,
  `pdf_render`.
- **FR-002** A report failure carries the code, the report id, the reference and the ids of the
  failing piece. It never carries a row value (constitution VIII).
- **FR-003** Views fail individually: the payload of a failed view carries `error` (card) and the
  other views render. A KPI row whose combined query fails retries metric by metric so only the bad
  metric shows a card.
- **FR-004** A view with no data carries `empty` (`empty_dataset`, the datasets without rows); the
  screen and the PDF show «Sin datos».
- **FR-005** Applying a project marks its preview `replaced` with the applied version, and the
  workspace page stops offering the preview links.
- **FR-006** Reading a preview whose schemas are gone answers 409 `preview_expired` and retires the
  preview (`expired`), so the links disappear by themselves.
- **FR-007** A PDF block that cannot be drawn becomes a card with `pdf_render` and its block id; the
  document still renders. An unknown block type is `layout_component_unknown`.
- **FR-008** Every message and label is Spanish and English.
- **FR-009** The error card's «Detalles técnicos» shows the code, the reference, the report and the
  failing ids, and the backend log command that finds the line.
- **FR-010** The engine reads only optimized models or the preview schemas of the running preview
  (constitution II/VI); no new source read is introduced.

## Success criteria

- `panorama-cripto` (four datasets joined on `snapshot_at`) renders in JSON and PDF from the preview
  and from the applied version, with full data, one empty dataset and no comparison period.
- Every code above has a test that triggers it and asserts that the rest of the payload still
  renders.
- A preview that expired or was replaced never answers 500.
