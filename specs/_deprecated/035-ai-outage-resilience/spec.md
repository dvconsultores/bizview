# Feature Specification: Surviving an AI outage — specific provider errors, no retries into a dead provider, fixes that need no AI

**Feature Branch**: `035-ai-outage-resilience`

**Created**: 2026-10-25

**Status**: Draft

**Input**: Owner, 2026-10-26, after a working day lost on `bi.getbizview.com`: the AI provider
stopped answering at 21:12 (it had answered at 17:35), every turn of the chat answered «El
proveedor de IA devolvió un error.» with no code, no provider text and no hint, Auto mode retried
into the same dead provider until it stopped, and the fix the validator had already computed —
`Conjuntos sin unión: altseason · Arreglo: declara joins: [...]` — could only be applied through
the AI, which was down. The owner read the Caddy container logs because nothing on screen said
which container the reason was in.

**Builds on**: 003/017 (AI provider layer, assistant loop), 014/028 (Auto mode and the run
contract), 020/021 (projects, commands), 023 (app guide), 030 (visual system), 033 (admin guides),
the CLI validator (`bizview_cli.validate`).

**Starting point**: commit `d598afc` (already shipped: 402 → `no_credit`, a 400 naming the model →
`model_not_found`, the redacted provider answer logged by the turn and shown by the Probar card).
This feature keeps it and closes the rest.

## Problem

Three failures compounded, and each one alone would have been survivable:

1. **The error was anonymous.** «El proveedor de IA devolvió un error.» carries no code, no provider
   message, no model, no time, no request id. The reason existed only in the backend log, and
   nothing on screen said that — so the owner read the edge proxy's log instead.
2. **Auto kept knocking on a dead door.** Every retry cost a round, ended in «Auto · detenido», and
   left the work half done. Typing «continua» produced the same dead call again.
3. **A machine-perfect fix was blocked behind the broken machine.** The validator had already
   produced the exact edit (`joins: [{left: assets.snapshot_at, right: altseason.snapshot_at}]`),
   but the only way to write it was a chat turn.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The error says what happened and what to do (Priority: P1) 🎯

The reader whose provider refuses a call sees a code, the provider's own words and one action,
instead of a sentence that means nothing.

**Independent Test**: with a recorded provider body (402, 401, 404, 429, 5xx, malformed tool
JSON), open a conversation and send a message: the bubble names the code, the model and the action.

**Acceptance Scenarios**:

1. **Given** the provider answers `402`, **When** a turn fails, **Then** the bubble says the
   account has no balance, shows the provider's message (redacted, ≤300 chars), the configured
   provider and model, and the action **Ir a Administración → IA**.
2. **Given** the provider answers `401`/`403`, **Then** the code is `bad_key` and the action is the
   same page; with `400`/`404` naming the model, the code is `model_not_found`; with `429`,
   `rate_limited` and the action is **Reintentar**, and the reason says how long to wait when the
   provider gave `retry-after`.
3. **Given** the provider is unreachable, times out or answers `5xx`, **Then** the code is
   `provider_down` and the action is **Reintentar**.
4. **Given** any failed bubble, **When** the reader expands **Detalles técnicos**, **Then** it shows
   the timestamp, a short request id, the model, and the exact command that reads the backend log
   (`docker logs --tail 200 bizview-backend | grep -i "AI"`).
5. **Given** the same failure in Administración → IA → Probar, **Then** the card shows the code,
   the provider's answer and the same details block.

---

### User Story 2 - Auto does not spend money on a provider that is down (Priority: P1)

An Auto run refuses to start — and stops — when the provider is provably unusable, and it keeps
everything it has already written.

**Independent Test**: with the provider stubbed to answer `402` twice, start an Auto run: the run
is refused before any provider call (zero calls counted), and the draft on disk is untouched.

**Acceptance Scenarios**:

1. **Given** the last recorded AI error is `no_credit`, `bad_key` or `model_not_found` and it is
   newer than the last success, **When** the reader confirms an Auto contract or starts a
   `/speckit-*` command, **Then** the run is refused immediately with the code and the action link,
   and no request leaves the installation.
2. **Given** a healthy start, **When** two consecutive provider errors with the same non-transient
   code happen mid-run, **Then** the run stops with status `blocked:ai_<code>` and the summary keeps
   the draft, the working state and everything written so far.
3. **Given** a transient code (`rate_limited`, `provider_down`), **Then** the run makes **one**
   bounded retry (never longer than 60 s, honouring `retry-after`) and stops with
   `blocked:ai_<code>` if it fails again.
4. **Given** the provider is unhealthy, **When** the reader sends «continua», «continúa» or
   «corrige», **Then** the answer is the refusal (no provider call) and the composer shows the IA
   status pill.
