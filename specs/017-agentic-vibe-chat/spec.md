# Feature Specification: Agentic vibe-reporting chat

**Feature Branch**: `017-agentic-vibe-chat`

**Created**: 2026-10-03

**Status**: Implemented (closed 2026-10-08, full suites green)

**Input**: Owner, 2026-10-03: "the chat view gets exhausted; it must work as a chat agent capable of
creating the workspace, reading the origin, creating the BI table, the ETL integration, scheduling the
refresh and the report using ReportLab." Observed in 014: on a simple request (one source, one table),
the assistant spent its whole token budget *probing the artifact schema* by proposing minimal drafts
and reading one validation level per round ("Sondeo nivel 2…"), and ended with "Se agotó el
presupuesto de esta conversación" and 7 open problems. The provider in use is DeepSeek through the
OpenAI-compatible provider.

**Builds on**: 014-vibe-chat (sessions, tools, draft, preview, apply). **Supersedes in 014**: the plan
rule "No tool can run SQL on a source, preview, apply or change controls" is replaced by FR-006 and
FR-010 below. Apply stays a human action with step-up.

## Root causes this feature must remove

1. The model is never given the artifact contract (JSON Schemas of `integration.yaml`, `report.yaml`,
   spec metadata, manifest) nor a complete valid example, so it guesses the shape.
2. Validation returns problems one level at a time and without the expected shape, so each fix costs a
   full round.
3. Every change resends whole files; every round resends full tool results (structure, workspace), so
   the 200k budget is spent on repetition.
4. When the budget ends, the conversation is a dead end.
5. The agent cannot check its own SQL, cannot run a preview, and cannot start from an empty workspace,
   so it cannot finish the job the owner described.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The agent knows the contract and writes a valid draft (Priority: P1) 🎯

The super user asks for a dashboard over a table of a configured source. The agent reads the
authoring contract once, inspects the source, asks only the business decisions it cannot infer, and
produces a complete draft (integration spec + integration files + report spec + report definition)
that passes validation without "probing".

**Why this priority**: this is exactly where 014 fails.

**Independent Test**: with the fake provider replaying a recorded conversation and with the opt-in
live DeepSeek eval (see SC-001), request "ventas diarias por estado de factura" over a test table; the
draft must be valid within the limits of SC-001.

**Acceptance Scenarios**:

1. **Given** a new conversation, **When** the agent starts working, **Then** it has access to an
   *authoring pack*: the JSON Schemas the validator uses (from `cli/`), the workspace rules, the preset
   templates, and at least one complete golden example that passes validation; the agent never needs
   to discover required properties by submitting test drafts.
2. **Given** a draft with problems, **When** it is validated, **Then** **all** problems are returned
   at once, each with file, JSON path, message, the expected type/shape at that path (schema
   fragment), and a suggested fix where the validator can infer one.
3. **Given** an existing valid draft, **When** the agent fixes a problem, **Then** it edits only the
   affected file(s) (write / replace text / delete) instead of resending the whole draft, and
   validation re-runs automatically.
4. **Given** the agent proposes a draft whose sole purpose is to discover the schema (e.g. 1–2 files,
   no spec), **When** detected, **Then** the tool answers with the relevant schema fragment and does
   not count it as a draft attempt.

---

### User Story 2 - The agent reads the origin safely (Priority: P1)

The agent lists sources, reads table/column structure, gets aggregate profiles, and checks that its
extraction SQL compiles and returns the expected columns — without ever receiving row values.

**Why this priority**: an integration whose SQL was never checked against the origin fails in preview
and costs more rounds.

**Independent Test**: seeded distinctive values in the test source never appear in any payload sent to
the provider (extends 014 SC-002), while the agent obtains column names, types and counts.

**Acceptance Scenarios**:

1. **Given** a source, **When** the agent calls `describe_source`, **Then** it gets tables, columns,
   types, keys, and a flag on columns likely to hold personal data (email, names, phone, document ids,
   chat ids, payment payloads) by name/type heuristics.
2. **Given** a table, **When** the agent calls `profile_source`, **Then** it gets only aggregates
   computed by product code: row count, null ratio and distinct count per column, and min/max for date
   and timestamp columns. No categorical or numeric values are returned.
