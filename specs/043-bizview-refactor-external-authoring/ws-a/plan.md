# Plan: 043 WS-A — Remove the authoring agent (+ WS-G Administración home)

**Input**: specs/043-bizview-refactor-external-authoring/spec.md (WS-A, WS-G) ·
**Constitution**: 3.0.0 · **Created**: 2026-10-29

One PR, five sequential batches. Detach first, delete second: nothing that import, preview,
apply or the Help page needs may die with the agent.

## Constitution Check

- IX (3.0.0): this plan implements the redefinition — the agent, its commands and its tables go.
- VIII: the provider layer keeps `complete()` only; no tool-calling remains. `AI_PROVIDER`
  already defaults to `none`.
- V: no stack change. `anthropic` stays (narrative uses `AnthropicProvider.complete`).
- Constraints: product schema change via one new Alembic migration; all removed user-visible
  strings leave both `es` and `en` together.

## Decisions (Claude, 2026-10-29 — audit against these)

- **D1 — Narrative survives.** The only production caller of `complete()` is
  `backend/app/engine/narrative.py` ("Resumen con IA", feature 005, declared per report spec,
  aggregates only). The spec's "kept for the help agent (033) only" was written against a help
  agent that has no code yet. Removing narrative would remove an owner-ratified 005 feature, so
  the surviving provider surface is: `Provider.complete`, `AIReply`, `AIError`, `get_provider`,
  `redact`, both providers' `complete` paths, `ai/errors.py` minus chat-only codes. Everything
  tool-calling (`Provider.chat`, `ToolSpec`/`ToolCall`/`ChatMessage`/…, `history_rules.py`,
  `fake.chat`, `_chat_timeout`) is deleted.
- **D2 — `/admin/ia` stays as a slim settings page** (provider, key, model, base URL, test) —
  the spec keeps "AI settings … for the help agent and the Claude connector, both optional".
  It leaves the Secciones grid (WS-G) and the `ia` help topic links to it; `ai/state.py` outage
  machinery and the `ai_status` table (035, deprecated) are dropped — narrative returns to plain
  per-call error handling; the "IA funcionando" pill and `useAIHealth` go.
- **D3 — Preview is re-keyed by project.** `assistant/preview.py` moves to
  `backend/app/projects/preview.py`; the `assistant_preview_request` table is replaced by
  `preview_request` keyed by `project_id` (+ requesting user); `engine/runner.run_preview`,
  `engine/datasets.preview_prefix`, `engine/report.PreviewVersion`, `worker.py`'s queue and
  `projects/apply.drop_for_session` → `drop_for_project` follow. The preview API routes under
  `/api/projects/{slug}/preview*` keep their shape.
- **D4 — Readiness becomes deterministic.** `assistant/readiness.py` moves to
  `backend/app/projects/readiness.py`. `query_check` items are satisfied by running
  `origin.run_check` for every query/request file during `POST /projects/{slug}/validate`
  (and re-checked at apply via the kept half of `origin.recheck_draft`). Personal-data
  confirmations move from conversation `working_state` to a project-level confirmation persisted
  on the project and surfaced on the project/import page.
- **D5 — Moves, not rewrites**: `assistant/guide/` → `app/guide/` (minus `ayuda.py`, `_ayuda.md`,
  chat-only helpers and the 14 `agente` topics — `tipos-de-spec`, `definir-*`, `distribuciones`,
  `metodo-spec-kit` are parked in `specs/043-…/drafts/guide-reuse/` for WS-B/WS-H, not deleted);
  `assistant/origin.py` check half → `app/projects/origin_checks.py` (profile/describe tool half
  deleted); `assistant/personal.py` → `app/projects/personal.py`; `tree.bootstrap_manifest` →
  `projects/compose.py` (or `projects/tree.py`); `WorkView` simplified to project-only;
  frontend `PreviewReports.tsx` → `components/projects/`, `relativeTime` → `lib/`.
