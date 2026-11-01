# Evidence — 046 release, documentation and governance

Every command below was run on this tree and its result pasted, not recalled.

## Gates

| Gate | Command | Result |
|---|---|---|
| all | `sh scripts/gates/all.sh` | `all gates passed` |
| 01 vocabulary | `sh scripts/check_vocabulary.sh` | exit 0 (was 8 hits before the rewrite) |
| 07 version | `sh scripts/gates/07-version.sh` | every copy `0.2.0`; `/api/health` half skipped (no backend on `:8081`) |
| 08 markdown | `sh scripts/gates/08-markdown.sh` | `ok` |

### Each new gate proved to fail on a reintroduced offence

| Offence | Gate | Exit |
|---|---|---|
| `"version": "0.1.0"` in `frontend/package.json` | 07 | 1 |
| `# asistente` in a document | 01 | 1 |
| a relative link to a missing file | 08 | 1 |
| a table row with one cell too many | 08 | 1 |
| an unclosed fenced block | 08 | 1 |
| `README.es.md` with fewer sections than `README.md` | 08 | 1 |

Each was reverted and the gate returned to 0.

## Suites

| Suite | Command | Result |
|---|---|---|
| Backend lint | `ruff check app tests alembic` | All checks passed |
| CLI lint | `ruff check .` (in `cli/`) | All checks passed |
| Backend i18n, AI and PDF | `pytest tests/test_ai.py tests/test_ai_status.py tests/test_pdf_preview.py tests/test_i18n_catalogue.py` | 63 passed, 1 skipped |
| Help guide | `pytest tests/test_guide.py tests/test_i18n_catalogue.py` | 14 passed |
| Frontend types | `npx tsc --noEmit` | clean |
| Frontend units | `npx vitest run` | 56 files, 592 tests passed |
| Installer | `bash deploy/tests/test_install.sh` | 62 passed, 0 failed |

## Defects this feature found and fixed

1. **`backend/tests/test_pdf_preview.py` imported `pdf.render_preview`**, which 045 deleted with the
   draft preview: the module could not be collected. Its two preview-route assertions were removed
   with the route; the rendering it also covered (every legacy view shape, the declared order) is
   now asserted against `pdf.render`, which is what a published report and a share link use.
2. **`backend/app/guide/es/definir-un-reporte.md` was 6043 bytes against the guide's 6000-character
   cap** — 045's string replacements pushed it over, and `test_guide.py` refused to load the guide.
   Trimmed to 5998 without losing a rule.
3. **Two help topics told the reader about a chat** (`ia.md`, `ayuda.md`, `estructura-de-proyecto.md`,
   `proyectos.md`) and one bold span claimed a screen message the catalogue no longer has; the drift
   guard caught it (`guide-drift.test.ts`) and the topics now quote the real labels.

## Version, before and after

| Copy | Before | After |
|---|---|---|
| `VERSION` | 0.1.0 | 0.2.0 |
| `backend/pyproject.toml` | 0.1.0 | 0.2.0 |
| `frontend/package.json` | 0.1.0 | 0.2.0 |
| `cli/pyproject.toml` | 0.3.0 | 0.2.0 |
| `cli/bizview_cli/__init__.py` | 0.4.0 | 0.2.0 |

Four different numbers for one release; `scripts/gates/07-version.sh` is what keeps that from
happening again.

## External dependency

`bizview-site` (the marketing repository) still carries the old hero line and the "AI Powered"
name. It is outside this repository: the owner listed here is **dvconsultores**, and the line to
ship there is the README's hero:
*"Your business data on your phone. Build the reports with any AI — Bizview validates, runs and
shares them."* This release does not block on it, and `CHANGELOG.md` records it.
