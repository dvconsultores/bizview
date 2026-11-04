# Tasks: per-source structure and the read-only structure chat

**Feature**: `052-source-structure-chat` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Legend: `[P]` parallel-safe, `[US1]`/`[US2]` user story from the spec. Order is execution order;
a task is ticked only when it is implemented and its file exists.

## Phase 1 — one generator, offline provable (FR-003, US1/AC3)

- [x] T001 New `cli/bizview_cli/structure.py`: `is_personal(name)` with its two word lists,
      `infer_timestamp_units(value)`, `suggest(shape)`, `pagination_hint(shape)`, `build_pack(...)`,
      `structure_json(pack)`, `structure_markdown(pack)` — the markdown fills
      `pack/bizview-starter-pack/bizview-starter/sources/<nombre>/structure.md` section by section
- [x] T002 `cli/bizview_cli/describe.py`: `structure_from()` reads the `pack` wrapper when present,
      and `write_pack(pack, out_dir)` writes `structure.md` + `structure.json`
- [x] T003 `cli/bizview_cli/__main__.py` + i18n: `bizview describe <source> --pack [--out DIR]`
- [x] T004 `[P]` `cli/tests/test_structure_pack.py`: PostgreSQL / REST / SOAP fixtures, template
      headings present, seeded row values + host + credential absent, wrapper accepted by
      `structure_from`

## Phase 2 — describe says more (US1/AC1, US1/AC2)

- [x] T005 `backend/app/sources/describe.py`: foreign keys from `information_schema`, `min`/`max`
      of up to 3 date/timestamp columns per table (`MAX_DATE_COLUMNS`), never failing the describe
      when one range cannot be read
- [x] T006 `[P]` `backend/tests/test_source_structure.py` (describe half): ranges capped, missing
      permission tolerated, no value beyond the two aggregates, FK list on the demo shape

## Phase 3 — the data the feature owns (data-model.md)

- [x] T007 `backend/app/models.py`: `SourceSampleRequest`, `SourceStructureFlag`,
      `SourceChatMessage`, `DataSource.notes`, and the new `AUDIT_KINDS`
      (`source_structure_notes_updated`, `source_structure_flag_changed`,
      `source_sample_created`, `source_sample_updated`, `source_sample_deleted`,
      `source_sample_run`, `source_chat_asked`, `source_chat_cleared`)
- [x] T008 `backend/alembic/versions/0049_source_structure.py`: the three tables, the column, the
      recreated `audit_event.kind` check constraint
- [x] T009 `[P]` `backend/tests/test_migrations.py`: `APP_TABLES` gains the three tables

## Phase 4 — settings, messages and the amendment that allows the chat

- [x] T010 `backend/app/config.py`: `ai_structure_chat_daily_tokens` (default 100 000, ≥ 0) and
      `ai_structure_chat_store_questions` (default false); `.env.example` and `docs/INSTALL.md` row
- [x] T011 `backend/app/i18n/es.py` + `backend/app/i18n/en.py`: every new message key (chat
      refusals, cap, typed provider errors, sample errors)
- [x] T011b `.specify/memory/constitution.md` VIII gains the one sentence of the 3.2.2 PATCH, with
      its Sync Impact Report — before any chat code lands (VIII is a MUST)

## Phase 5 — the structure API (contracts/api.md)

- [x] T012 `backend/app/sources/structure.py`: flags read/write, notes, `pack_for(source, ...)`
      built from describe + flags + notes + BI-ready flag, audited download
- [x] T013 `backend/app/sources/samples.py`: run one sample through the stored credential
      (`GET` only), shape, `records`/`fields`, `timestamp_units`, pagination, persisted `last_*`
- [x] T014 `backend/app/api/sources.py`: `GET .../structure`, `PUT .../structure/notes`,
      `PUT .../structure/columns`, `GET/POST .../samples`, `PATCH/DELETE .../samples/{id}`,
      `POST .../samples/{id}/run` — permissions, re-auth and audit as the contract says
