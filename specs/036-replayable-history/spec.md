# Feature Specification: Replayable conversation history — no orphan `tool_result` blocks

**Feature Branch**: `036-replayable-history`

**Created**: 2026-10-26

**Status**: Draft

**Input**: Owner, 2026-10-26 09:25, from production (`bi.getbizview.com`, project `coinmarketcap`,
session 23): every turn of the conversation answers

```
provider_error · Modelo: deepseek-flash (anthropic)
BadRequestError: Error code: 400 - {'error': {'message': 'unexpected `messages.4.content.0:
tool_use_id` found in `tool_result` blocks: call_00_g9JNBifdtD02Zjv7EV6i7946. Each `tool_result`
block must have a corresponding `tool_use` block in the previous message.'}}
```

including «continua». The provider is healthy (Probar passes): the *replayed history* is
structurally invalid, so the conversation is poisoned for good.

**Builds on**: 003/017 (AI provider layer, assistant loop), 014/028 (conversation storage, Auto
mode), 035 (`provider_error` bubble, `/api/health.ai`, request ids), 022 (bilingual UI).

## Evidence and root cause (verified against the production rows)

Session 23, in id order:

```
3661 assistant  calls=1                              ← tool_use call_00_g9JN… (apply_draft)
3662 assistant  «Contrato del run autorizado: …»     ← written by the tool, mid-exchange
3663 tool       call_00_g9JN… «Aplicó la versión 12.» ← the tool_result
…  3700 assistant «El proveedor de IA devolvió un error.» (every turn from here)
```

`_load_history_with_summaries` seeds a synthetic «sin resultado» for `call_00_g9JN…` as soon as it
sees the assistant message (line 3661) because the *next* row is not a `tool` row, and then leaves
the real `tool` row (3663) standing alone after an assistant *text* message. The Anthropic
converter turns every `tool` row into a `tool_result` block in the following user turn, so the
payload contains `tool_result(call_00_g9JN…)` right after an assistant message that does not
declare it → `400`.

Four defects add up to that, and all of them are in this feature's scope:

1. **Pairing by adjacency.** Tool results are matched to the *immediately following* rows instead of
   to the assistant message that requested them, so any message written between the `tool_use` and
   its result (a tool's own note, the run-contract line, a preview outcome) breaks the pairing.
2. **No structural validation.** Nothing checks the payload before the HTTP call, so a bad build is
   sent and the provider's 400 is reported as `provider_error`, with no way out.
3. **Window and summary cuts inside an exchange.** The last-N window and the "first user message"
   trim can start in the middle of an assistant→tool exchange, or keep a result whose `tool_use`
   was cut; summarised results stay `tool_result` blocks after their ids were dropped.
4. **Round persistence is not atomic.** `_commit_round` runs before every tool, so a round can be
   committed half-way (assistant `tool_use` written, results lost or vice versa) when the round
   then fails, is stopped or hits a budget.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A conversation always produces a valid payload (Priority: P1) 🎯

Whatever the stored rows look like, the provider receives a structurally valid conversation.

**Independent Test**: build from random stored histories (tool exchanges, interleaved assistant
notes, failed rounds, stops, windows 1..50) and assert the validator accepts every build.

**Acceptance Scenarios**:

1. **Given** any stored history, **When** the messages are built for a provider, **Then** every
   `tool_result` answers a `tool_use` of the assistant turn immediately before it, ids are unique,
   no two consecutive messages share a role and no message is empty.
2. **Given** an assistant message with a `tool_use` and no matching result, **Then** the
   `tool_use` is replaced by a short text note («[herramienta apply_draft sin resultado]») in the
   same assistant turn, never dropped silently.
3. **Given** a `tool` row whose `tool_use` is not in the window, **Then** it is emitted as text
   inside the assistant turn, never as a `tool_result` block.
4. **Given** the session-23 shape (assistant `tool_use`, assistant note, then the tool row),
   **Then** the build reorders the result to immediately follow its own assistant turn and the
   payload is accepted.

### User Story 2 - A failing round leaves nothing half-written (Priority: P1)

**Independent Test**: make the provider fail (or stop the run) in the middle of a round that has
already executed a tool; assert no `tool` row exists afterwards and the next turn builds cleanly.

**Acceptance Scenarios**:

1. **Given** a round with tool calls, **When** the round completes, **Then** its assistant message
   and its tool rows become visible in **one** transaction.
2. **Given** a round that fails, is stopped or hits a budget after a tool ran, **Then** only one
   assistant message (the reason) is stored, with no `tool` rows from that round.
3. **Given** the claim must stay fresh during a long tool, **Then** the heartbeat is written in its
   own short transaction and does not commit the turn.

### User Story 3 - An already-poisoned conversation can be repaired (Priority: P2)

**Independent Test**: seed a session with orphan rows, run the repair, assert the next build is
valid and the report says what was dropped.

**Acceptance Scenarios**:

1. **Given** the installation upgrades, **Then** a data migration pairs every tool row with its
   assistant message, marks unpaired ones `orphan` and logs the count per session.
2. **Given** an `history_invalid` bubble, **Then** it explains the problem in one line and offers
   **Reparar conversación**; the conversation's owner or a super user can run it from the chat
   header too.
3. **Given** a repair, **Then** it drops (or pairs) what the provider cannot accept, reports the
   count and is audited; the conversation sends again immediately.

## Requirements

- **FR-001** One module (`app/assistant/history.py`) builds provider messages for both providers;
  nothing else converts stored rows into provider payloads.
- **FR-002** Pairing uses the stored call id (and `assistant_message_id` once set), never adjacency.
- **FR-003** Results of one assistant turn are grouped in the single user turn right after it.
- **FR-004** Orphan results are dropped and orphan `tool_use` blocks become a text note.
- **FR-005** The window cuts only at a user-text boundary; an exchange older than the window is
  text, never `tool_result` blocks.
- **FR-006** Consecutive same-role messages are merged; empty messages are never emitted.
- **FR-007** `validate_provider_messages(messages, provider)` checks the provider rules; the loop
  repairs once and, if still invalid, fails with code `history_invalid`.
- **FR-008** Drops and repairs log at WARNING with session id, message ids and call ids only.
- **FR-009** A failed, stopped or budget-cut round persists **no `tool` row**: the results are
  written once, at the end of the round, so nothing half-written is ever replayed. The assistant
  turn that asked for the tools is committed before they run — it has to be, or **Detener** (a second
  connection) could not release the claim, and holding the session row locked across a tool is what
  deadlocked it; the builder notes its unanswered call, so the leftover turn is still replayable.
- **FR-010** Tool rows store `call_id`, `assistant_message_id` and `round`.
- **FR-011** A migration pairs and flags existing rows; `POST /api/assistant/sessions/{id}/repair`
  does the same on demand for its owner or a super user, and is audited.
- **FR-012** `history_invalid` is a provider error code of 035 with its own es/en text and a repair
  action; `/api/health.ai` is unchanged.
- **FR-013** The chat header offers **Reparar conversación**; the guide explains it.

## Success Criteria

- **SC-001** 100 % of generated histories (10 000 cases) pass the validator for both providers.
- **SC-002** The session-23 shape builds a valid payload and the transport receives it.
- **SC-003** A failing or stopped round leaves zero `tool` rows and one assistant note; the next
  turn sends, and the unanswered call reaches the provider as text, never as a `tool_result`.
- **SC-004** No `provider_error` on replay caused by structure: the failure mode is impossible by
  construction and reported as `history_invalid` if it ever recurs.

## Assumptions

- Tool rows written by `preview.record_outcome` (no call id) are transcript-only: they are marked
  `orphan` and never replayed.
- The provider payload shape is unchanged for healthy conversations (same blocks, same summaries),
  so prompt caching keeps working.
