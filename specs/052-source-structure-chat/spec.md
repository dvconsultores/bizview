# Feature Specification: Per-source structure — "Descargar estructura" and "Generar estructura con IA"

**Product**: Bizview · **Feature Branch**: `052-source-structure-chat` (worked on `main`) ·
**Created**: 2026-11-03 · **Status**: Approved — converged 2026-11-03: the structure chat is
replaced by one button that generates the pack with AI (owner decision, `## Clarifications`)

**Input**: Owner, 2026-11-03: "I have the connection to CoinMarketCap connected. In the scope we
need the AI chat to indicate the database structure (tables, types, etc.), and it was removed.
Each connection can have its own chat to indicate structure."

**What the repo has today** (checked on `main`, 0.2.0): `GET /api/sources/{name}/describe`
(structure only; PostgreSQL tables/columns/keys, REST response `shape` of a path, Supabase tables,
SOAP operations; audited; token or session), the CLI `bizview describe`, an AI provider layer with
`complete()` (Anthropic / OpenAI-compatible) and `GET /api/admin/ai` + `POST /api/admin/ai/test`
status/test, and the guide of 033 (an index of topics, answered without a provider). **Missing**:
any UI on the source page to see or download the structure, the structure pack that 043 WS-B
promised (`sources/<name>/structure.md` + `structure.json` — the starter pack ships the *template*
only), and a way to ask questions about a source. 045 removed the authoring chat; it did not
replace the one thing of it that the owner still needs: knowing what a source contains.

**Decision**: each source gets an **Estructura** tab with (1) the structure rendered and
downloadable as the authoring pack expects, and (2) **one button — "Generar estructura con IA"** —
that runs an internal, non-interactive pass: Bizview scans the source, the AI identifies what can be
extracted (tables or endpoints, fields, types, keys, relations, date fields, pagination, personal
data), product code verifies every name against the scan, and the result *is* the structure pack
handed to the other AI, the one that builds the dashboard outside Bizview. The user types nothing.
AI stays optional (VIII): without a provider the tab still shows and downloads the plain scan.
*(Replaces the read-only structure chat this spec first delivered; the owner reviewed it on
production and asked for the button instead: "the simpler the better".)*

**Builds on**: 004 (sources), 043 WS-B (authoring pack), 048 (BI-ready flag in the pack), 033
(guide/help boundary), 003 (provider layer), 019/048 (direct reads remain the only data path).

---

## Clarifications

### Session 2026-11-03

- Q: Does "Descargar paquete de autoría" (starter pack + structure) ship with this feature? → A: No.
  It needs the authoring pack as CLI package data and it belongs on the project screen (043 WS-B);
  this feature ships "Descargar estructura" (`structure.md` + `structure.json`) and leaves the pack
  zip with US3.
- Q: Where do the two tabs live? → A: On the existing source detail page
  (`/admin/fuentes/:id`): `Conexión` is the form as it is today, `Estructura` is new.
- Q: When is the structure read? → A: On first open of the tab, and again only when the super user
  presses **Actualizar**; the tab keeps what it last rendered while the request is in flight.
- Q: How are date ranges obtained without reading rows? → A: one `min()`/`max()` per date or
  timestamp column (at most 3 per table) inside the describe connection; no row is ever returned
  or stored. 043 WS-B names exactly this and the pack template prints it.
- Q: How does the chat refuse a data request — prompt or code? → A: both. Product code refuses
  first, before any provider call, so a fix in the prompt can never leak a data request; the system
  prompt repeats the rule so drafts stay clean.
- Q: Which setting holds the daily cap? → A: `AI_STRUCTURE_CHAT_DAILY_TOKENS`, default 100 000 per user per
  source per UTC day; a refusal says how much is left tomorrow and points to Administración → IA.
- Q: Are question texts stored? → A: only when the installation sets `AI_STRUCTURE_CHAT_STORE_QUESTIONS`
  (default off); token counts and audit entries are always recorded.
- Q: A chat, or something else? → A: **no chat.** The owner reviewed the implementation on
  production (`/admin/fuentes/2`, source `coinmarketcap`) on 2026-11-03 and replaced it with **one
  button, "Generar estructura con IA"**, that produces the pack in one internal pass. The chat, its
  endpoint, its history table and its prompt are removed; the tab, the downloads, the sample
  requests, the observations, the describe endpoint, the audit and SC-002's data boundary stay.
- Q: Who writes `structure.md` once the AI has enriched the pack? → A: product code. The AI returns
  the JSON document only; `structure.md` is rendered from it, so the two files cannot disagree.