- [x] T015 `[P]` `backend/tests/test_source_structure.py` (API half): md/json parity with the
      generator, audit entry, notes and flag round trip, sample run stores no value, 422s

## Phase 6 — the chat (FR-004, FR-005, US2)

- [x] T016 `backend/app/ai/prompts/source_structure.md`: the system prompt of FR-005 (data file)
- [x] T017 `backend/app/ai/chat.py`: `refusal(question)`, `context(pack, question)` with the
      60 000-char cap and per-schema index, `validate(answer, pack)`, `ask(...)` with the daily cap,
      history, usage and audit
- [x] T018 `backend/app/api/sources.py`: `GET/POST/DELETE .../chat` with the typed errors of the
      contract (`ai_not_configured`, `ai_<code>`, `ai_chat_cap`)
- [x] T019 `backend/app/worker.py#housekeeping`: purge `source_chat_message` older than 30 days
- [x] T020 `[P]` `backend/tests/test_source_structure_chat.py`: provider payload audit (structure,
      question, 10 turns, no credential/host/value), refusals without a provider call, `unknown`
      objects flagged, cap 429 then tomorrow answers, typed provider error, AI off

## Phase 7 — the tab (FR-001, FR-002, FR-006, FR-007, US1, US2)

- [x] T021 `frontend/src/api/types.ts` + new `frontend/src/api/sources.ts`: the structure, sample
      and chat types and calls
- [x] T022 `frontend/src/pages/admin/SourceStructure.tsx`: structure view per kind, search box,
      personal chip + toggle, notes, sample requests with **Ejecutar**, the two downloads, the
      "Actualizar" button, a per-schema list that pages when a schema has many tables, mobile-first
      (stacked), two panes from `lg`
- [x] T023 `frontend/src/components/StructureChat.tsx`: non-modal panel (bottom sheet on mobile),
      question box, turns, `unknown` chips, the AI-off hint, typed errors with the
      Administración → IA link
- [x] T023b `frontend/src/pages/admin/AI.tsx`: the AI settings page names "Chat de estructura" as
      the feature that uses the provider (FR-006)
- [x] T024 `frontend/src/pages/admin/SourceForm.tsx`: tabs `Conexión | Estructura` without changing
      what the form does; the tab survives a reload (`?tab=estructura`)
- [x] T025 `frontend/src/i18n/es.ts` + `frontend/src/i18n/en.ts`: all the new strings
- [x] T026 `[P]` `frontend/tests/unit/source-structure.test.tsx`: tree renders, search filters,
      personal chip, downloads hit the right URLs, chat off shows the hint, an answer with an
      unknown object shows the chip, and the three interactions of SC-005 are the only ones needed

## Phase 8 — the guide (FR-008)

- [x] T027 `backend/app/guide/{es,en}/*.md` + `index.yaml`: "Estructura de una fuente",
      "Chat de estructura", "Peticiones de muestra", with routes and aliases
- [x] T028 Run the drift tests and fix what they name (`tests/test_guide.py`,
      `frontend/tests/unit/guide-drift.test.ts`)

## Phase 9 — documentation

- [x] T029 `docs/AUTHORING.md` (or the pack chapter that promises the structure) says where the
      download lives and what the two files contain

## Phase 10 — verification

- [x] T030 Backend: `uv run pytest tests/test_source_structure.py
      tests/test_source_structure_chat.py tests/test_migrations.py tests/test_sources_api.py
      tests/test_guide.py -q`
- [x] T031 CLI: `cd cli && uv run pytest tests/ -q`
- [x] T032 Frontend: `npx vitest run tests/unit/source-structure.test.tsx` and `npm run build`

---

## Phase 11 — convergence 2026-11-03: the chat becomes one generator button

Owner decision after reading the feature on production: no chat; one button that produces the pack
with AI, internally and without input.

- [x] T033 Converge the spec: US2 replaced, FR/SC/entities rewritten, constitution PATCH 3.2.3
- [x] T034 `cli/bizview_cli/schemas/structure.schema.json`: the pack document (generator, tables,
      fields, relations, suggested metrics, dropped) — and its byte-identical copy in
      `pack/bizview-starter-pack/bizview-starter/.bizview/schemas/`
