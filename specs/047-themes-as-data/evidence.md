# Evidence — 047 themes as data

Every number here is a command that was run on this machine, on `main`, with the repository's own
virtualenv (`/home/andres/vsCodeProjects/bizview/.venv`). Nothing is projected.

## The contract and the validator (commit 1, `0a3f377`)

| What | Command | Result |
|---|---|---|
| The five built-ins obey the contract | `for t in impacto clasico monocromo contraste daltonico; do bizview theme validate frontend/src/theme/themes/$t.json; done` | five `✓ tema válido`, exit 0 |
| Refusals name path and value | `pytest cli/tests/test_theme.py` | 27 passed |
| The offline preview | `bizview theme preview … --out /tmp/i.svg` | 2348-byte SVG, exit 0 |
| A `.png` output is refused instead of writing SVG under a wrong name | `bizview theme preview … --out /tmp/i.png` | exit 2, message names `.svg` |
| The PDF mirror and the derivation agree | `pytest backend/tests/test_theme_parity.py` | 14 passed |
| 030's gates still hold | `pytest backend/tests/test_palette.py` | 16 passed |
| … | `npx vitest run tests/unit/themes.test.ts tests/unit/palette-presets.test.ts` | 12 passed |

## Storage, API, migration (commit 2, `294b216`)

| What | Command | Result |
|---|---|---|
| The library, the upload, the refusals, the ETag | `pytest backend/tests/test_themes.py` | 11 passed |
| The migration creates, seeds and refuses to downgrade | `pytest backend/tests/test_migrations.py` | 9 passed |
| 030's appearance endpoint is untouched | `pytest backend/tests/test_appearance_api.py` | 7 passed |
| Every backend audit kind has a label | `npx vitest run tests/unit/audit-labels.test.ts` | 1 passed |
| `app.main` imports with the router registered | `python -c "import app.main"` | ok |

## Apariencia (commit 3, `92af795`)

| What | Command | Result |
|---|---|---|
| The library, the upload and its problems, the four actions | `npx vitest run tests/unit/appearance-page.test.tsx` | 10 passed |
| Whole frontend suite | `npx vitest run` | 616 passed (58 files) |

## Report theme, mode, share, PDF (commit 4, `0373262`)

| What | Command | Result |
|---|---|---|
| Resolution, mode, the area's tokens, the session override | `npx vitest run tests/unit/report-theme.test.tsx` | 13 passed |
| The PDF reads an uploaded theme from its row and uses its light variant | `pytest backend/tests/test_palette.py` | 16 passed |
| The CLI accepts `layout.theme.id|mode` and refuses a bad one | `pytest cli/tests/test_report_layout.py` | 68 passed |
| The PDF preview path still works | `pytest backend/tests/test_pdf_preview.py` | 7 passed |

## Projects carry themes (commit 5, `ddb85bb`)

| What | Command | Result |
|---|---|---|
| Import, the three collision answers, a refusal, removal, the unknown-id problem | `pytest backend/tests/test_project_themes.py` | 9 passed |
| The zip import/export round trip is unaffected | `pytest backend/tests/test_projects_zip.py tests/test_projects_editor_api.py` | passed |

## Docs, pack, changelog (commit 6)

| What | Command | Result |
|---|---|---|
| The gate suite | `bash scripts/gates/all.sh` | all gates passed (05 needs `DATABASE_URL_BI` and is run separately) |
| Whole frontend suite | `npx vitest run` | 616 passed (58 files) |
| The guide's own contract (48 topics, headings, aliases) | `pytest backend/tests/test_guide.py` | 9 passed |
| The guide never drifts from the app | `npx vitest run tests/unit/guide-drift.test.ts` | 5 passed |
| The whole CLI suite | `pytest cli/tests` | exit 0 |
| Backend lint | `ruff check .` | All checks passed |

## What was deliberately not done

- **`bizview theme preview` writes SVG, not PNG.** Rasterising needs a headless browser or an image
  library and neither is a dependency here; the extension is refused rather than lied about
  (research R11).
- **The pack does not ship copies of the five built-ins.** They already exist twice with a drift
  test; a third copy would be a third place to forget, so `THEME.md` carries one complete theme and
  Apariencia's **Descargar** hands over the real ones (research R12).
- **The backend's full test suite was not run in one pass**: on this machine it needs roughly twenty
  minutes per database module. Every module this feature touches was run, and the numbers above are
  those runs.