3. **Given** an extraction query, **When** the agent calls `check_query`, **Then** the query is
   enforced read-only with sqlglot, run in a read-only session as `LIMIT 0`/describe-only, and the
   result is the list of output columns and types or the database error text with literals redacted.
4. **Given** flagged personal columns, **When** the agent drafts the integration, **Then** it excludes
   them unless the super user explicitly asks for one, and the integration spec records the decision.

---

### User Story 3 - The agent can start from nothing (Priority: P1)

On an installation with sources configured but no workspace version yet, the agent creates the
workspace (manifest and folders from the preset in `cli/bizview_cli/workspace_template/`) as part of
its first draft.

**Independent Test**: on an empty installation, a conversation ends with an applied version 1
containing the manifest, one integration and one report.

**Acceptance Scenarios**:

1. **Given** no active workspace version, **When** a draft is built, **Then** the tree starts from the
   workspace template instead of failing with "Aplica una vez el espacio de trabajo desde Git…".
2. **Given** an active version created from Git whose spec documents were never stored (pre-011),
   **When** a draft is built, **Then** the agent is told which documents are missing and may
   regenerate them inside the draft; the super user sees them as part of the draft.

---

### User Story 4 - The agent finishes the job: table, ETL, schedule, report, PDF (Priority: P1)

The agent produces everything needed for the dashboard to exist after apply: the dataset contract
(columns, keys, types) from which the engine creates the BI table `ds_<integration>`, the extraction
(validated SQL or request definition), incremental window and idempotency keys, the refresh schedule,
checks, the report (metrics, dimensions, views, filters) and the PDF export layout rendered by
ReportLab in the backend. It runs the preview itself and fixes what fails. Only applying needs the
human.

**Independent Test**: from a single request, the conversation reaches state "Listo para aplicar" with
a successful preview (row counts shown, report rendered, PDF preview downloadable); after "Aplicar"
the worker creates `ds_<integration>`, runs on the declared schedule, and the dashboard and its PDF
export work for a normal user.

**Acceptance Scenarios**:

1. **Given** a valid draft, **When** the agent calls `run_preview`, **Then** the same preview as 014
   runs (bounded window, temporary schema, never `ds_*`), and the agent receives status, row counts
   per table, check results and sanitized errors; the conversation shows "Ejecutó una vista previa".
2. **Given** a successful preview, **When** the super user opens it, **Then** the draft report renders
   marked "Vista previa" and a "PDF de vista previa" generated by the backend with ReportLab can be
   downloaded.
3. **Given** the draft omits the schedule, keys, or PDF layout, **When** validated, **Then** it is not
   "Listo para aplicar"; the agent asks the super user only for decisions it cannot infer (e.g. refresh
   frequency) and proposes a default for the rest.
4. **Given** "Listo para aplicar", **When** the super user presses "Aplicar", **Then** 014 FR-006
   applies unchanged (step-up, re-validation, new version, audit, rollback).

---

### User Story 5 - Long work does not die on the budget (Priority: P2)

The agent works in bounded steps, reports progress, and never loses work when a limit is reached.

**Independent Test**: force the budget to a small value; the conversation stops with the draft and a
progress summary intact, the super user extends the budget, writes "continúa", and the agent resumes
from where it stopped without repeating discovery.

**Acceptance Scenarios**:

1. **Given** a long task, **When** the per-message round limit is reached, **Then** the agent posts a
   progress message (what is done, what is next) and continues on "continúa" without redoing completed
   steps.
2. **Given** usage reaches 80% of the budget, **When** the next round starts, **Then** the agent is
   told and prioritises reaching a valid draft; the UI shows the warning.
3. **Given** the budget is exhausted, **When** the super user presses "Ampliar presupuesto", **Then**
   after step-up the budget grows by a configured step, the action is audited, and the conversation
   can continue.
4. **Given** any stop (budget, round limit, provider error), **Then** the latest draft, its validation
   and the working notes are stored and shown.

---

### User Story 6 - Works with DeepSeek through the OpenAI-compatible provider (Priority: P2)

**Acceptance Scenarios**:

1. **Given** DeepSeek configured as the OpenAI-compatible provider, **When** the agent loop runs,
   **Then** tool calls, tool results, and multi-round history are exchanged in the shape that provider
   accepts (including any provider-specific reasoning fields, which are never resent or stored in the
   transcript unless the provider requires it), verified by recorded-transport tests.
2. **Given** a provider error (rate limit, invalid tool arguments, context too long), **When** it
   happens, **Then** the loop retries or repairs once (e.g. asks the model to re-emit invalid JSON
   arguments), otherwise stops with the draft preserved and a clear message.

### Edge Cases

- The agent proposes a path outside the allowed draft paths, or a file over the limits: rejected with
  the allowed patterns in the message (no silent drop).
- `check_query` or `profile_source` on a slow origin: per-call timeout; result says "tiempo agotado"
  and the agent narrows the query.
- The source structure changes between draft and apply: apply re-validates (014), and `check_query`
  is re-run on the draft's queries at apply time.
- Two drafts would create the same integration id: rejected; the agent reuses the existing integration
  (014 US1/AC4).
- Personal-data columns requested by the super user: allowed only with an explicit confirmation step in
  the conversation, recorded in the integration spec.
- Internet security profile: `run_preview`, `check_query` and `profile_source` follow the same TLS
  rules as the worker.

## Requirements *(mandatory)*

### Functional Requirements

#### Authoring contract
- **FR-001**: The system prompt (a stable prefix, so provider-side prompt caching can apply) MUST
  include the workspace rules and a compact contract summary; a `get_authoring_guide(topic?)` tool MUST
  return the full JSON Schemas used by the validator, field descriptions, allowed enums (view types,
  aggregations, schedule format) and the golden example(s).
- **FR-002**: The schemas served to the agent MUST be the same objects the validator uses (single
  source in `cli/`), and CI MUST fail if the golden example stops validating.

#### Validation and editing
- **FR-003**: Draft validation MUST collect all problems in one pass (all schema errors plus semantic
  checks) and return per problem: file, JSON path, message, expected schema fragment, and suggested fix
  when inferable. The banner and draft cards in the UI show the same list.
- **FR-004**: An `edit_draft(ops)` tool MUST support write file, replace text in file, and delete file
  on the current draft, with the 014 path and size limits; `propose_draft` remains for a full draft.
- **FR-005**: A draft MUST reach "Listo para aplicar" only when: validation passes, every query passed
  `check_query`, and the latest preview succeeded.

#### Origin access (metadata only)
- **FR-006**: New tools `profile_source(name, table)` and `check_query(source, sql | request)` MUST
  run only through the read-only connectors, sqlglot read-only enforcement for SQL, per-call timeouts,
  and the sanitising layer of 014; they MUST NOT return row values, credentials or connection details.
- **FR-007**: `describe_source` MUST flag likely personal-data columns; drafts MUST exclude them by
  default (FR-007 is the enforcement of constitution VIII for this feature).

#### Workspace bootstrap
- **FR-008**: `build_tree` MUST start from the workspace template when there is no active version, and
  MUST report missing stored spec documents as fixable draft problems instead of a hard error.

#### Complete deliverable
- **FR-009**: A complete draft MUST contain: integration spec (spec, plan, tasks), dataset contract
  (columns, types, keys), extraction, incremental window, schedule, checks; report spec (spec, plan,
  tasks), report definition (metrics, dimensions, views, filters) and PDF export layout for ReportLab.
- **FR-010**: The agent MAY call `run_preview` (same constraints as 014 FR-005, at most one preview
  running per conversation, configurable maximum previews per conversation); `apply` and control
  changes remain super-user actions only.
- **FR-011**: The preview MUST offer a PDF generated by `backend/app/reports/` with ReportLab from the
  preview data.

#### Loop, history and budget
- **FR-012**: The loop MUST keep a stored *working state* per conversation (goal, decisions taken,
  sources and tables inspected with a short structure note, current step) and send it each round
  instead of old tool results; tool results older than the last round are sent as their summary only.
- **FR-013**: The draft is sent as a file index plus the files touched in the last rounds, not in
  full every round.
- **FR-014**: The per-message round limit MUST be configurable (default 20); on reaching it the agent
  posts a progress message; "continúa" resumes from the working state.
