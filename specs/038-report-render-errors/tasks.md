# Tasks: Report render errors (038)

**Feature**: `038-report-render-errors` · [spec.md](./spec.md) · [plan.md](./plan.md)

## Phase 1 — Root cause and the typed catalogue

- [X] T001 `app/engine/render_errors.py`: `RenderError`, the code catalogue and the payload `card()`.
- [X] T002 `app/engine/report.py`: translate `pg_errors` into codes in `aggregate()`, guard
      `_column`/`from_clause` (`dataset_missing`, `join_failed`), validate formats per view.
- [X] T003 Engine: per-view isolation (`_run_view`), metric isolation for a KPI row
      (`_kpis_one_by_one`), derived facts that never break a view, `empty` detection.
- [X] T004 `render_reference` per payload (report routes and preview routes) logged at ERROR.

## Phase 2 — Preview lifecycle

- [X] T005 `app/projects/apply.py`: a preview becomes `replaced` with the applied version in the
      apply transaction.
- [X] T006 `app/assistant/preview.py`: `preview_expired` for `replaced`/`expired`, and when the
      preview schemas are gone the read retires the preview.
- [X] T007 Frontend: the workspace page drops the preview links and shows the replacing version with
      the applied dashboard.

## Phase 3 — Cards on screen and in the PDF

- [X] T008 `RenderErrorCard` with «Detalles técnicos» (code, reference, report, ids, log command).
- [X] T009 `LayoutRenderer` and `ReportViews`: a view's `error`/`empty` is its own card;
      `KpiGrid` renders the card of the metric that failed.
- [X] T010 `pdf_layout.render_layout`: unknown block and failing block become cards; the fixed story
      prints the card of an error/empty view.
- [X] T011 `es.ts`/`en.ts` and `app/i18n/{es,en}.py`: codes, labels, log command.

## Phase 4 — Tests, docs, changelog

- [X] T012 Fixture project `tests/fixtures/projects/coinmarketcap/` (four datasets joined on
      `snapshot_at`, report `panorama-cripto`, web + PDF layouts).
- [X] T013 Regression: JSON + PDF from the preview (full data, one empty dataset, no comparison) and
      from an applied version; the applied integration runs through the worker.
- [X] T014 Typed errors: `metric_error` (division by zero, only that metric fails),
      `format_unknown`, `dataset_missing`, `join_failed`/`unknown column`, `empty_dataset`,
      `layout_component_unknown` in the PDF.
- [X] T015 Preview after apply: `replaced` + 409 `preview_expired`; dropped schemas → `expired`.
- [X] T016 Join builder: two, three and four sets on one key, and a set without a join.
- [X] T017 Frontend unit test: the card of one tile while the others render.
- [X] T018 `docs/guides/tableros/errores.md` (one entry per code) and `CHANGELOG.md` under
      Unreleased.
