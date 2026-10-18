# Implementation Plan: Vibe-reporting chat

**Branch**: `014-vibe-chat` | **Date**: 2026-10-02 | **Spec**: [spec.md](./spec.md)

## Summary

A super-user "Asistente" with stored conversations. The AI runs a bounded server-side tool loop
(list sources, describe structure, read the active workspace, propose a draft); drafts are workspace
files validated by the same validator on a temporary tree built from the active version + draft;
"Vista previa" runs the draft integration on a short window into a temporary schema and renders the
draft report; "Aplicar" (step-up) creates a new workspace version from that tree. Depends on 011
(spec texts stored) and 013 (controls survive versions).

## Technical Context

Python 3.12 / FastAPI / SQLAlchemy / Alembic (migration `0009_assistant`); provider SDKs already
present (anthropic, httpx for OpenAI-compatible). React 19 / Tailwind frontend. Tests never call a
live AI (fake provider; `AI_LIVE_TESTS=1` opt-in only).

## Constitution Check

VIII (AI optional and private): only structure, metadata, validation messages, run status and row
counts reach the provider — enforced by a single sanitising tool layer and tested (SC-002). IX
(spec-driven): drafts are full specs + artifacts validated with "no spec, no run"; nothing runs
without the super user's Vista previa / Aplicar. Product schema via Alembic. Views not modals.
→ PASS.

## Design

### Provider
- `Provider.chat(messages, *, tools, system, max_tokens) -> ChatReply(text, tool_calls[{id,name,args}],
  usage{input,output})` for AnthropicProvider (tool_use blocks) and OpenAICompatibleProvider (tools /
  tool_calls); `complete()` unchanged. Same error mapping/redaction.
- `FakeProvider` for tests (scripted replies), selectable only when `BIZVIEW_TEST_HOOKS=1`.

### Tools (server-executed, `app/assistant/tools.py`)
- `list_sources()` → [{name, kind}] from Fuentes de datos.
- `describe_source(name, path?)` → `app.sources.describe.describe(...)` output (structure only) passed
  through `sanitize()` (drops any key named like sample/example/value(s)/rows, caps sizes).
- `get_workspace()` → active version: integrations/reports ids, definitions, SQL/request files, spec
  metadata and documents (011), the workspace manifest.
- `propose_draft(files: {relative_path: text}, summary)` → paths restricted to `specs/integrations/*`,
  `specs/reports/*`, `integrations/<id>/**`, `reports/<id>/**`; ≤ 40 files, ≤ 512 KB each; stores the
  draft on the session and returns the validation issues.
- No tool can run SQL on a source, preview, apply or change controls.

### Loop (`app/assistant/service.py`)
- `send(session, text)`: append user message; up to 8 provider rounds; each tool call executed and
  logged as a `tool` message (name + short summary shown in the UI, full result stored); history sent
  = system prompt (workspace rules + preset templates from `cli/bizview_cli/workspace_template`) +
  last 30 messages + current draft summary; tokens counted against `token_budget` (default
  `AI_CHAT_TOKEN_BUDGET=200000`); budget exceeded → assistant message says so, no more calls.

### Draft validation / apply
- `build_tree(db, draft) -> Path`: temp dir with `bizview.yaml` (manifest), every active integration
  and report (`integration.yaml`/`report.yaml` dumped from definitions + their files), their spec
  folders from stored documents (011; if any document is missing → error "Aplica una vez el
  espacio de trabajo desde Git para guardar sus specs" ), then the draft files on top; run
  `wsv.validate(root, known_sources=…)` and write the lock in the tree.
- `apply_tree(db, actor, root, origin)` generalises `service.apply` (shared code path: same checks,
  version row with `commit=None`, `source="chat:<id>"`, documents stored, dashboards synced, audit).
- Re-validated at apply time against the then-active version.

### Preview
- Request row `assistant_preview` processed by the worker: run the draft integration with
  `runner.run_integration(..., preview_schema="preview_<session id>", window ≤ 7 days, no publish
  outside that schema)`; store status/row counts/errors on the session.
- Report preview: `GET /api/assistant/sessions/{id}/preview/report/{report_id}/data` uses the report
  engine with tables resolved in the preview schema; the frontend reuses the report components in a
  "Vista previa" frame.
- Cleanup: drop `preview_<id>` on apply/archive and in the worker after 24 h.

### Data (migration 0009_assistant)
- `assistant_session(id, title, created_by FK, status open|applied|archived, draft jsonb,
  validation jsonb, preview jsonb, applied_version_id FK NULL, tokens_used int, token_budget int,
  created_at, updated_at)`.
- `assistant_message(id, session_id FK cascade, role user|assistant|tool, content text, tool_name
  NULL, tool_payload jsonb NULL, created_at)`.
- `assistant_preview_request(id, session_id, requested_by, taken_at, finished_at)`.
- Audit types: `assistant_draft_applied`, `assistant_session_archived`.

### API (super user, CSRF) `/api/assistant`
- `GET/POST /sessions`, `GET /sessions/{id}`, `POST /sessions/{id}/messages`, `POST /sessions/{id}/preview`,
  `GET /sessions/{id}/preview`, `GET …/preview/report/{report_id}` + `/data`, `POST /sessions/{id}/apply`
  (recent re-auth), `POST /sessions/{id}/archive`; `GET /api/workspace/versions/{id}/export.zip`
  (FR-009, super user).

### Frontend
- `pages/admin/Assistant.tsx` (list + "Nueva conversación"), `pages/admin/AssistantSession.tsx`
  (transcript, tool chips, composer, draft cards with validation pill, Vista previa, Aplicar, token
  usage); draft details and preview as `View`s; phones stack; nav item "Asistente" for the super
  user when AI is configured.

## Tests
- Backend: provider `chat()` mapping for both providers (mocked transports); tool sanitisation; loop
  with FakeProvider (tool calls, budget, max rounds); draft path restrictions; build_tree + validation
  incl. "no spec, no run"; preview into temporary schema never touches `ds_*`; apply creates a version
  equal to a Git apply of the same files; SC-002 payload audit (seeded distinctive row values and the
  source password never appear in any request sent to the fake provider).
- Frontend unit for transcript/draft cards; e2e with the fake provider (test hooks): conversation →
  valid draft → preview → apply → dashboard visible → rollback.