- [x] T035 `cli/bizview_cli/structure.py`: `enriched_schema()`, `validate_enriched(doc)`,
      `enriched_json(doc)`, `enriched_markdown(doc)` — `structure.md` rendered from the JSON
- [x] T036 `cli/bizview_cli/describe.py`: `structure_from()` also reads a generated pack (tables →
      fields), so `bizview validate --describe FILE` works with it
- [x] T037 `backend/app/ai/prompts/structure_enrich.md`: the internal prompt (JSON only, names from
      the scan, no invention, metrics as suggestions, Spanish notes)
- [x] T038 `backend/app/sources/structure_scan.py`: the scan — describe, every sample, the OpenAPI
      document and the base listing when the source serves one, scrubbed formats only, chunked
- [x] T039 `backend/app/sources/structure_ai.py`: enrich (one `complete()` per chunk, ≤ 6, token
      ceiling, one repair round), verify (drop unknown names/relations/paths), save with the
      previous pack beside it
- [x] T040 `backend/app/models.py` + `alembic/versions/0050_structure_pack.py`:
      `data_source.structure_pack`/`structure_pack_prev`, drop `source_chat_message`, audit kind
      `source_structure_generated`, chat kinds moved to historical
- [x] T041 `backend/app/api/sources.py`: `POST .../structure/generate`, `GET .../structure` serves the
      generated pack (`?mode=scan` forces the scan), chat routes and `ChatIn` removed
- [x] T042 `backend/app/config.py`, `.env.example`, `docs/INSTALL.md`: `AI_STRUCTURE_TOKENS`
      (default 150 000) replaces the two chat settings
- [x] T043 Remove the chat: `backend/app/ai/chat.py`, `prompts/source_structure.md`, worker purge,
      `frontend/src/components/StructureChat.tsx`, its i18n block, its tests
- [x] T044 `frontend/src/pages/admin/SourceStructure.tsx`: full-width card, the generator button with
      progress and Cancelar, `dropped` list, "Ver cambios" diff, the generated tables view
- [x] T045 `frontend/src/api/sources.ts` + `types.ts`: the pack, the generate call (with abort), the
      diff shapes; `api/admin/AI.tsx` names the generator and shows the internal prompt read-only
- [x] T046 `frontend/src/i18n/{es,en}.ts`: strings for the generator; the chat block removed
- [x] T047 Guide: `generar-estructura-con-ia` (es/en) replaces `chat-de-estructura`; index, aliases,
      counts in `test_guide.py`/`test_guide_api.py`
- [x] T048 `backend/app/i18n/{es,en}.py`: generator messages (AI off, unsupported kind, run failed,
      ceiling reached); chat messages removed
- [x] T049 Gates: `source_chat` and `AI_STRUCTURE_CHAT_` added to `scripts/check_vocabulary.sh` and
      `scripts/gates/06-settings.sh` so the removed surface cannot come back
- [x] T050 `backend/tests/test_source_structure_ai.py`: scan + enrich + verify with the fake provider
      over recorded CoinMarketCap shapes — schema-valid, relations only between existing fields,
      `dropped` names the planted table, markdown matches the template, repair round, failure keeps
      the scan, payload audit, AI off, token ceiling; and the chat routes are gone (404)
- [x] T051 `cli/tests/test_structure_pack.py`: the enriched document validates against the schema,
      `enriched_markdown` renders it, a generated `structure.json` feeds `structure_from`
- [x] T052 `frontend/tests/unit/source-structure.test.tsx`: rewritten for the button — disabled with
      the hint when AI is off, progress, `dropped`, diff, generated table rows
- [x] T053 Docs: `docs/AUTHORING.md`, `docs/VIBE-REPORTING.md`, `pack/.../PROMPT.md` (the pack's two
      files are the generated ones), `CHANGELOG.md`
- [x] T054 Verify: pytest (structure, AI, guide, migrations), `npx vitest run`, `tsc`, `npm run
      build`, the eight gates
