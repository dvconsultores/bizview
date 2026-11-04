# Implementation Plan: Per-source structure and the read-only structure chat

**Branch**: `052-source-structure-chat` (worked on `main`) · **Date**: 2026-11-03 ·
**Spec**: [spec.md](./spec.md)

## Summary

The product can already *read* a source's structure (`GET /api/sources/{name}/describe`) but the
only way to see it is a token, a terminal and `bizview describe`. This feature puts that output on
the source page — a second tab, **Estructura** — renders it, lets the super user download it in the
authoring pack's own format, and adds a chat that answers questions about *that structure only*.

Three pieces of code carry the whole feature:

1. **One generator** in `cli/bizview_cli/structure.py`: `structure.json` and `structure.md` are
   produced there, so the CLI (`bizview describe --pack`), the API (`GET .../structure?format=`), the
   UI download and the future authoring pack cannot drift. It lives in `cli/` because the backend
   already depends on that package (`app/projects/zip.py` imports `bizview_cli.budgets`) and the
   constitution makes `cli/` the single source of the authoring contract.
2. **A chat service** in `backend/app/ai/chat.py`: a product-code refusal guard, a size-bounded
   context built from the same pack, the provider's `complete()`, object-name validation of the
   answer, a per-user daily token cap and audit of counts. No tools, no file writes, no row reads.
3. **The tab** in `frontend/src/pages/admin/SourceStructure.tsx`, with the chat in a non-modal panel
   beside it (`StructureChat.tsx`) and the existing form untouched under the `Conexión` tab.

No new dependency, no new stack component, no change to how sources are read today.

## Technical Context

**Language/Version**: Python 3.11+ (backend, FastAPI), TypeScript 5 / React 19 (frontend)
**Primary dependencies**: none added — `httpx`/`psycopg`/`zeep` describe the sources,
`anthropic`/OpenAI-compatible `complete()` answers, `jsonschema` already validates artifacts
**Storage**: PostgreSQL — three new tables and one column (`data_source.notes`), migration
`0049_source_structure`
**Testing**: `pytest` (backend, `uv run pytest`), `vitest` (frontend unit), `pytest` in `cli/`
**Target Platform**: the existing container (backend image ships `cli/` + `backend/` only)
**Constraints**: structure only — no credentials, hosts or row values; AI optional (VIII);
ES + EN for every string; the tab must render in < 10 s on the demo sources
**Scale/Scope**: one source at a time; catalogues of 1 000+ tables truncated per schema; chat
context capped at ~60 000 characters (~15 k tokens)

## Constitution Check

| Principle | Effect |
|---|---|
| I. Mobile-first | The tab is designed at 375 px first: tabs on top, structure list stacked, chat as a bottom sheet; the two-pane layout starts at `lg` |
| II. Backend as ETL | Untouched: the structure read is describe (metadata), never a report path |
| III. Source of truth is external | Describe and samples are read-only through the catalogue's credential; `path` relative, `same_origin`, guarded client |
| IV. Folder separation | Generator in `cli/bizview_cli/structure.py` (shared), service glue in `backend/app/sources/`, chat in `backend/app/ai/`, UI in `frontend/src/pages/admin/` |
| V. Fixed stack | No component added or removed; no new dependency |
| VII. Many installations | No customer names; the personal-data heuristic list is generic |
| VIII. AI optional and private | This is the second AI surface (with help) and the reason for **PATCH 3.2.1 → 3.2.2**: the principle lists the structure chat beside help, and the inputs are the structure pack only |
| IX. Spec-driven reporting | Untouched: nothing here authors a project |
| Constraints | Every string ES + EN; no credentials returned or logged; no writes to the origin |

**Gate: PASS**, with the VIII amendment (PATCH 3.2.2) applied before implementation.

## Architecture

```
GET /api/sources/{name}/describe            (exists, unchanged)
        │  describe JSON (structure only)
        ▼
cli/bizview_cli/structure.py ──────────────► structure.json  (pack header + structure)
   build_pack(describe, source, flags, notes)   structure.md  (the pack template, filled)
   structure_markdown(pack)
   structure_json(pack)
        ▲                    ▲                          │
        │                    │                          ▼
   bizview describe     backend/app/sources/      GET /api/sources/{name}/structure?format=md|json
   --pack               structure.py (flags,      (download, audited as source_described)
                        notes, BI-ready flag)
                                   │
                                   ▼
                        backend/app/ai/chat.py ──► provider.complete(system, prompt)
                          guard → context → call → validate names → usage
```

