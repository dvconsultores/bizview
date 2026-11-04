# Feature Specification: Per-source structure — "Descargar estructura" and a read-only structure chat for each connection

**Product**: Bizview · **Feature Branch**: `052-source-structure-chat` (worked on `main`) ·
**Created**: 2026-11-03 · **Status**: Draft

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
downloadable as the authoring pack expects, and (2) an optional **read-only chat scoped to that
source's structure** — it answers questions about tables, columns, types, keys, endpoints and
shapes, suggests which objects fit a request, and can draft the `sources/<name>/structure.md`
notes; it never reads rows, never writes files, never runs commands. AI stays optional (VIII):
without a provider the tab still shows and downloads the structure.

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

### User Story 2 — Ask the connection about itself (Priority: P1)

With AI configured, the Estructura tab has a chat panel on the right (side sheet, non-modal).
The super user asks "¿qué tablas tienen las facturas y cómo se relacionan con clientes?" or
"¿qué campos trae el endpoint de listados y cuál es la fecha?"; the assistant answers from the
structure only, names objects exactly as they appear, and can propose a draft of
`structure.md` notes or a `REQUEST.md` paragraph to paste into the authoring pack.

**Why this priority**: the owner asked for it by name ("each connection can have its own chat to
indicate structure"); it is the second half of the same tab, and it degrades to US1 when no
provider exists.

**Independent Test**: with a fake provider, questions about the CoinMarketCap structure get
answers that cite only objects present in the describe output; a question asking for data
("¿cuánto vendimos ayer?", "dame 5 filas") is refused with the standard line.

**Acceptance Scenarios**:

1. **Given** a question, **Then** the context sent to the provider is: the system prompt, the
   source's structure (as `structure.json`, truncated per schema with a note when over the
   token limit), the user's question and the last 10 turns — never credentials, hosts, row
   values; verified by a payload audit test.
2. **Given** an answer, **Then** every table/column/endpoint it mentions is validated against the
   structure; unknown names are flagged in the UI ("no existe en la fuente") so hallucinated
   objects never reach a spec.
3. **Given** "Resume esta fuente para el REQUEST.md" or "Redacta las observaciones de
   structure.md", **Then** the assistant returns text the user can copy or insert into the
   downloadable `structure.md` "Observaciones" section (saved on the source as notes; audited).
4. **Given** a request for data, writes or actions ("ejecuta", "borra", "muéstrame filas"),
   **Then** the chat refuses with one line and offers the structure instead; it has no tools
   except reading the already-fetched structure.
5. **Given** a provider error, **Then** the 035-style typed message (code, provider text,
   action link to Administración → IA) is shown; nothing else breaks.
6. **Given** usage, **Then** a per-user daily token cap for this chat (setting, default 100 k)
   and audit of counts only (question text stored only if the installation enables it).

---

### Edge Cases

- Huge PostgreSQL catalogues (1 000+ tables): one describe, capped at 300 tables and 200 columns
  per table, and the pack says it was truncated; reading per schema on demand and picking schemas
  with checkboxes is deferred (see Out of scope).
- Personal-data flags are heuristics: the super user can toggle a column's flag; the choice is
  saved and travels in the pack.
- The chat's structure context exceeds the model's window: send a per-schema index first and
  fetch the schema the question names (one internal round, no tools exposed to the model).
- Prompt injection in column names/comments: structure is data; the system prompt says so;
  object-name validation (US2/AC2) catches fabricated objects.
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

- **FR-001**: Source detail gets tabs `Conexión | Estructura`; Estructura renders the describe
  output per kind with search, personal flags (toggleable, persisted), row counts and date
  ranges (PostgreSQL), sample requests (REST/Supabase), operations (SOAP).
- **FR-002**: Sample requests stored per REST/Supabase source (`method`, `path`, `params`,
  `name`, `notes`); executed on demand through the stored credential; shape, `records`/`fields`
  suggestions and `timestamp_units` inferred by product code.
- **FR-003**: "Descargar estructura" → `structure.md` + `structure.json` in the pack format
  (single generator used by the UI, the API `GET /api/sources/{name}/structure?format=md|json`,
  and the CLI `bizview describe --pack`). The pack template in `pack/` is the format both must
  produce. The starter pack + structure zip ("Descargar paquete de autoría") is deferred (see
  Clarifications and Out of scope).
- **FR-004**: Structure chat: `POST /api/sources/{name}/chat` (super user; session-scoped history
  stored per user/source, 30 days); context = system prompt + structure + question + last 10
  turns; provider `complete()`; object-name validation of answers; refusal rules; typed errors;
  daily cap; audit of counts. No tools, no file writes, no commands, no data.
- **FR-005**: System prompt (data, versioned in `backend/app/ai/prompts/source_structure.md`):
  answer in the user's language; only objects in the structure; exact names in backticks; say
  "no está en la estructura" rather than guess; never request or produce row values; when asked,
  draft `structure.md` observations or a `REQUEST.md` paragraph in the pack's format.