5. **Given** an installation with AI off or with no key, **Then** nothing changes: the assistant is
   unavailable exactly as today and every deterministic fix still works (US3).

---

### User Story 3 - The fix the validator already knows needs no AI (Priority: P2)

The problems panel offers **Aplicar arreglo** for every problem whose correction is fully known,
in every mode, with the AI down, and the assistant uses that same fix instead of rewriting files.

**Independent Test**: a project whose `report.yaml` has no `joins` (the session-23 fixture) shows
one problem with a fix; one click applies it, validation goes 1 → 0, the diff is shown, and the
project applies — with the provider stubbed as down.

**Acceptance Scenarios**:

1. **Given** a problem with a complete, deterministic correction, **Then** the panel shows
   **Aplicar arreglo** next to the text, and **Aplicar todos los arreglos** when more than one
   exists.
2. **Given** **Aplicar arreglo** is pressed, **Then** the draft file is edited exactly as the fix
   says, validation runs again, the applied diff is shown and the change is audited like a manual
   edit.
3. **Given** a problem without a deterministic correction, **Then** no button appears (only the
   text and the hint, as today).
4. **Given** the AI is healthy and the assistant meets one of these problems, **Then** it applies
   the fix through its own tool instead of rewriting the file by hand.
5. **Given** a fix cannot be applied (the file changed since validation), **Then** the action is
   refused with a message, nothing is written, and validation is re-run so the reader sees the
   current state.

---

### User Story 4 - The installation says whether the AI is healthy (Priority: P3)

`/api/health` and the administration home answer «is the AI working?» without opening a log.

**Independent Test**: with the provider stubbed to fail once and succeed once, `/api/health` moves
from `last_error_code` to `last_ok_at`, and the Administración home pill follows.

**Acceptance Scenarios**:

1. **Given** any request, **When** `/api/health` is read, **Then** it carries an `ai` block with
   whether it is configured, the provider, the model, and the last success and last error (code and
   time) — never the key and never the provider's message.
2. **Given** Administración, **Then** a pill shows the AI state (sin configurar · funcionando · error
   `<code>`), and the IA page shows the last error with its fix.

---

### Edge Cases

- The provider reports a `400` whose body mentions both length and the model: the code is
  `context_too_long` (the reader can act on it by shortening the conversation).
- A `429` without `retry-after`: the retry waits a fixed, short time and never more than 60 s.
- The provider answers `200` with malformed tool-call JSON: one repair round, then
  `invalid_tool_call`.
- The first ever run (no `last_ok_at`, no error): treated as healthy — no refusal.
- Two conversations fail at the same time: the last error wins; neither blocks `ok_at` from being
  recorded by the other.
- The AI is turned off between the failure and the retry: the refusal disappears and the assistant
  reports «La IA no está configurada» as today.
- A fix whose `json_path` no longer exists (the file changed by hand): refused, nothing written,
  validation re-run.
- Two fixes for the same file applied in one step: applied in declaration order, one validation run
  at the end.
- A recorded provider answer longer than 300 characters: truncated with an ellipsis, and the
  truncation is not mistaken for the end of the message.

## Requirements *(mandatory)*

### Provider errors

- **FR-001**: Every provider failure MUST map to exactly one stable code: `no_credit` (402),
  `bad_key` (401/403), `model_not_found` (400/404 naming the model), `rate_limited` (429, with
  `retry_after` when the provider sends it), `context_too_long` (400 naming length/tokens),
  `provider_down` (5xx, timeouts, connection errors), `invalid_tool_call` (malformed tool JSON after
  one repair round), `provider_error` (anything else). `not_configured`, `refused` and `timeout`
  keep their current meaning.
- **FR-002**: The same mapping MUST apply to the Anthropic provider, the OpenAI-compatible provider
  and Anthropic-compatible third-party endpoints (DeepSeek `/anthropic`), including their
  non-standard bodies.
- **FR-003**: Every failure surfaced to a person MUST show: the code, a translated explanation, the
  provider's own message (redacted of keys and identifiers, max 300 characters), the configured
  provider and model, and one action — **Ir a Administración → IA** for `no_credit`, `bad_key`,
  `model_not_found`, `not_configured`; **Reintentar** for `rate_limited`, `provider_down`,
  `timeout`; no action for `refused` and `invalid_tool_call`.
- **FR-004**: Every failure MUST record its code and time for the installation (last success and
  last error), and the turn MUST log the code with the redacted provider answer.
- **FR-005**: `GET /api/health` MUST include `ai: {configured, provider, model, last_ok_at,
  last_error_code, last_error_at}`. No key, no message text, no token counts.
- **FR-006**: Administración → IA → Probar MUST run a short completion **and** a one-round tool
  call, report both, record the outcome in FR-004's status, and — when the provider offers a models
  endpoint — list the model ids it reports so a wrong configured model is visible.