- **D6 — Migration order**: first fix `0029` (its `upgrade()` imports `app.assistant.repair`;
  inline or no-op that step so fresh installs survive the package deletion), then one new drop
  migration after 0040 that (a) for every applied conversation verifies the spec folder exists in
  the project files and writes it from the session draft if missing, (b) creates
  `preview_request` and migrates pending rows, (c) drops `assistant_*`, `ai_status`, the
  `project_file_revision.session_id`/`command_run_id` FKs (columns kept as plain nullable ints
  for history) and `app_user.attachments_notice_at`. Historical `assistant_*` audit kinds stay
  in `AUDIT_KINDS` (rows exist); no new rows are written.
- **D7 — SC-002 grep gate** (`asistente|speckit-|run_contract|token_budget`) runs in CI over
  `backend/app frontend/src docs README*` and **excludes** `cli/bizview_cli/workspace_template/`
  (the external skeleton legitimately ships `speckit-*` commands), `specs/`, `CHANGELOG.md` and
  Alembic history.
- **D8 — WS-G rides Batch A3**: AI card out of `adminTiles.ts`, pill out of `AdminHome.tsx`,
  reworded `tokensText`/`projectsText`, new "Paquete de autoría" card ships with WS-B (the page
  it links to does not exist yet) — WS-G acceptance 2 is split accordingly and noted in tasks.

## Batches (each: brief → apply verbatim → verify → audit → correct)

- **A1 Detach** (backend): D4 and the D5 moves that are behavior-preserving (guide, origin check
  half, personal, `tree.bootstrap_manifest`); `api/guide.py` re-pointed; D4's deterministic
  readiness path is **additive** (validate runs the checks; the agent's path keeps working).
  Suites green with the assistant still present. — *Amended 2026-10-29: D3 (preview re-key) and
  the WorkView simplification move to A2: `validation`/`query_checks`/`preview` already live on
  the Project (WorkView), and preview's session coupling (advisory locks, conversation messages,
  `_view`) cannot be re-keyed while the chat still runs it.*
- **A2 Delete backend + re-key**: D3 preview re-key (project-keyed schemas and lock, worker
  queue on the new `preview_request`, `record_outcome` retired — the outcome lives in
  `project.preview`), WorkView simplified to project-only; then `app/assistant/`,
  `api/assistant.py`, testhooks, tool-calling provider surface (D1), 035 state machinery (D2),
  config settings (spec'd list), models/constants, `main.py`, `worker.py` leftovers,
  `projects/*` session parameters and busy-gates, backend i18n deletions, D6 migrations,
  `cli.py` `import_open_drafts` removal.
- **A3 Delete frontend + WS-G**: moves first (D5), then `components/assistant/`, pages, routes,
  `routeAccess`, api clients, `types.ts` blocks, i18n groups (`assistant` minus `downloadZip`
  relocation, `chatAttachments`, slim `ai`, `nav.ai` etc.), `AppShell`/`ShellChrome`/
  `ProjectWorkspace`/`Projects`/`Help`/`Security`/`PaneTabs`/`StatusBar` edits, AdminHome per D8.
- **A4 Tests**: delete the ~62 backend + ~26 frontend assistant suites, edit the ~20 + ~5
  touched ones, rewrite `projects.spec.ts` e2e around import/preview/apply, `conftest.py`
  cleanup, `guide-drift` re-pathed. Full suites run once at the end of A4 (code first, test last).
- **A5 Docs, deploy, gate**: `.env.example`, `install.sh`, `bizview.yml`, `Caddyfile`,
  README/README.es, `INSTALL.md`, `VIBE-REPORTING.md`, `copilot-instructions`, delete
  `DIAGNOSIS.md`/`prompt_*.md`/`tmp/dev041`, CHANGELOG 0.2.0 "Removed" (014, 015, 017, 021,
  024, 028, 029, 035, 036, 039, 040 by number), CI grep gate (D7).

## Verification

- Per batch: `ruff` + focused pytest / vitest on touched areas; A1 additionally full backend
  suite (behavior-preserving gate).
- End of A4: full backend + frontend + e2e suites, `alembic upgrade head` on a fresh test
  schema (proves D6/0029).
- A5: grep gate green locally before it lands in CI.

## Complexity Tracking

Deviation none. D1 narrows the spec's wording ("help agent only") without widening scope; the
owner ratifies it implicitly by keeping 005 — flagged in the session report for explicit
ratification.