- Q: What happens when the AI pass fails or the provider is off? → A: the plain scan stays the pack.
  A failed run changes nothing (`structure_pack` keeps its previous value) and the tab says why.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — See and download the structure of a connection (Priority: P1) 🎯

The super user opens Fuentes de datos → `coinmarketcap` → tab **Estructura**. Bizview reads the
source (structure only) and shows it: for PostgreSQL, schemas → tables → columns (type, nullable,
keys, row count, date min/max, personal-data flag); for REST, the saved **sample requests**
(method, path, params) with the response shape, suggested `records` and `fields` JSONPaths; for
Supabase, tables; for SOAP, operations. "Descargar estructura" produces
`sources/<name>/structure.md` + `structure.json` (the authoring-pack format); "Descargar paquete
de autoría" bundles the starter pack with this source's structure.

**Why this priority**: it is the whole point of the request — the owner cannot write a spec for a
connection he cannot see — and it works with no provider configured.

**Independent Test**: on the demo PostgreSQL source and on CoinMarketCap, the tab renders in
under 10 s, the download matches the format in `pack/` (`sources/<nombre>/structure.md`
template), and a seeded distinctive row value never appears anywhere (014 SC-002 reused).

**Acceptance Scenarios**:

1. **Given** a PostgreSQL source, **When** Estructura opens, **Then** it lists schemas, tables and
   views with columns (type, nullable, PK/FK), estimated row counts, min/max of date columns,
   and flags likely personal columns (email, name, phone, document id, chat ids) with a
   "personal" chip; a search box filters by name; large catalogues paginate per schema.
2. **Given** a REST source, **Then** the tab has "Peticiones de muestra": the super user adds
   method/path/params (stored on the source; no secrets), Bizview runs each through the stored
   credential and shows the response shape (keys/types, array lengths, one scrubbed example for
   enums/dates only), with suggested `records` and `fields`; existing `path` describe output is
   reused.
3. **Given** "Descargar estructura", **Then** `structure.md` and `structure.json` follow the pack
   template exactly (sections per kind; "Observaciones" with what the source does not have, the
   BI-ready flag from 048 when set, plan/budget notes the super user typed), and the download is
   audited (`source_described`).
4. **Given** `AI_PROVIDER=none`, **Then** everything above works; the chat panel shows one line
   on how a super user can enable AI.

---

### User Story 2 — Generate the structure pack with AI, in one pass (Priority: P1)

With AI configured, the Estructura tab has one button: **Generar estructura con IA**. The super user
presses it and types nothing. Bizview scans the source (describe plus, for REST/Supabase, the saved
sample requests, the OpenAPI document when the source exposes one, and the base path listing), sends
that scan to the provider in chunks, and asks for one strict JSON document: the logical tables, their
fields with types and semantics, the row key, the date field, relations between tables, pagination
and incremental strategy, the personal-data columns, the suggested `records`/`fields` JSONPaths and
the notes that say what one row is — plus metrics the structure makes computable, marked as
suggestions. Product code verifies every name against the scan, drops what does not exist, and saves
the result as the pack. "Descargar estructura" then serves that pack, and `structure.md` is rendered
from it.

**Why this priority**: it is the whole point of the owner's request — the pack is what the external
AI reads — and it degrades to the plain scan when there is no provider.

**Independent Test**: with a fake provider over recorded CoinMarketCap responses, the button
produces a schema-valid `structure.json` whose relations reference fields that exist, whose
`dropped` lists the planted fake table, and whose `structure.md` renders with the pack template's
sections.

**Acceptance Scenarios**:

