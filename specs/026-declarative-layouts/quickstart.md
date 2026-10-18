# Quickstart: proving declarative layouts work

Validation scenarios for `specs/026-declarative-layouts`. Each one is runnable on its own and proves
one user story. Shapes and field names come from [data-model.md](./data-model.md) and
[contracts/](./contracts/); nothing here is implementation code.

## Prerequisites

- Python 3.11+ with `uv` (backend and CLI), Node 24 with npm (frontend).
- A PostgreSQL instance: `backend` tests need `CI_DATABASE_URL` (or `DATABASE_URL_BI` locally plus a
  test database URL) and create their own temporary `app_test_*` schema.
- Playwright browsers once: `cd frontend && npx playwright install` (or `--with-deps`).

Commands are the ones `CONTRIBUTING.md` and `.github/workflows/ci.yml` already use.

## Scenario 1 — a dashboard composed by a layout (US1)

```sh
cd cli     && uv run bizview validate ../cli/bizview_cli/golden   # the golden layout is valid
cd cli     && uv run pytest tests/test_report_layout.py
cd frontend && npm test                                            # component kinds + grid
cd frontend && npx playwright test tests/e2e/layout.spec.ts        # 375 px and 1280 px, both themes
```

Expected:
- the golden report validates with **no errors** and no layout warnings;
- the dashboard renders KPI → line → bar → table in the declared order, in the declared spans at
  1280 px, and stacked in the same order at 375 px;
- changing `layout.web.components[1].view` to a view that does not exist makes `bizview validate`
  fail with `path: /layout/web/components/1/view`;
- deleting `layout.web` restores today's `data.views` order (FR-009) with no other diff.

## Scenario 2 — the same report as a one-page PDF (US2)

```sh
cd backend && uv run pytest tests/test_pdf_declarative_layout.py tests/test_layout_parity.py
cd backend && uv run pytest tests/test_pdf_layout.py                # the fixed template still passes
```

Expected:
- the one-page golden layout produces exactly one page;
- a 500-row table block renders in under 10 s (SC-003);
- with `overflow: truncate` the table ends with "y N más" and the row count of the remainder; with
  `continue` the header repeats on the next page;
- for one query string, every figure in `GET /api/reports/{id}/data` appears in the PDF text read by
  `tests/test_reports_params.py::_pdf_lines` (SC-002);
- a block with an unknown `type` fails validation before any PDF is built.

Manual check against a running stack:

```sh
docker compose up -d --build
curl -s -o /tmp/ventas.pdf -X POST 'http://localhost/api/reports/ventas/pdf?period=this_month'
file /tmp/ventas.pdf          # → PDF document, 1 page (as declared)
```

## Scenario 3 — preview inside the Asistente (US3)

```sh
cd backend  && uv run pytest tests/test_assistant_preview.py
cd frontend && npx playwright test tests/e2e/assistant.spec.ts
```

Expected: a complete draft carrying both layouts shows the dashboard from `layout.web` in
**Vista previa** and offers **PDF de vista previa** built from `layout.pdf`; a layout problem is
listed with file, JSON path and the expected fragment, like any other draft problem (015 FR-003).

## Scenario 4 — a human edits the layout by hand (US4)

```sh
cd cli && uv run bizview init /tmp/ws-layout --name layout-demo --agent claude --no-git
# edit /tmp/ws-layout/projects/<slug>/reports/<id>/report.yaml and add a layout.web block
cd cli && uv run bizview validate /tmp/ws-layout
cd cli && uv run pytest tests/test_report_layout.py tests/test_authoring.py
```

Expected:
- a valid layout → exit code `0`, no messages;
- a dangling reference → exit code `1`, an error naming the file and the JSON Pointer;
- an unsuitable chart (a pie over 40 categories) → a **warning** (exit code `0`) and the renderer's
  documented fallback;
- the authoring guide (`authoring.guide("report")`, and the human pages under
  `backend/app/assistant/guide/es|en/`) documents every component and block with one example.

## Scenario 5 — nothing changes when no layout is declared (SC-006)

```sh
cd backend  && uv run pytest tests/test_report_regression_019.py tests/test_vibe_reporting.py
cd frontend && npm test && npx playwright test tests/e2e/reporting.spec.ts tests/e2e/report-params.spec.ts
```

Expected: every existing report renders identically — the same view order, the same PDF story, the
same API payload except the additive `summary` field.

## Scenario 6 — no executable content gets in (SC-004)

```sh
cd backend && uv run pytest tests/test_draft_content_check.py
```

Expected: all 50 adversarial drafts are rejected with a problem that names the file and the offending
line, and no file is written; a legitimate layout draft with YAML only is accepted.

## Full gate before declaring the feature done

```sh
cd backend  && uv run ruff check app tests alembic && uv run pytest
cd cli      && uv run ruff check . && uv run pytest
cd frontend && npx tsc --noEmit -p . && npm test && npm run build && npm run check:compat
cd frontend && npm run e2e
```

Plus the live eval of SC-005 (`backend/tests/live/`, 015 SC-001): the Asistente proposes a valid
`layout.web` and `layout.pdf` on the first validation pass in at least 4 of 5 runs.
