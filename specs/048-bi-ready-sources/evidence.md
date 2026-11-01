# Evidence — 048 BI-ready sources

Every line is a command run on this machine, on `main`, with the repository's own virtualenv.
Nothing is projected, and nothing that was not run is claimed.

## Phase 0 — the constitution (commit `be685fa`)

| What | Command | Result |
|---|---|---|
| The amendment renders and its links resolve | `bash scripts/gates/08-markdown.sh` | ok |
| The version moved, nothing was renumbered downwards | `grep '**Version**' .specify/memory/constitution.md` | `3.2.0 … Last Amended: 2026-11-01` |

## Phase 1 — the declaration and its proof (commit `e5be4b3`)

| What | Command | Result |
|---|---|---|
| Bounds, the deny-list refused inside `schemas`, non-PostgreSQL refused, a writable credential refused and not stored, the 019 backfill, one message key per refusal | `pytest backend/tests/test_bi_ready_declaration.py` | 20 passed |
| Both migrations apply, seed and refuse to run backwards; models and migrations agree | `pytest backend/tests/test_migrations.py` | 9 passed |
| `app.main` imports with the new routes and payloads | `python -c "import app.main"` | ok |

## Phase 2 — the scope holds (commit `992b50b`)

| What | Command | Result |
|---|---|---|
| The short form resolves its columns; a missing object is a problem; an object outside the declaration is refused with the fix named; offline it only warns; the 019 shape is untouched | `pytest cli/tests/test_direct_bi_ready.py` | 6 passed |
| The scope is asked again at execution, and at the two render funnels | `pytest backend/tests/test_bi_ready_declaration.py -k "engine or renders"` | 2 passed |
| 019's direct suites, including «a report with the flag off never connects» | `pytest backend/tests/test_direct_sources.py tests/test_direct_engine.py` | pass |
| The whole CLI suite | `pytest cli/tests` | exit 0 |

## Phase 3 — the source page (commit `992b50b`)

| What | Command | Result |
|---|---|---|
| The section appears only for PostgreSQL, sends the declaration, shows the badge and the last day | `npx vitest run tests/unit/source-direct-flag.test.tsx` | 8 passed |
| Every new label exists in both languages; no literal in a component | `npx vitest run tests/unit/no-literals.test.ts tests/unit/i18n-parity.test.ts` | pass |
| Every backend audit kind has a label | `npx vitest run tests/unit/audit-labels.test.ts` | 1 passed |
| Whole frontend suite | `npx vitest run` | 617 passed (58 files) |

## Phase 4 — the daily snapshot (commit `cc75e5f`)

| What | Command | Result |
|---|---|---|
| One row per report/day/parameters, newest wins, a month kept, the notice | `pytest backend/tests/test_direct_snapshot.py` | 6 passed |
| Migration `0045` applies and the models match it | `pytest backend/tests/test_migrations.py` | 9 passed |

## Phase 5 — docs, guide, changelog

| What | Command | Result |
|---|---|---|
| The gate suite | `bash scripts/gates/all.sh` | all gates passed (05 needs `DATABASE_URL_BI` and runs alone) |
| The guide's own contract (48 topics, headings, aliases, bold labels are real labels) | `pytest backend/tests/test_guide.py` and `npx vitest run tests/unit/guide-drift.test.ts` | 9 and 5 passed |
| Backend lint | `ruff check .` | All checks passed |

## What this feature did **not** do, and why

- **It did not build the protections the brief lists as missing.** They already shipped in 019 —
  read-only session, `SET LOCAL statement_timeout`, per-source concurrency, cached result, deny-list,
  read log — and the specification says so with file references. What 048 adds is the declaration.
- **It did not build the 043 WS-B structure-pack zip** (`sources/<name>/structure.md`): that part of
  043 was never implemented and has no consumer. `describe`'s JSON payload — what `bizview describe`
  already reads — is what now carries the BI-ready marking (research R7).
- **It did not add a notification system.** There is none in the product; "notified" is the audit
  event (`source_bi_ready_verified` / `source_bi_ready_unverified`) plus the badge and the date on
  the source page. Inventing a notification subsystem was a bigger feature than this one.
- **The scope is typed, not picked from a widget.** The schema and object lists are comma-separated
  inputs validated by the server, not a tree built from `describe`; a picker would be nicer and is
  the obvious next step.
- **`scripts/gates/05-migration.sh` was not run**: the only `DATABASE_URL_BI` configured points at a
  shared server, and creating/dropping `app_test_*` schemas there is not this feature's decision.
  `tests/test_migrations.py` covers both new migrations end to end.
