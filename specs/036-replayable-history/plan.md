# Implementation Plan: Replayable conversation history (036)

**Feature**: `036-replayable-history` · [spec.md](./spec.md) · [tasks.md](./tasks.md)

## Technical context

| | |
|---|---|
| Backend | FastAPI + SQLAlchemy + Alembic (constitution V, unchanged) |
| Storage | `assistant_message` gains `call_id`, `assistant_message_id`, `round`, `orphan` |
| Providers | `AnthropicProvider`, `OpenAICompatible` — both consume the neutral `ChatMessage` list |
| Frontend | React 19 + Tailwind; one bubble action and one header menu item (feature 010 look) |
| Tests | pytest with the scripted `FakeProvider` (transport spy, no live AI) + vitest |

## Constitution check

- **V (fixed stack)** — no new component, library or service; Alembic owns the schema change.
- **VIII (AI optional and private)** — unchanged: this is loop correctness. No new data leaves the
  installation; the log lines carry ids and codes, never content. Plan note: *no amendment*.
- **IX (spec-driven)** — the fix is product code in the assistant loop, not customer logic.
- **I/IV** — mobile-first bubble/menu, and the module lives in `backend/app/assistant/`.

Verdict: **PASS**, no amendment.

## Decisions

1. **One builder** (`backend/app/assistant/history.py`) with a row shape (`StoredMessage`) fed from
   two constructors — `from_db(db, session_id, window)` and `from_chat(history)` — so the in-turn
   history and the replayed history are the same code path.
2. **Pair by call id, group, then emit.** Walk the stored rows in order: an assistant row with calls
   is emitted, immediately followed by the single user turn carrying *all* results owned by it
   (wherever they sit in the window). Rows displaced by that regrouping keep their own order after
   the exchange. Unpaired results are dropped; unpaired calls become a text note.
3. **Window by user-text boundary**: take the newest `HISTORY_LIMIT` rows, then move the cut
   forward to the oldest user message with text (or drop leading non-user rows when there is none).
   A result whose owner is outside the window becomes a text note in the assistant turn.
4. **Validation before the call**, provider-aware (`anthropic` requires alternation, results first
   in the user turn, unique ids; `openai` requires `tool` rows to follow the assistant whose
   `tool_calls` name them). One repair pass (drop the offending blocks), then `history_invalid`.
5. **Atomic rounds, measured against the lock**: the result rows are buffered and written once,
   just before the round's single commit — so a round that dies leaves no `tool` row. The assistant
   turn with its `tool_use` blocks is still committed before the tools run: **Detener** arrives on a
   second connection and must be able to take the session row, and the round's transaction holds it.
   Two alternatives were implemented and rejected for that reason (a mid-round `_commit_round`
   removal, then a separate-connection heartbeat): both deadlock the stop request for the length of
   a tool. The builder is what makes the leftover assistant turn replayable — its unanswered call
   becomes a text note.
6. **Repair is data, not code**: `app/assistant/repair.py::repair_rows(db, session_id)` is the one
   implementation used by the migration and by `POST /api/assistant/sessions/{id}/repair`.
7. **Who may repair**: the conversation's owner (it is their transcript) or a super user. Audited
   as `assistant_conversation_repaired`.

## Source layout

```
backend/app/assistant/history.py      NEW  builder + validator (+ StoredMessage, HistoryInvalid)
backend/app/assistant/repair.py       NEW  pairing/flagging used by migration and API
backend/app/assistant/service.py      loop: build+validate, heartbeat instead of mid-round commit
backend/app/ai/errors.py              + history_invalid (code, text, no automatic retry)
backend/app/models.py                 assistant_message: call_id, assistant_message_id, round, orphan
backend/alembic/versions/0029_*.py    NEW  columns + backfill (pair, or flag `orphan`)
backend/app/api/assistant.py          POST /sessions/{id}/repair
backend/app/i18n/{es,en}.py           history_invalid text, repair result, audit label
backend/tests/test_history_build.py   NEW  builder, validator, fuzz, session-23 fixture
backend/tests/test_history_atomic.py  NEW  round atomicity (0 tool rows on failure)
backend/tests/test_history_repair.py  NEW  migration helper + endpoint
frontend/src/components/assistant/…   ProviderError action + header menu item + strings + tests
```

## Delivery (four commits)

1. **Builder + validator + tests** — the payload can no longer be structurally invalid.
2. **Atomic rounds** — a failing round cannot leave half an exchange behind.
3. **Migration + repair action + UI** — existing conversations are healed, on demand or by upgrade.
4. **Docs + CHANGELOG** — the guide section and the release note.

## Risks

- *Prompt caching*: regrouping keeps the same blocks for healthy conversations (assistant + single
  user turn with the results), so the cached prefix is unchanged.
- *Long rounds*: the heartbeat is what keeps the claim fresh now, with the same 900 s stale window;
  a tool that outlives it re-claims as today.
- *Migration on a large table*: the backfill is three set-based `UPDATE`s with an index on
  `(session_id, id)`; no per-row Python.