- **FR-015**: Budget usage MUST use the provider's reported usage; warning at 80%; "Ampliar
  presupuesto" with step-up and audit; nothing stored is lost when the budget ends.
- **FR-016**: Every tool call MUST appear as a chip in the conversation (014 FR-007), including
  `get_authoring_guide`, `profile_source`, `check_query`, `edit_draft` and `run_preview`.

#### Provider
- **FR-017**: The OpenAI-compatible provider MUST support the full tool loop with DeepSeek, verified
  by recorded transports; invalid tool-argument JSON triggers one repair round.

### Key Entities

- **Authoring pack**: validator JSON Schemas, workspace rules, preset templates, golden example(s);
  read-only, served from `cli/`.
- **Validation problem**: file, JSON path, message, expected schema fragment, suggested fix.
- **Working state** (per conversation): goal, decisions, inspected sources/tables with structure
  notes, current step, progress summary.
- **Query check** (per draft query): query fingerprint, result (columns+types or redacted error),
  checked at.
- **Draft readiness**: validation passed + all queries checked + latest preview succeeded →
  "Listo para aplicar".
- **Budget extension**: conversation, step added, actor, time (audited).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the opt-in live eval (`AI_LIVE_TESTS=1`, DeepSeek) on the reference test source, the
  request "dashboard de facturas por día y estado, actualizado cada hora, con PDF" reaches "Listo para
  aplicar" with ≤ 3 validation cycles, 0 schema-probing drafts, and ≤ 40% of the default token budget,
  in at least 4 of 5 runs.
- **SC-002**: 0 row values, credentials or connection strings in any payload sent to the provider,
  including the new tools (014 SC-002 extended with `profile_source` and `check_query`).
- **SC-003**: After apply, `ds_<integration>` exists with the contract's columns and keys, the worker
  runs on the declared schedule, and the report and its PDF export work for a normal user, in 100% of
  e2e runs.
- **SC-004**: From an empty installation (no workspace version), a conversation produces an applied
  version 1 in the e2e suite.
- **SC-005**: A conversation stopped by budget or round limit resumes after "Ampliar presupuesto" /
  "continúa" without re-calling `describe_source` for tables already in the working state.

## Assumptions

- The validator's JSON Schemas already live in `cli/` and can be served as data (constitution IV).
- Min/max of date columns, counts and null ratios are aggregates composed by product code and are
  allowed by constitution VIII; no constitution amendment is needed. If review disagrees, `profile_source`
  drops min/max and a PATCH amendment clarifies VIII.
- DeepSeek is configured through the existing AI administration (OpenAI-compatible endpoint); no new
  stack component.
- The repository examples and golden files use generic names only (constitution VII): no customer or
  source names from real installations.

## Amendment 2026-10-05 (owner): autonomous runs

Owner, 2026-10-05: "it must work as autonomous agent, must work alone without auth". Supersedes
US5 AC1 and AC3 and the step-up part of FR-015:

- **FR-018**: A message starts an autonomous run that continues server-side until the agent ends
  its turn (it asks the super user a business question or reports the result), the draft reaches
  "Listo para aplicar", or a hard limit is hit. Neither "continúa" nor keeping the page open is
  needed; the UI shows progress and can be closed.
- **FR-019**: The budget extends automatically by `AI_CHAT_BUDGET_STEP` up to `AI_CHAT_BUDGET_MAX`
  without any human action (each extension audited as automatic). Only `AI_CHAT_BUDGET_MAX` stops
  a run. "Ampliar presupuesto" no longer requires re-authentication.
- **FR-020**: The super user can stop a running agent at any time ("Detener"); work saved up to
  the last completed round is kept.
- Apply remains a human action with step-up (FR-005, 014 FR-006) — unchanged.
- Clarification 2026-10-07 (from FR-019): because the budget extends itself up to
  `AI_CHAT_BUDGET_MAX`, the manual "Ampliar presupuesto" button is removed from the UI. A run that
  reaches the maximum stops with its progress summary and says to continue in a new conversation or
  raise `AI_CHAT_BUDGET_MAX`; SC-005's budget path is satisfied by continuing after the maximum is
  raised.