### Auto mode

- **FR-007**: Before an Auto contract is confirmed and before every `/speckit-*` command starts, the
  product MUST refuse when the last recorded error is `no_credit`, `bad_key` or `model_not_found`
  and is newer than the last success — with no provider call.
- **FR-008**: During a run, two consecutive provider errors with the same non-transient code MUST
  stop the run with status `blocked:ai_<code>`; a transient code gets exactly one bounded retry
  (≤60 s, honouring `retry-after`) before stopping.
- **FR-009**: A stopped run MUST keep the draft, the working state and the summary (015 US5) and
  MUST say what was kept. Status values MUST be `blocked:ai_no_credit`, `blocked:ai_bad_key`,
  `blocked:ai_model_not_found`, `blocked:ai_rate_limited`, `blocked:ai_provider_down`.
- **FR-010**: While the provider is unhealthy, a message that only means «keep going» («continua»,
  «continúa», «corrige», «sigue») MUST be answered with the refusal instead of a provider call, and
  the composer MUST show the AI status pill.

### Deterministic fixes

- **FR-011**: Validation problems whose correction is fully known MUST carry a structured fix
  (`{file, json_path, op: set|append|insert, value}` plus the human text `Arreglo: …`), and the
  problems panel MUST offer **Aplicar arreglo** (and **Aplicar todos los arreglos** when there is
  more than one) in the project workspace and in the assistant panel, in every mode, with the AI
  down.
- **FR-012**: Applying a fix MUST write through the same path as a manual edit (revision, audit,
  ready-check), re-run validation, show the resulting diff, and refuse — writing nothing — when the
  file no longer matches what validation saw.
- **FR-013**: These rules MUST ship with a structured fix: missing `joins` between `uses` sets;
  missing `date`; missing `label`/`label_en`; unknown chart type (suggested type); missing
  `schedule` (default); missing `layout.theme.palette` (installation default); an undeclared filter
  referenced by a layout (remove the reference). Each is a pure function with a before/after test.
- **FR-014**: The assistant MUST apply these rules through a tool (`apply_fix`) instead of rewriting
  the file with `edit_draft`, when the AI is healthy.

### Where to look

- **FR-015**: Every provider-error bubble and the Probar card MUST include a collapsible
  **Detalles técnicos** with the exact log command, the timestamp, the model and a short request id.
- **FR-016**: The administration guide MUST gain a «Problemas frecuentes» section listing every code,
  its meaning and its fix, and the in-app help MUST answer «la IA devolvió un error» from it.

### Quality

- **FR-017**: WCAG AA, keyboard reachable, `prefers-reduced-motion` respected, mobile-first; every
  string in `es.ts`/`en.ts` (server messages in `app/i18n/{es,en}.py`); no key, token or
  provider-side identifier in any user-visible text or log line.

### Key Entities

- **AI status**: the installation's last success (`at`), last error (`code`, `at`) and the model the
  provider answered with. One per installation; no key material.
- **Structured fix**: the machine-applicable half of a validation problem — the file, where in it,
  the operation and the value — published next to the human `Arreglo:` text.
- **Run stop reason**: why an Auto run stopped, expressed as `blocked:ai_<code>` so the summary and
  the audit line agree with the bubble.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reader whose provider refuses a call can name the cause and the next step without
  opening a terminal: the bubble carries code, provider text and action for 100% of the failure
  kinds in FR-001.
- **SC-002**: Zero provider requests are made when an Auto run is refused (asserted by a spy on the
  transport) and at most **two** for a run that stops mid-way on a non-transient code.
- **SC-003**: The session-23 situation (a `report.yaml` without `joins`) goes from 1 problem to 0,
  and the project applies, with **one click** and the AI down.
- **SC-004**: `/api/health` answers the AI state in every installation, configured or not, and the
  Administración home pill matches it in both themes.
- **SC-005**: No provider failure anywhere leaves the reader with a message that has no code —
  verified by a test that walks every code in FR-001 and asserts a translated, actionable text.
- **SC-006**: A wrong model is diagnosable without a restart: the Probar card lists the model ids the
  provider reports, and the configured one is marked when absent.

## Assumptions

- The provider's own error body is the best diagnosis available and is safe to show once redacted
  (no key, no token, no user data; product code sends only aggregates and metadata — principle VIII).
- Recording one last-success and one last-error per installation is enough; no per-user history.
- Deterministic fixes are a validator concern (principle IX): the rules and their corrections live
  beside the rule, not in the interface.
- A restart is not required after fixing the key, the balance or the model: the next turn retries
  and the status clears on its own.
- The in-app guide (033) is generated from the same catalogue used by the admin page, so the
  «Problemas frecuentes» section is written once.
