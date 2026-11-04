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
