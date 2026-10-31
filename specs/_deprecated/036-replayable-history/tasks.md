# Tasks: Replayable conversation history (036)

**Input**: [spec.md](./spec.md) · [plan.md](./plan.md)
**Tests**: required by the owner's brief (fuzz, session-23 fixture, atomic rounds, repair, both
provider formats).

## Phase 1 — Builder + validator (commit 1)

- [X] T001 [P] `backend/app/assistant/history.py`: `StoredMessage`, `HistoryInvalid`, the module
      docstring with the four rules, `from_db()` / `from_chat()` constructors.
- [X] T002 [US1] `build()`: pair by call id, group results into the user turn right after their
      assistant turn, drop orphans, note orphan `tool_use`, merge same-role, never empty.
- [X] T003 [US1] Window: cut at a user-text boundary; an exchange older than the window becomes
      text inside the assistant turn.
- [X] T004 [US1] `validate_provider_messages(messages, provider)` + `assert_valid()` with the
      Anthropic and OpenAI-compatible rules; violations name the index and the call ids.
- [X] T005 [US1] `service.py`: build through the module for every `provider.chat`, one repair pass
      on `HistoryInvalid`, then `AIError("history_invalid")`; WARNING log with ids only.
- [X] T006 [P] `app/ai/errors.py` + `app/i18n/{es,en}.py`: the `history_invalid` code, its text
      and its action (repair, not retry).
- [X] T007 [P] `backend/tests/test_history_build.py`: session-23 fixture builds valid and the
      transport receives the reordered exchange; window boundary; old exchange as text; unique ids;
      grouped results first; no consecutive same role; no empty message.
- [X] T008 [P] Fuzz: 10 000 random stored histories (windows 1..50) → `validate` accepts 100 % for
      `anthropic` and `openai_compatible`.

## Phase 2 — Atomic rounds (commit 2)

- [X] T009 [US2] `service.py::_heartbeat` (own short transaction, same claim check) replacing the
      `_commit_round` before each tool; the round's rows are written by the single commit at its end.
- [X] T010 [US2] Tool rows carry `call_id`, `assistant_message_id` and `round`; the builder prefers
      the FK when present.
- [X] T011 [P] `backend/tests/test_history_atomic.py`: a tool that fails mid-round leaves zero
      `tool` rows and one assistant reason; a stopped round the same; the next turn sends.

## Phase 3 — Migration + repair (commit 3)

- [X] T012 [US3] `app/assistant/repair.py::repair_rows(db, session_id)` — pair by call id, set
      `assistant_message_id`/`call_id`, flag the rest `orphan`, return what changed.
- [X] T013 [US3] Alembic `0029_assistant_history`: the four columns + backfill (three set-based
      `UPDATE`s), logging the orphan count per session.
- [X] T014 [US3] `POST /api/assistant/sessions/{id}/repair` (owner or super user), audited as
      `assistant_conversation_repaired`, returns the report; `GET` session keeps working.
- [X] T015 [US3] Frontend: **Reparar conversación** in the chat header menu and in the
      `history_invalid` bubble, with the result notice; `es.ts`/`en.ts`.
- [X] T016 [P] `backend/tests/test_history_repair.py` (migration helper + endpoint) and
      `frontend/tests/unit/assistant-repair.test.tsx`.

## Phase 4 — Docs + release (commit 4)

- [X] T017 [P] Guide topic «Reparar conversación» (`backend/app/assistant/guide/{es,en}/`) and the
      short section in `docs/guides/asistente/`; keep the guide-drift test green.
- [X] T018 [P] `CHANGELOG.md` under Unreleased with the incident and the four fixes.
- [X] T019 Gates: ruff (backend + cli), targeted pytest suites, `npx tsc --noEmit`,
      `npx vitest run`, `npm run build`.
- [X] T020 Commit in the four slices, push, `./deploy.sh`, run the migration, verify
      `/api/health` shows the new commit and that session 23 sends after a repair.