- **FR-006**: Everything works with `AI_PROVIDER=none` except the chat panel (replaced by the
  enable hint); the Administración home has no AI card (043-G stays), the AI settings page
  remains under Administración → IA for provider/key/model and now lists "Chat de estructura"
  as the feature using it.
- **FR-007**: i18n ES/EN; feature-010 look; side sheet non-modal; mobile: tabs + bottom sheet.
- **FR-008**: Guide topics (033 format): "Estructura de una fuente", "Chat de estructura" and
  "Peticiones de muestra", with the routes/tiles the drift tests read.

### Key entities

- **Sample request** (`source_sample_request`): belongs to a source; `name`, `method`, `path`,
  `params` (query, no secrets), free `notes`; stores the last measured `shape` summary so the tab
  and the pack do not need to re-call the endpoint for a download.
- **Column personal flag** (`source_column_flag`): source, `schema`, `table`, `column`, `personal`
  (bool) — only the columns the super user overrode; a heuristic default covers the rest.
- **Structure notes** (`data_source.notes`): the free text the super user (or the chat, on
  request) writes into "Observaciones"; travels in `structure.md`.
- **Chat message** (`source_chat_message`): source, user, `role` (question/answer), `text` when
  the installation stores it, token counts always, `created_at`; purged after 30 days.
- **Chat usage** (`source_chat_usage`): per user, per source, per UTC day: questions and tokens
  spent, which is what the daily cap reads.

## Success criteria *(mandatory)*

### Measurable outcomes

- **SC-001**: For the demo PostgreSQL source and CoinMarketCap, Estructura renders in < 10 s and
  the downloaded `structure.md`/`.json` has every section the pack template asks for, with no
  placeholder left and no value from the source's rows.
- **SC-002**: 0 row values, credentials or hosts in the tab, the downloads, the chat context or
  the chat answers (payload audit with seeded values).
- **SC-003**: 100 % of answers that mention objects absent from the structure are flagged in the
  UI (adversarial fake-provider fixture).
- **SC-004**: Data requests to the chat are refused in 100 % of the fixture cases; the chat has
  no tool surface (asserted in the provider payload).
- **SC-005**: A super user who has never seen the feature can go from "Fuentes de datos" to a
  downloaded `structure.md` in three interactions (open the source, open Estructura, download).

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
- `bizview check-request --sample` (043 WS-C): not present in the CLI today and not needed by
  this delivery.

## Constitution check

- **III** (source of truth is external): describe and samples are read-only through the
  catalogue's credentials; `path` relative only; SSRF rules of `security/netguard` unchanged.
- **VIII** (AI optional and private): only structure and metadata are sent; no authoring by AI —
  the chat explains and drafts notes the *user* saves, it never writes artifacts. The principle
  lists the read-only help agent as the only AI surface; this chat joins it. **PATCH: 3.2.1 →
  3.2.2** (the brief says 2.0.1 because it was written against an older copy of the file, exactly
  as recorded for 046 and 048).
- **IX** (spec-driven reporting): unchanged — projects still enter only through import; nothing
  here authors a project.
- **V** (fixed stack): no new component; the existing provider layer and `httpx`/`psycopg`
  connectors do the work.
- **Constraints**: every user-visible text in ES and EN; no credentials returned or logged.

→ PASS with the VIII PATCH 3.2.2.

## Decisiones tomadas (modo autónomo)

- [specify] decision — delivery covers US1 and US2 only; US3 (request-file drafts) and its live
  eval wait for a follow-up spec, decided with the owner on 2026-11-03.
- [specify] decision — US1 keeps the sample requests (FR-002): they are what makes a REST
  connection's structure visible at all, and 043 WS-B lists them inside the structure pack.
- [specify] decision — the brief's `GET/POST /api/ai` is written as the real routes
  `GET /api/admin/ai` and `POST /api/admin/ai/test` (verified in `backend/app/api/ai.py`); the
  chat route is added under the source, `/api/sources/{name}/chat`.
- [analyze] decision — the edge case that asked for a per-schema, on-demand describe with schema
  checkboxes is out of scope: this delivery caps the single describe at 300 tables and states the
  truncation in the pack, which is what the tab and the download need. Recorded under Out of scope.
- [analyze] decision — the sample body cap is the connector's existing 1 MB, not the brief's 2 MB.
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
- [implement] decision — the chat history is read as the last 20 rows (ten question/answer turns)
  ordered by `created_at, id`: several turns can share a timestamp, and a shuffled history is worse
  than a short one.
- [clarify] decision — the structure is read lazily on first open of the tab and re-read on
  **Actualizar**; nothing polls, and the last rendered structure stays visible while a re-read is
  in flight or when it fails (the error is shown above it).
