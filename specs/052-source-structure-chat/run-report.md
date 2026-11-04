# Run report — 052 per-source structure and the structure chat

**Run**: `/speckit-all 052-source-structure-chat` · 2026-11-03 · stages: specify → clarify → plan →
tasks → analyze → implement → converge → verify · scope agreed with the owner: **US1 + US2**, US3
(request-file drafts) deferred.

## Stages

| Stage | Result | Artifact |
|---|---|---|
| specify | spec written from `pendind_specs/052-…` and the code as it is (0.2.0) | [spec.md](./spec.md) |
| clarify | 7 questions answered from the constitution and the pack's own template, recorded in the spec | `## Clarifications` |
| plan | one generator, one chat service, one tab; constitution gate PASS with the VIII PATCH | [plan.md](./plan.md) · [research.md](./research.md) |
| tasks | 34 tasks in 10 phases | [tasks.md](./tasks.md) |
| analyze | 2 HIGH (per-schema checkboxes, 2 MB cap) and 2 MEDIUM (missing VIII task, AI page) fixed before code | `## Decisiones tomadas` |
| implement | all 34 tasks | this tree |
| converge | no unticked task left; nothing new to append | — |
| verify | every command below run; all green | — |

## Verification

| Command | Result |
|---|---|
| `cd cli && uv run pytest tests -q` | 33 passed |
| `cd cli && uv run ruff check bizview_cli tests` | clean |
| `cd backend && uv run pytest tests/test_source_structure.py -q` | 23 passed |
| `cd backend && uv run pytest tests/test_source_structure_chat.py -q` | 34 passed |
| `cd backend && uv run pytest tests/test_migrations.py tests/test_sources_api.py tests/test_ai.py tests/test_ai_status.py tests/test_admin_matrix.py -q` | 126 passed, 1 skipped |
| `cd backend && uv run pytest tests/test_guide.py tests/test_guide_api.py -q` | 12 passed (after the topic count 49 → 52) |
| `cd backend && uv run ruff check app tests` | clean |
| `cd frontend && npx vitest run` | 686 passed (64 files) |
| `cd frontend && npx tsc -b --noEmit` | clean |
| `cd frontend && npm run build` | built |
| `sh scripts/gates/01-vocabulary.sh` · `02-dead-code` · `03-dependencies` · `04-routes` · `06-settings` · `07-version` · `08-markdown` | all ok |
| `sh scripts/gates/05-migration.sh` | not run: it needs a disposable database, and the suite's `test_migrations.py` already applies every revision to a throwaway schema |

## What landed

- **One generator** (`cli/bizview_cli/structure.py`) behind three callers: the tab's download,
  `GET /api/sources/{name}/structure?format=md|json`, and `bizview describe --pack`. A test compares
  the two outputs byte for byte, so "one generator" cannot quietly become two.
- **The tab** (`frontend/src/pages/admin/SourceStructure.tsx` + `SourceForm` tabs): structure per
  kind, search, personal chips with a stored override, date ranges, notes, sample requests with
  **Ejecutar**, both downloads, **Actualizar**, and a chat beside it (a bottom sheet under `lg`).
- **The chat** (`backend/app/ai/chat.py`, prompt in `backend/app/ai/prompts/source_structure.md`):
  product-code refusal before any provider call, a 60 000-character context with a per-schema index
  fallback, object-name validation, a per-user/UTC-day token cap, counts-only audit, and 30-day
  retention purged by the worker.
- **Data**: `0049_source_structure` adds `source_sample_request`, `source_structure_flag`,
  `source_chat_message`, `data_source.notes` and eight audit kinds.
- **Guide**: three topics (`estructura-de-una-fuente`, `chat-de-estructura`,
  `peticiones-de-muestra`) in ES and EN with the routes the drift tests read.
- **Constitution**: VIII amended, 3.2.1 → 3.2.2, with its Sync Impact Report.

## Decisions worth remembering

- `AI_STRUCTURE_CHAT_*`, not the brief's `AI_CHAT_*`: that prefix belongs to the removed authoring
  agent and `scripts/gates/06-settings.sh` fails the build when it comes back.
- The sample-run failure is committed before the error is answered — otherwise the request's
  rollback erased the very record the tab shows.
- The chat reads its structure only when it is going to call the provider: a refusal or a spent
  budget costs no structure read.
- History is the last 20 rows ordered by `created_at, id`; several turns share a timestamp and the
  tie-break is what keeps a conversation in order.

## Pending for the human

- **US3** — the request-file drafts inside "Descargar paquete de autoría" and its live eval
  (`Panorama cripto` in ≤ 2 rounds): the pack zip itself is deferred with it, because the backend
  image does not ship `pack/`. Worth a follow-up spec.
- **Live eval** against the real CoinMarketCap source: the suite proves the payload and the
  rendering with fixtures; only a run against the customer's key can confirm the 10-second render.
- The pending brief `pendind_specs/052-source-structure-chat-spec.md` is retired by this run (its
  content lives in [spec.md](./spec.md), with the deferral recorded).