**Why the generator lives in `cli/`.** Two callers must produce the same bytes: the terminal
(`bizview describe --pack`, no product code involved) and the API. The backend already imports
`bizview_cli` (project export, import budgets, layout), and the constitution says `cli/` owns the
contract the authoring pack reads. A backend-only generator would force a second copy in the CLI,
which the Constraints section calls a defect.

**Why `structure.json` is a wrapper, not a new schema.** The body under `"structure"` is exactly
what `/describe` returns, so `bizview validate --describe NAME=FILE` keeps working —
`structure_from()` learns to look inside the wrapper when it is there. The `pack` header carries
what the markdown needs and what a reader needs to trust the file: source name, kind, when it was
read, the BI-ready flag, the notes and whether anything was truncated.

## Phase 0 — Research

See [research.md](./research.md): R1 generator home, R2 markdown fidelity, R3 date ranges without
row values, R4 refusal in code, R5 token cap accounting, R6 the sample-request method, R7 how the
chat stays inside the context window, R8 what the personal-data heuristic is.

## Phase 1 — Design

- **[data-model.md](./data-model.md)**: the three tables, the `notes` column, the two file shapes
  and the chat payloads.
- **[contracts/api.md](./contracts/api.md)**: every route, its permission, its audit entry and its
  error codes.
- **[contracts/structure-pack.md](./contracts/structure-pack.md)**: what `structure.md` and
  `structure.json` must contain, section by section, and what must never appear in them.
- **[quickstart.md](./quickstart.md)**: how to see the tab and how to prove the claims.

## Phase 2 — Implementation order

1. **Generator** (`cli/bizview_cli/structure.py` + `bizview describe --pack` + `structure_from`
   compatibility). Provable offline, no database.
2. **Describe enrichment**: foreign keys, date min/max (capped), so the generator has something to
   print for PostgreSQL.
3. **Model + migration** `0049_source_structure`, with `APP_TABLES` updated.
4. **API**: structure download, personal flags, notes, sample requests, chat — each audited.
5. **Chat service**: guard, context, provider call, validation, cap.
6. **Frontend**: tabs, structure view, downloads, samples, chat panel, i18n.
7. **Guide topics** (033 format) and the drift tests they need.
8. **Tests** at every step, in the same change.

## Project Structure

```text
cli/bizview_cli/structure.py                     generator shared by CLI and API (new)
cli/bizview_cli/describe.py                      --pack, structure_from accepts the wrapper
cli/bizview_cli/__main__.py                      describe --pack, --out

backend/app/sources/describe.py                  foreign keys + date ranges, capped
backend/app/sources/structure.py                 flags, notes, pack assembly, audit (new)
backend/app/sources/samples.py                   sample request execution + suggestions (new)
backend/app/ai/chat.py                           guard, context, call, validation, cap (new)
backend/app/ai/prompts/source_structure.md       the system prompt (new data file)
backend/app/api/sources.py                       the new routes
backend/app/models.py                            3 tables, notes column, audit kinds
backend/alembic/versions/0049_source_structure.py
backend/app/worker.py                            purge chat history after 30 days
backend/app/guide/{es,en}/*.md, index.yaml       three topics

frontend/src/pages/admin/SourceForm.tsx          tabs Conexión | Estructura
frontend/src/pages/admin/SourceStructure.tsx     the tab (new)
frontend/src/components/StructureChat.tsx        the chat panel (new)
frontend/src/api/types.ts, api/sources.ts        types + the source structure API (new)
frontend/src/i18n/{es,en}.ts                     strings
frontend/tests/unit/source-structure.test.tsx    tab + chat behaviour

backend/tests/test_source_structure.py           generator, downloads, flags, notes, samples
backend/tests/test_source_structure_chat.py      context audit, refusals, validation, cap
cli/tests/test_structure_pack.py                 the generator from the terminal
```

## Risks and how they are handled

| Risk | Handling |
|---|---|
| A chat that quietly reads data | The chat receives the *pack*, never a connector; the guard refuses data questions before any provider call; a payload test asserts the request body |
| Hallucinated objects reaching a spec | Every object-shaped token in an answer is checked against the pack; unknown ones are returned as `unknown` and chipped in the UI |
| Describe becomes slow on a big catalogue | Date ranges are capped at 3 columns per table and 300 tables; a failure to read one column's range never fails the describe |
| Two generators drifting again | One module, two callers, and a test that runs the CLI and the API on the same fixture and compares bytes |
| New tables forgotten in the migration test | `test_migrations.py`'s `APP_TABLES` is updated in the same change |

## Complexity Tracking

No constitution violation to justify. The VIII amendment is a clarification of scope (which AI
surfaces exist), not a relaxation: the chat has fewer capabilities than the help agent it joins.
