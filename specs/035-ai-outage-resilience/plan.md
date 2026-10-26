# Implementation Plan: Surviving an AI outage

**Branch**: `main` (owner rule: never a new branch) | **Date**: 2026-10-26
**Spec**: [spec.md](./spec.md)

## Summary

Make an AI outage survivable instead of fatal: give every provider failure a specific code, a
provider message, one action and a «Detalles técnicos» block (backend + bubble + Probar card);
record the installation's AI status and publish it in `/api/health` and an Administración pill;
refuse Auto runs and `/speckit-*` commands — with no provider call — while the provider is provably
unusable, and stop a run after two identical non-transient failures while keeping its work; and
give the validator's deterministic corrections a machine-applicable form so **Aplicar arreglo** in
the problems panel (and the assistant's `apply_fix` tool) fix the session-23 case with one click
and no AI at all.

## Technical Context

**Language/Version**: Python 3.11+ (backend, worker, CLI), TypeScript 5 (React 19 SPA).
**Primary Dependencies**: FastAPI, SQLAlchemy 2, Alembic, `anthropic` SDK, `httpx` (OpenAI-compatible),
`jsonschema` + `sqlglot` (CLI validator), Tailwind + Lucide. **No new dependency.**
**Storage**: PostgreSQL. One new table `ai_status` (single row), migration `0028_ai_status`.
Assistant failures reuse `assistant_message.tool_payload["error"]` (028 does the same with
`contract`), so no second migration.
**Testing**: `pytest` (backend + CLI, FakeProvider and `httpx.MockTransport` — never a live model),
`vitest` + Testing Library (frontend).
**Target Platform**: Linux containers (backend, worker, Caddy) and any modern browser.
**Project Type**: web product — Python backend + worker, React SPA, CLI validator shipped to
customers' workspaces.
**Performance Goals**: a refusal costs no provider call and no more than one DB read; the bubble
renders with the message it arrives in (no extra request); `/api/health` stays a single round trip.
**Constraints**: keys never logged or returned (VIII); every string in `es`/`en`; deterministic
fixes are validator rules (IX); no new stack component (V); mobile-first, WCAG AA (I).

## Constitution Check

*GATE: evaluated before Phase 0 and re-evaluated after Phase 1.*

| Principle | How this feature satisfies it |
|---|---|
| I. Mobile-first | Bubble grows with content, details collapse by default, actions are ≥44 px targets; nothing new is a fixed-width column. |
| II/VI. Backend as ETL | Untouched: no origin query, no dataset. |
| III. Source of truth external | Untouched: the provider message is metadata, never source records. |
| IV. Folders | Backend code in `backend/app/{ai,assistant,projects}`, CLI rules in `cli/bizview_cli`, UI in `frontend/src`, docs in the in-app guide. |
| V. Fixed stack | No new component: the models list uses the providers' own endpoints over the existing SDK/httpx; the status row is a normal Alembic table. |
| VII. One product | Codes and texts are product data (`es`/`en`), not per-installation configuration. |
| **VIII. AI optional and private** | **Strengthened**: the fix layer makes the validator's corrections applicable with AI off, and the refusal path guarantees a broken provider never blocks editing, validating or applying. Only aggregates/metadata keep going to the provider; the stored provider message is redacted (no key, no ids) and capped at 300 chars. |
| IX. Spec-driven | The deterministic fixes *are* validator rules with a declarative `fix_data`; the assistant must use them instead of rewriting YAML. |
| Constraints | Every string in both languages; Alembic owns the new table; no HTML from the API; keys never logged. |

**Result: PASS.** No existing gate is weakened.

## Phase 0 — Research (research.md)

R1 stable code set · R2 mapping per provider incl. DeepSeek bodies · R3 where the status lives ·
R4 refusal without a provider call · R5 retry budget & stop rule · R6 structured fix shape ·
R7 pre-schema vs post-schema rules · R8 how the bubble gets its data · R9 models list · R10
request id. See [research.md](./research.md).

## Phase 1 — Design

- [data-model.md](./data-model.md): `AIStatus`, provider error payload, `fix_data`, run stop reason.
- [contracts/](./contracts/): `health-ai.md`, `provider-errors.md`, `project-fixes.md`.
- [quickstart.md](./quickstart.md): runnable end-to-end scenarios, including the session-23 fixture.

### Source layout (files this feature touches)

```
backend/app/ai/__init__.py            codes, AIError.retry_after, redaction + truncation helper
backend/app/ai/anthropic_provider.py  exception → code, list_models()
backend/app/ai/openai_compatible.py   status/body → code, list_models()
backend/app/ai/service.py             status(), test_connection() (completion + tool call + models)
backend/app/ai/state.py               NEW: read/record ai_status (one row)
backend/alembic/versions/0028_ai_status.py  NEW
backend/app/api/health.py             ai block
backend/app/api/ai.py                 /test returns codes, details and models
backend/app/assistant/service.py      refusal (contract/command/«continua»), consecutive-failure
                                      stop, error payload on the message, log with request id
backend/app/assistant/tools.py        apply_fix tool
backend/app/projects/fixes.py         NEW: apply fix_data through fs.apply_ops, audit, revalidate
backend/app/api/projects.py           POST /{slug}/fix
backend/app/i18n/{es,en}.py           codes, actions, refusals, details
cli/bizview_cli/validate.py           Issue.fix_data + pre-schema fixable rules + joined/date fixes
cli/bizview_cli/report_layout.py      palette/filter fixes where the rule lives
frontend/src/components/assistant/ProviderError.tsx  NEW bubble body
frontend/src/components/assistant/AssistantChat.tsx  IA pill + refusal
frontend/src/components/ide/ProblemsPanel.tsx        Aplicar arreglo / Aplicar todos
frontend/src/pages/admin/AI.tsx                      codes, details, models list, status
frontend/src/pages/admin/AdminHome.tsx               IA pill
frontend/src/api/{types,projects}.ts                 error payload, fix endpoint
frontend/src/i18n/{es,en}.ts                         strings
backend/app/assistant/guide/{es,en}/ia.md            «Problemas frecuentes»
CHANGELOG.md                                          Unreleased
```

## Phase 2 — Delivery in four commits (as the owner asked)

1. **Error mapping + health + Probar** — codes (incl. `bad_key`, `provider_down`,
   `invalid_tool_call`), `AIError.retry_after`, redaction/truncation, `ai_status` + migration,
   `/api/health.ai`, `/api/admin/ai/test` (completion + tool call + models), admin page.
2. **Auto refusal / stop** — pre-run refusal for `no_credit`/`bad_key`/`model_not_found`, refusal
   for «continua»/«corrige», two-strike stop with `blocked:ai_<code>`, one bounded retry for
   transient codes, work preserved.
3. **Structured fixes** — `Issue.fix_data`, the seven rules, `POST /{slug}/fix`, `apply_fix` tool,
   problems panel buttons.
4. **UI details + docs + CHANGELOG** — `ProviderError` bubble with Detalles técnicos, IA pill in
   the composer and the admin home, guide section, changelog.

## Post-design Constitution re-check

- VIII: the refusal path and the fix layer make the product usable with AI off; the stored provider
  message is redacted and capped; nothing sensitive is added to `/api/health`.
- IX: fixes are declarative data produced by validator rules; the assistant is steered to the tool
  that applies them instead of hand-writing YAML.
- V: no new dependency; the models list uses `GET /models` (OpenAI-compatible) and
  `client.models.list()` (Anthropic SDK).

**PASS.**

## Risks & mitigations

| Risk | Mitigation |
|---|---|
| Renaming `invalid_key`→`bad_key`, `timeout`/`unreachable`→`provider_down` breaks existing tests or UI | Grep every code; update i18n, tests and the turn's retry logic in the same commit; a test walks every code and asserts a translated, actionable text. |
| A fix writes the wrong YAML | Fixes are produced by the validator itself, are JSON-pointer operations, and are applied only when the file still hashes what validation saw; the applied diff is shown. |
| Recording status on every turn adds a write | One UPSERT per failed turn and one per successful turn, in its own short session (`view._persist` pattern), never inside the turn's transaction. |
| `blocked:ai_<code>` breaks the Auto summary | `run.status` keeps its enum; the code travels in `stop_reason` and in the summary text the reader sees. |

## Complexity Tracking

No constitution violations, so no entries. The one added table (`ai_status`) is the minimum needed
to answer «is the AI working?» across requests.
