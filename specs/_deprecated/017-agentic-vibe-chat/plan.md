# Implementation Plan: Agentic vibe-reporting chat

**Branch**: `017-agentic-vibe-chat` | **Date**: 2026-10-03 | **Spec**: [spec.md](./spec.md)

## Summary

Turn the 014 assistant into an agent that can finish the job in a bounded budget: an authoring pack
served from `cli/` (the validator's own schemas + a golden workspace), exhaustive validation with
the expected shape and a suggested fix per problem, incremental `edit_draft`, metadata-only origin
tools (`profile_source`, `check_query`), bootstrap from the workspace template, an agent-run preview
with a ReportLab PDF, a "Listo para aplicar" readiness gate, a stored working state that replaces old
tool results in the history, budget extension with step-up, and a DeepSeek-safe OpenAI-compatible
tool loop. Apply stays a human action (014 FR-006).

## Technical Context

Python 3.12 / FastAPI / SQLAlchemy / Alembic (migration `0011_agentic_assistant`), jsonschema +
sqlglot in `cli/bizview_cli`, ReportLab in `backend/app/reports/pdf.py`, psycopg read-only sessions
(`engine.extract._pg_connect`: `default_transaction_read_only=on`, `statement_timeout`). React 19 /
Tailwind frontend. Tests never call a live AI (fake provider + recorded transports);
`AI_LIVE_TESTS=1` enables the SC-001 eval only. Product DB tests run on `DATABASE_URL_BI`
(`app_test_*` schemas).

## Constitution Check

- **IV (separated folders)**: schemas, golden example and authoring guide live in `cli/`; the
  backend imports them (single source, FR-002).
- **V (fixed stack)**: no new component; ReportLab, sqlglot, jsonschema, httpx already present.
- **VII (one product)**: golden files use generic names (`facturas`, `origen_ventas`), no customer
  data.
- **VIII (AI optional and private)**: new tools return structure, counts, null ratios, distinct
  counts, date min/max, column names/types and redacted error texts only. Every tool result passes
  the 014 `sanitize()` layer plus a new value-free contract; SC-002 payload audit extended with
  seeded distinctive values in text, numeric and date columns (dates appear only as min/max).
  Personal-data columns are flagged and excluded by default (FR-007).
- **IX (spec-driven)**: drafts are full Spec Kit specs + artifacts; "no spec, no run" unchanged;
  readiness adds checked queries and a successful preview before "Aplicar".
- **Security**: SQL from the agent runs only through sqlglot read-only enforcement
  (`sqlsafety.check_query`) + read-only session + `LIMIT 0` + timeout; requests only GET with
  `limit=1` and only key/type shapes are returned; budget extension and apply need recent re-auth
  and are audited.
→ PASS (no amendment; see spec Assumptions for min/max).

## Design

### 1. Authoring pack (`cli/bizview_cli/authoring.py`, `cli/bizview_cli/golden/`)
- `golden/` is a complete workspace (PostgreSQL variant): `bizview.yaml`,
  `specs/integrations/001-facturas/{spec,plan,tasks}.md`, `integrations/facturas/integration.yaml`
  (+ `queries/facturas.sql` with `:window_start/:window_end`, `primary_key`, `date_column`,
  `incremental.window_days`, `schedule: "0 * * * *"`, `row_count` + `not_null` checks),
  `specs/reports/001-facturas-dia/…`, `reports/facturas-dia/report.yaml` (kpis, trend, ranking,
  table, filters, `pdf: {enabled, orientation, views}`), plus `golden-supabase/` with only the
  request variant (`integrations/facturas-api/requests/facturas.yaml`).
- `authoring.summary() -> str`: compact contract text **generated from the schemas** (required keys,
  enums for column types, view types, metric formats, incremental modes, check types, schedule
  pattern, path patterns) + workspace rules; deterministic so it is a stable prompt prefix.
- `authoring.guide(topic) -> dict`: topics `index`, `workspace`, `integration`, `request`, `report`,
  `spec` (spec/plan/tasks rules + preset templates), `example` (golden files), `example-supabase`,
  `fragment:<schema>#<json-pointer>`. Schemas are `validate.SCHEMAS[name].schema` (same objects).
- CLI test: golden validates with `known_sources={"origen_ventas"}`; summary mentions every
  required key of every schema (CI fails on drift, FR-002).

### 2. Exhaustive validation (`cli/bizview_cli/validate.py`)
- `Issue` gains optional `file`, `path` (JSON pointer), `expected` (compact schema fragment, ≤ 1 KB),
  `fix` (suggested fix text). Old fields unchanged (CLI output and lock unchanged).
- Remove the 20-error cap (cap at 200 per file). For `oneOf` errors pick the branch matching the
  discriminator (`type` const / required key such as `query` vs `request`, `mode` vs
  `window_days`, `sql` vs `formula`) and report that branch's errors; otherwise `best_match`.
- Fix hints by validator keyword: `required` → "añade `<key>`" with the fragment;
  `additionalProperties` → "quita `<key>`; permitidas: …"; `enum`/`const` → allowed values;
  `pattern` → pattern + example; `type` → expected type; `minItems/minProperties` → minimum.
- Collect more per pass: when an artifact has schema errors but `id` and `spec` are usable, still run
  `_check_spec` (spec/plan/tasks problems arrive in the same pass); semantic checks still need a
  schema-valid artifact (they index required keys) — documented, and the schema pass now reports
  all schema errors at once, so at most two cycles remain (schema → semantic).
- `file` is filled for every issue (`integrations/<id>/integration.yaml`, the query file, the spec
  folder file, `bizview.yaml`).

### 3. Draft tools (`backend/app/assistant/tools.py`, `tree.py`)
- `get_authoring_guide(topic?)` → `authoring.guide`.
- `propose_draft(files, summary)` unchanged contract; **probe detection**: no `spec.md` in the
  files and ≤ 2 files and no current draft → not stored, not counted; answers with the schema
  fragments for the given paths + "usa get_authoring_guide('example')"; `stats.probes += 1`.
- `edit_draft(ops: [{op: write|replace|delete, path, content?, old?, new?}], summary?)` on the
  current draft; `replace` requires exactly one occurrence of `old`; 014 path/size limits; rejected
  paths list the allowed patterns; validation re-runs; result = validation + readiness.
- `read_draft(paths)` → current content of draft files (the history keeps only an index).
- Validation result per problem: `{file, path, code, message, expected, fix}`; same list stored on
  the session for the UI banner/cards.
- **Readiness** (`assistant/readiness.py`, FR-005/FR-009): problems "pendientes" (not validator
  errors) when a draft integration dataset lacks `primary_key`, lacks `incremental` (explicit
  `mode: full` or `window_days`), has no `checks`; a draft report lacks `pdf.enabled: true`; a draft
  SQL/request file has no passing `check_query` for its current sha256; the latest preview is not
  `succeeded` for the current draft fingerprint; a flagged personal column is used without
  confirmation (see 5). `ready = validation.valid and not pending`. "Listo para aplicar" = ready.

### 4. Bootstrap (`tree.py`, FR-008)
- No active version → manifest from `workspace_template/files/bizview.yaml` (`{name}` →
  `INSTALLATION_NAME`/`bizview`) and the draft may also write `bizview.yaml` (allowed path added).
- Active version with spec entries without stored documents → `build_version_tree` skips them and
  returns `missing_specs: [folder…]`; validation turns each into a problem
  (`code: missing_spec_documents`, fix: "regenera <folder>/{spec,plan,tasks}.md en el borrador"),
  never a hard error.

### 5. Origin tools (`backend/app/assistant/origin.py`, FR-006/FR-007)
- `describe_source` adds `personal: <kind>` per column from name/type heuristics (email/correo,
  nombre/name/apellido, phone/telefono/celular/movil, cedula/dni/rif/ssn/passport/documento,
  chat_id/telegram, card/tarjeta/iban/cuenta, json/jsonb named payload/raw/data). Cached per
  session in the working state: a second call for an inspected table returns the stored note
  (`refresh: true` forces a new read) — SC-005.
- `profile_source(name, table)`: PostgreSQL — identifiers validated against `describe` output and
  quoted with `psycopg.sql.Identifier`; one query: `count(*)`, per column (≤ 80) `count(col)`
  → null ratio, `count(DISTINCT col)` (skipped for json/bytea), `min/max` for date/timestamp only;
  read-only session, timeout `AI_TOOL_TIMEOUT_SECONDS` (default 20) → "tiempo agotado".
  Supabase/REST: row count only (`Prefer: count=exact`, `limit=0`); SOAP: not available.
- `check_query(source, path | sql)`: SQL → `sqlsafety.check_query` (read-only, single SELECT) →
  `SELECT * FROM (<sql>) AS q LIMIT 0` with `window_start/window_end` bound → output columns and
  `format_type` names from `cursor.description`; errors → `preview.redact_values`. Request (draft
  `requests/*.yaml`, Supabase/REST GET only) → one page with size 1 → per declared field: found?
  JSON type; never values. Result stored in `session.query_checks[path] = {sha256, ok, columns,
  error, at}`; also compares with the dataset `columns` and reports missing/extra columns.
- Personal columns: readiness pending when a draft dataset column matches a flagged column of the
  inspected source unless (a) a user message in the conversation names that column and (b) the
  integration `spec.md` has a `**Datos personales**:` line listing it.
- Same TLS/netguard rules as the worker (reuse `extract` connectors and `netguard`).
- Apply re-runs `check_query` on every draft query; a failure blocks apply with the redacted error.

### 6. Agent preview + PDF (`assistant/preview.py`, `reports/pdf.py`, FR-010/FR-011)
- `run_preview` tool: requires valid draft; at most one running (existing advisory lock) and
  `AI_CHAT_MAX_PREVIEWS` (default 5) per conversation (`stats.previews`); runs
  `runner.run_preview` **in-process** in the request (same function as the worker, `time_limit_s`
  = 120) so the agent gets the outcome in the same round; stores `session.preview` with the draft
  fingerprint; conversation chip "Ejecutó una vista previa"; result = `outcome_lines` + check
  results.
- The 014 "Vista previa" button keeps the worker path.
- `pdf.render(..., preview=False)` gains `preview` ("Vista previa" in the header and metadata) and
  honours `pdf.orientation` (`portrait|landscape`) and `pdf.views` (indexes/order of views; default
  all). `report.schema.json` `pdf` gains `orientation` and `views` (additive; CLI 0.2.0).
- `POST /api/assistant/sessions/{id}/preview/report/{rid}/pdf` → PDF from the preview data.

### 7. Loop, working state, history, budget (`assistant/service.py`, FR-012…FR-016)
- System prompt = **stable prefix** (rules + `authoring.summary()` + preset templates; no dynamic
  data) + `## Estado` suffix (working state, draft index with size/sha per file, validation
  problems ≤ 30, readiness pending, preview outcome, budget %, "≥ 80%: prioriza un borrador
  válido").
- `update_notes(goal?, decisions_add?, step?, done_add?, next?)` tool; describe/profile/check tools
  add `inspected[source][table] = short note` automatically. Stored in
  `assistant_session.working_state`.
- History: only the latest round's tool results in full; older tool results become their stored
  summary; older `propose_draft`/`edit_draft` call arguments are replaced by the file list
  (`read_draft` gets content). Applied both when loading history and inside a turn between rounds.
- `MAX_ROUNDS` → `AI_CHAT_MAX_ROUNDS` (default 20). On reaching it: one extra call with no tools
  asking for a progress message (done / next); if the budget does not allow it, a product-composed
  progress message from the working state. "continúa" is a normal message; the working state makes
  it resume.
- Budget: provider usage (`ChatUsage`); `≥ 80%` flag in the state suffix and `session_json`
  (`budget_warning`); exhausted → message + draft/working state preserved.
  `POST /api/assistant/sessions/{id}/budget` (recent re-auth) adds `AI_CHAT_BUDGET_STEP`
  (default 100 000) up to `AI_CHAT_BUDGET_MAX` (default 2 000 000); audit
  `assistant_budget_extended`.
- Every tool call is a chip (FR-016) with a Spanish label.
- `stats` jsonb: `rounds, validations, probes, previews, query_checks` (for SC-001 and the UI).

### 8. Provider (`ai/openai_compatible.py`, `ai/__init__.py`, FR-017, US6)
- `ChatMessage.reasoning: str | None` (in memory only, never stored). The OpenAI-compatible
  provider reads `message.reasoning_content` into `ChatReply.reasoning`; the loop attaches it to the
  assistant message of the **current** user turn only, and the provider sends `reasoning_content`
  back only for assistant messages after the last user message (DeepSeek thinking + tools); earlier
  turns never carry it. Anthropic provider ignores it.
- Invalid tool-argument JSON → `ToolCall(args={}, args_error="…")` instead of an error; the loop
  answers that call with "argumentos JSON no válidos: <error>; vuelve a emitir la llamada" once per
  turn, then stops with the draft preserved.
- `rate_limited` → one retry after `min(Retry-After, 10)` s; new code `context_too_long` (HTTP 400
  with context-length text) → compact history to working state + last round and retry once.
- Recorded transports (`backend/tests/fixtures/deepseek/*.json`, synthetic content) for: tool call
  round-trip, reasoning_content handling, invalid JSON repair, usage with cache-hit fields.

### Data (migration `0011_agentic_assistant`)
- `assistant_session`: add `working_state jsonb NULL`, `query_checks jsonb NULL`,
  `stats jsonb NOT NULL DEFAULT '{}'`.
- Audit kinds: add `assistant_budget_extended`.
- Downgrade drops the columns and restores the kind check (refuses if rows of the new kind exist).

### Config
`AI_CHAT_MAX_ROUNDS` (20, 1–60), `AI_CHAT_BUDGET_STEP` (100 000), `AI_CHAT_BUDGET_MAX`
(2 000 000), `AI_CHAT_MAX_PREVIEWS` (5), `AI_TOOL_TIMEOUT_SECONDS` (20, 1–120); documented in
`deploy/` env example and README.

### API (super user, CSRF)
- `POST /api/assistant/sessions/{id}/budget` (recent re-auth).
- `POST /api/assistant/sessions/{id}/preview/report/{rid}/pdf`.
- `session_json` adds `working_state`, `readiness {ready, pending[]}`, `stats`, `budget_warning`,
  validation problems with `file/path/expected/fix`.

### Frontend (`AssistantSession.tsx`, `api/types.ts`, `i18n/es.ts`)
- Tool chips for the new tools; problems list (file, path, message, fix; expected shape
  collapsible) in banner and draft cards; readiness checklist with "Listo para aplicar" pill
  (validación, consultas comprobadas, vista previa); "PDF de vista previa" download; 80% warning;
  "Ampliar presupuesto" with the existing step-up view (no modals); "Notas de trabajo" view with
  the working state; "Aplicar" enabled only when ready.

## Tests
- CLI: golden validates; summary covers required keys; exhaustive validation returns all schema
  errors of a multi-error file in one pass with `file/path/expected/fix`; `oneOf` branch selection
  (extract, incremental, checks, views, metrics).
- Backend: authoring tool; probe detection; `edit_draft` ops + limits + allowed-pattern message;
  bootstrap from template; missing pre-011 specs as fixable problems; personal-data flags;
  `profile_source` aggregates only + timeout; `check_query` (read-only enforcement, LIMIT 0 columns,
  redacted error, request shape-only); readiness rules; agent `run_preview` (never `ds_*`, max
  previews) + preview PDF; history compaction (old results → summaries, old draft args → index);
  working-state cache (SC-005: no second describe for an inspected table); round limit progress
  message; 80% warning; budget extension (step-up, audit, cap); provider recorded transports
  (reasoning not resent across turns, invalid JSON repair, rate-limit retry, context too long);
  SC-002 payload audit extended to the new tools; apply re-runs `check_query`; migration 0011.
- Frontend unit (problems list, readiness, budget warning/extension) and e2e (fake provider):
  empty installation → agent flow → ready → apply → `ds_<integration>` + dashboard + PDF (SC-003,
  SC-004).
- Live eval (opt-in `AI_LIVE_TESTS=1`): `backend/tests/live/test_agent_eval.py` runs SC-001 5×
  on the e2e reference source and reports validation cycles, probes and budget %.

## Amendment 2026-10-05: autonomous runs (FR-018…FR-020)

- `POST /sessions/{id}/messages` validates, claims the conversation (Phase 10 claim), stores the
  user message, commits and returns **202** with the session; the run continues in a background
  thread with its own DB session (`service.run_turn`, the former `send` core). A process-wide
  semaphore caps concurrent runs (`AI_AGENT_MAX_CONCURRENT`, default 4 → 409 when full). Tests
  run turns inline through an injectable runner.
- Per-run round limit `AI_CHAT_MAX_ROUNDS` default 60; stop when the model ends its turn, readiness
  is reached, the hard budget max, the round limit, or two consecutive identical failing tool calls.
- Budget: when `tokens_used >= token_budget` and `token_budget < AI_CHAT_BUDGET_MAX`, extend by the
  step automatically (audit `assistant_budget_extended`, `detail.auto = true`, no actor); at the max,
  stop with the progress summary. The budget route drops `recent_reauth`.
- "Detener": `POST /sessions/{id}/stop` clears `busy_since` (releasing the claim); the run's next
  heartbeat sees the lost claim, rolls back only the in-flight round and exits; a message
  "Detenido por el usuario." is posted.
- A process restart kills the thread; the Phase 10 stale reclaim recovers the conversation.
- UI: sending returns immediately and enters the busy/polling state (Phase 10); "Detener" button
  while busy; "Ampliar presupuesto" without step-up.