1. **Given** a REST source with saved samples, **When** "Generar estructura con IA" runs, **Then**
   the scan (describe + every sample's shape + the discoverable endpoints) is what reaches the
   provider — never a credential, a host or a row value (payload audit) — and the answer becomes the
   saved pack with `generator.mode: ai`, the model and the token usage.
2. **Given** an answer that names a table the scan does not have, **Then** it is dropped and listed
   under `dropped`; relations that reference a field absent on either side are dropped the same way;
   the tab shows the list.
3. **Given** a malformed answer, **Then** one repair round is attempted; if it fails again, the run
   fails with a typed error (035 vocabulary) and the previous pack — or the plain scan — is still
   what the tab and the download serve.
4. **Given** `AI_PROVIDER=none`, **Then** the button is disabled with the line that explains how a
   super user enables AI, and everything else (tab, samples, notes, downloads) works.
5. **Given** a PostgreSQL source, **Then** relations that the catalogue already knows (foreign keys)
   are part of the pack even with no AI pass, and an AI pass adds semantics and notes on top.
6. **Given** a second run, **Then** the previous pack is kept beside the new one and the tab offers
   "Ver cambios" (tables and fields added, removed, changed).

---

### Edge Cases

- Huge PostgreSQL catalogues (1 000+ tables): one describe, capped at 300 tables and 200 columns
  per table, and the pack says it was truncated; reading per schema on demand and picking schemas
  with checkboxes is deferred (see Out of scope).
- Personal-data flags are heuristics: the super user can toggle a column's flag; the choice is
  saved and travels in the pack.
- The scan does not fit one model call: it is chunked per schema or endpoint, at most 6 chunks per
  run, and a per-run token ceiling (setting, default 150 k) stops a run that would cost more; the
  pack then says what was not examined.
- Prompt injection in column names/comments: the scan is data; the internal prompt says so, and the
  name check (US2/AC2) drops anything fabricated.
- A source that exposes an OpenAPI document with hundreds of paths: it is read as names and types
  only and never in full; over the chunk budget the run says so instead of pretending.
- REST sample with pagination: the shape shows the first page; `pagination` suggestion based on
  known keys (`next`, `cursor`, `page`, `total`).
- SSRF/limits: describe and samples use the source's stored base URL only; `path` must be
  relative; timeouts 20 s; response body capped at 1 MB for shaping, the connector's existing limit
  (the brief's 2 MB is an upper bound, and being stricter with a customer's payload is not a loss).
- Share with a consultant: the download is the artifact; no public links.
- A source that is unreachable, disabled, or whose credential was revoked: the tab shows the
  035-style typed error, keeps the last structure it rendered for the session, and the download
  refuses instead of producing an empty pack.

## Requirements *(mandatory)*

### Functional

- **FR-001**: Source detail gets tabs `Conexión | Estructura`; Estructura renders the structure per
  kind with search, personal flags (toggleable, persisted), row counts and date ranges
  (PostgreSQL), the generated tables with their fields, keys, relations and notes
  (REST/Supabase/PostgreSQL after a run), and operations (SOAP).
- **FR-002**: Sample requests stored per REST/Supabase source (`method`, `path`, `params`,
  `name`, `notes`); executed on demand through the stored credential; shape, `records`/`fields`
  suggestions and `timestamp_units` inferred by product code. They are also an input of the scan.
- **FR-003**: "Descargar estructura" → `structure.md` + `structure.json`. When a generated pack
  exists it is what both files carry (`structure.md` rendered from the JSON by product code);
  otherwise the plain scan is. One generator, used by the UI, by
  `GET /api/sources/{name}/structure?format=md|json&mode=pack|scan` and by
  `bizview describe --pack`.
- **FR-004**: `POST /api/sources/{name}/structure/generate` (super user, recent re-authentication):
  scan (no AI) → enrich (AI, `complete()`, one call per chunk, at most 6) → verify (no AI) → save
  (`data_source.structure_pack`, with the previous one beside it). Audit `source_structure_generated`
  with counts only. No tools, no file writes, no commands, and no row values anywhere.
- **FR-005**: The internal prompt is data, versioned in
  `backend/app/ai/prompts/structure_enrich.md`: return only JSON matching
  `cli/bizview_cli/schemas/structure.schema.json`; use only names present in the scan; never invent a
  table, field or path; mark metrics that are computable from the structure as suggestions; write
  the notes in Spanish, as the pack template does.
- **FR-006**: Everything works with `AI_PROVIDER=none` except the button (disabled, with the line
  that explains how to enable AI); the AI settings page names "Generar estructura con IA" as the
  feature that spends the provider and shows its internal prompt read-only.
- **FR-007**: i18n ES/EN; feature-010 look; the structure card takes the full width; mobile-first
  (the tab and its buttons stack, the tables scroll inside a bounded card).
- **FR-008**: Guide topics (033 format): "Estructura de una fuente", "Generar estructura con IA" and
  "Peticiones de muestra", with the routes the drift tests read.

### Key entities

- **Structure pack** (`data_source.structure_pack`, plus `structure_pack_prev`): the generated
  document of `structure.schema.json` — generator (mode, model, version), tables with fields, keys,
  date field, relations, `suggested_metrics`, `dropped` — or `{}` when no run has succeeded. Its
  previous value is kept so the tab can show what changed.
- **Scan** (not stored): describe output + sample shapes + discoverable endpoints, plus the
  scrubbed formats (an enum's values, a date's shape). What the AI may see, and what every name in
  the answer is checked against.
- **Sample request** (`source_sample_request`): belongs to a source; `name`, `method`, `path`,
  `params` (query, no secrets), free `notes`; stores the last measured shape summary so the scan and
  the download need not re-call the endpoint.
- **Column personal flag** (`source_structure_flag`): source, `schema`, `table`, `column`, `personal`
  — only the overrides; the heuristic covers the rest, and the AI's `personal` list is initial data.
- **Structure notes** (`data_source.notes`): the free text the super user writes into
  "Observaciones"; travels in `structure.md` and is merged into the pack's notes.

## Success criteria *(mandatory)*

### Measurable outcomes

- **SC-001**: For the demo PostgreSQL source and CoinMarketCap, Estructura renders in < 10 s and the
  downloaded `structure.md`/`.json` has every section the pack template asks for, with no
  placeholder left and no value from the source's rows.
- **SC-002**: 0 row values, credentials or hosts in the tab, the downloads, the scan sent to the
  provider or the saved pack (payload audit with seeded values).
- **SC-003**: 100 % of the tables, fields and relations the AI invents are absent from the saved pack
  and listed under `dropped` (adversarial fake-provider fixture).
- **SC-004**: With `AI_PROVIDER=none`, or after a failed run, the tab still renders and the download
  still produces a pack — the plain scan.
- **SC-005**: A super user who has never seen the feature goes from "Fuentes de datos" to a
  downloaded `structure.md` in three interactions (open the source, open Estructura, download), and
  to a generated pack in four (press "Generar estructura con IA").

## Assumptions

- The REST sample requests are the mechanism 043 WS-B called "saved sample requests".
- DeepSeek/OpenAI-compatible or Anthropic via the existing provider layer; `complete()` is
  enough (no tool calling).
- The installation's AI key is the same one the connection test uses: this feature adds no
  second provider configuration and no per-source key.
- Postgres row counts stay `reltuples` estimates (the describe already does this): the feature
  never runs `count(*)` over customer tables.

## Out of scope *(deferred, recorded 2026-11-03)*

- **US3 — sample requests become reusable**: drafts of
  `integrations/<id>/requests/<name>.yaml` inside "Descargar paquete de autoría", and SC-004 of
  the brief ("the live eval builds `Panorama cripto` from the pack"). The sample requests
  themselves are built here (FR-002) and are already downloadable in `structure.md`/`.json`; only
  their packaging as ready-made request files waits, decided with the owner.
- **"Descargar paquete de autoría"** (the starter pack zip with this source's structure). The
  backend image ships `cli/` and `backend/` only, so serving the pack means first making
  `PROMPT.md`, `REQUEST.md`, `request/` and the `sources/<nombre>/` skeleton CLI package data —
  a change to the authoring pack (043/049), not to the source page. Recorded as a clarification.
- **Per-schema describe and schema checkboxes** for catalogues over the 300-table cap: the single
  describe truncates and says so, which the tab and the download need; picking schemas one at a
  time is a follow-up.
- `bizview check-request --sample` (043 WS-C): not present in the CLI today; `bizview validate
  --describe`/`--live` is what reads a pack, and it now also reads the generated one.
- **The structure chat** (delivered by the first pass of this feature, removed by the convergence):
  conversational questions about a source's structure. The generator covers the need with one
  action and no interaction.

## Constitution check

- **III** (source of truth is external): the scan and the samples are read-only through the
  catalogue's credentials; `path` relative only; SSRF rules of `security/netguard` unchanged.
- **VIII** (AI optional and private): only structure and metadata are sent — the scan is describe
  output, response shapes and scrubbed formats; no row values, no credentials, no hosts. The AI
  writes a *description of the structure*, not an artifact of a project: nothing here authors a
  dashboard, and the pack is still what a human hands to the external AI. **PATCH: 3.2.2 → 3.2.3**
  (the sentence naming the structure chat now names AI-assisted structure generation — internal,
  non-interactive, metadata only).
- **IX** (spec-driven reporting): unchanged — projects still enter only through import; the pack is
  an input to that authoring, not a shortcut around it.
- **V** (fixed stack): no new component; the existing provider layer, `jsonschema` and the
  connectors do the work.
- **Constraints**: every user-visible text in ES and EN; no credentials returned or logged; the
  schemas in `cli/` stay the single source of the contract — `structure.schema.json` joins them and
  the pack ships the same file.

→ PASS with the VIII PATCH 3.2.3.

## Decisiones tomadas (modo autónomo)

- [specify] decision — delivery covers US1 and US2 only; US3 (request-file drafts) and its live
  eval wait for a follow-up spec, decided with the owner on 2026-11-03.
- [specify] decision — US1 keeps the sample requests (FR-002): they are what makes a REST
  connection's structure visible at all, and 043 WS-B lists them inside the structure pack.
- [specify] decision — the brief's `GET/POST /api/ai` is written as the real routes
  `GET /api/admin/ai` and `POST /api/admin/ai/test` (verified in `backend/app/api/ai.py`); the
  source's own route lives under it, `/api/sources/{name}/structure/generate` (was `.../chat`
  before the convergence).
- [analyze] decision — the edge case that asked for a per-schema, on-demand describe with schema
  checkboxes is out of scope: this delivery caps the single describe at 300 tables and states the
  truncation in the pack, which is what the tab and the download need. Recorded under Out of scope.
- [analyze] decision — the sample body cap is the connector's existing 1 MB, not the brief's 2 MB.
  *Superseded in part (2026-11-03): kept for the plain scan; the AI scan adds the OpenAPI document
  and the base listing, both capped at 1 MB each.*
- [specify] decision — the "fake provider" the brief asks for in tests is a test-level stand-in
  for `app.ai.get_provider` (the pattern `backend/tests/test_ai.py` already uses); the product
  gains no `fake` provider, so no test-only branch ships in the request path.
- [specify] decision — the constitution PATCH is 3.2.2, not 2.0.1: the file is at 3.2.1 today and
  earlier briefs (046, 048) already recorded the same numbering drift.
- [specify] decision — the chat stores question text only when a new setting says so
  (`AI_STRUCTURE_CHAT_STORE_QUESTIONS`, default off); token counts and audit are always recorded.
- [specify] decision — `structure.json` keeps the existing describe JSON as its body (the shape
  `bizview describe --json` already prints) plus a `pack` header with source name, kind, the
  BI-ready flag and the notes, so one generator serves the CLI, the API and the UI.
- [clarify] decision — "Descargar paquete de autoría" is deferred with US3: the backend image
  does not ship `pack/`, and turning the starter pack into CLI package data is a change to the
  authoring pack (043/049). "Descargar estructura" is delivered whole.
- [clarify] decision — the chat's refusal of data/action requests is a product-code guard that
  runs before the provider is called, plus the same rule in the system prompt: SC-005 needs 100 %
  on the fixtures, and a prompt alone cannot promise that.
- [implement] decision — the two settings are `AI_STRUCTURE_CHAT_DAILY_TOKENS` and
  `AI_STRUCTURE_CHAT_STORE_QUESTIONS`, not the brief's `AI_CHAT_*`: that prefix is the removed
  authoring agent's, and `scripts/gates/06-settings.sh` fails the build when it reappears (045).
- [converge] decision — the chat is **removed**, not kept beside the button: endpoint, history
  table, prompt, i18n, tests and its two settings. The owner read the chat on production and asked
  for one button; two AI surfaces on the same page would answer the same question twice.
- [converge] decision — the AI returns the JSON document only and **product code renders
  `structure.md`** from it, so the two files cannot disagree (the alternative — the AI writing the
  markdown — makes the pair drift by construction).
- [converge] decision — the previous pack is kept in `structure_pack_prev` so "Ver cambios" works
  on a later visit, not only right after a run.
- [converge] decision — the token ceiling is per run (`AI_STRUCTURE_TOKENS`, default 150 000), not
  per user per day: a generation is a deliberate action by a super user, and a run is bounded by its
  six chunks. A run that would exceed it stops chunking and says which schemas were not examined.
- [converge] decision — SOAP sources keep the plain scan: an operation's signature has no rows,
  fields, keys or relations to infer, so `POST .../structure/generate` answers 422 there and the tab
  says why.
- [converge] decision — "Descargar paquete de autoría" stays deferred (see Out of scope): the
  backend image does not ship `pack/`, and turning the starter pack into CLI package data is a
  change to the authoring pack (043/049), not to this tab.
- [converge] decision — the run is synchronous with a progress line and a Cancelar that stops
  waiting; the pipeline is bounded (one describe, samples already measured, at most six AI calls), so
  a job queue would be a component this feature does not need.
- [converge] decision — the OpenAPI probe tries three well-known paths with an 8-second timeout each
  and stops at the first that answers: a source that publishes nothing must not make the button wait.
- [converge] decision — the audit records the run's token count under `usage`, not as a top-level
  `tokens`: `app/services/audit.py` refuses a key that looks like a secret, and the count belongs
  with the other numbers anyway.
- [converge] decision — the search box stays (FR-001): it filters the generated tables by id, row
  description and field name, and the scan by table or column name.
- [clarify] decision — the structure is read lazily on first open of the tab and re-read on
  **Actualizar**; nothing polls, and the last rendered structure stays visible while a re-read is
  in flight or when it fails (the error is shown above it).
