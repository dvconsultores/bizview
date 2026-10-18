---
description: "Task list for feature 014 — Vibe-reporting chat"
---

# Tasks: Vibe-reporting chat

**Roles**: DeepSeek writes code; Claude audits/converges. Security-sensitive (AI data boundary,
super-user apply): Claude reviews line by line. No live AI in tests.

## Phase 1: Foundational
- [X] T001 Migration backend/alembic/versions/0009_assistant.py + models per plan "Data"; migration test
- [X] T002 Provider `chat()` with tool calls in backend/app/ai/{__init__,anthropic_provider,openai_compatible}.py + FakeProvider (test hooks only); tests with mocked transports

## Phase 2: User Story 1 — Validated draft (P1) 🎯
- [X] T003 [US1] backend/app/assistant/tools.py (list_sources, describe_source + sanitize, get_workspace, propose_draft with path/size limits) + tests incl. sanitisation
- [X] T004 [US1] backend/app/assistant/tree.py build_tree + validation (uses 011 documents) + tests
- [X] T005 [US1] backend/app/assistant/service.py loop (rounds, history window, budget, tool messages) + backend/app/api/assistant.py sessions/messages routes + tests with FakeProvider; SC-002 payload audit test

## Phase 3: User Story 2 — Preview and apply (P1)
- [X] T006 [US2] Preview: runner preview_schema mode + worker processing of assistant_preview_request + report engine schema override + preview routes + cleanup; tests (never touches ds_*)
- [X] T007 [US2] Apply: refactor backend/app/workspace/service.py apply into shared apply_tree; POST apply (recent re-auth) + audit; version export zip; tests (chat apply ≡ Git apply)

## Phase 4: User Story 3 — Sessions UI (P2)
- [X] T008 [US3] frontend: api types, es.ts strings, nav item, pages Assistant.tsx + AssistantSession.tsx (transcript, tool chips, composer, draft cards, Vista previa view, Aplicar with step-up, usage) + unit tests
- [X] T009 [US3] e2e frontend/tests/e2e/assistant.spec.ts with the fake provider (test hooks): conversation → draft → preview → apply → dashboard → rollback; CHANGELOG

## Phase 5: Polish
- [X] T010 Backend tests for touched modules + frontend suites; `/speckit-converge`

## Phase 6: Convergence
- [X] T011 Let an applied conversation accept new requests that start a new draft on the current active version (backend `send` + UI composer), and show/link the workspace version it produced per US3/AC3 (contradicts)
- [X] T012 Pass the preview outcome (status, sanitised errors, row counts — never row values) into the assistant context and show it in the conversation so the AI can fix the draft per US2/AC3 (partial)
- [X] T013 Hide the "Asistente" nav item when AI is not configured and, on opening the Asistente, explain how to configure it with all actions disabled per FR-001 (partial)
- [X] T014 Take the workspace lock before building the draft tree in `apply_draft` (or detect an active-version change) so a concurrent apply is never silently dropped and the user is told per Edge: concurrent apply (partial)
- [X] T015 Show the draft as cards grouped Spec de integración / Integración / Spec de reporte / Reporte with readable content per US1/AC2 (partial)
- [X] T016 Add a "Descargar (zip)" action for workspace versions (Espacio de trabajo and applied conversations) using `export.zip` per FR-009 (partial)
- [X] T017 Drop the session's preview schemas when a conversation is archived per Edge: preview cleanup (partial)
