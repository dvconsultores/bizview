# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **One `/speckit-specify` run can draft several specs**: a brief that covers an integration *and*
  its report produced only the first spec and then waited for a second request. The write scope now
  accepts the reserved number and the two after it (up to three specs per run, each with its
  `spec.md` and checklist), and the command prompt says to draft every piece of the brief in one go.
- **`/fix`: quick changes without a spec**: small, precise edits to an artifact that already exists
  (an `integration.yaml`, `report.yaml`, query or request) with the same validation, `check_query`
  and `run_preview` as the rest, but no spec, plan or tasks. It cannot create artifacts or specs and
  never touches the constitution.

- **The next command is offered when a run finishes**: a suggestion used to depend on the model
  calling `suggest_command`, so a finished command could leave the user with nowhere to go. The
  session payload now carries `next_step`, computed by the product from the finished run and the
  spec's stage (specify → plan → tasks → implement, plus clarify first when `spec.md` still has open
  clarifications), and the composer shows a **Siguiente: /speckit-…** chip that fills it. It only
  appears when idle with an empty composer, so it never competes with the Pipeline.

- **Autonomous runs can be requested in the brief**: saying "modo autónomo", "sin preguntar" or
  "decide tú y anota las suposiciones" now tells the assistant to choose the most reasonable
  default, record each assumption in the document it writes, and stop only for something
  irreversible or about privacy, credentials or scope. Documented in `docs/VIBE-REPORTING.md`,
  together with the two things that remain explicit user actions (commands never start each other;
  the Pipeline button asks once, and an unrequested personal column is never included silently).

- **Delete a conversation**: until now a chat could only be archived, so test conversations piled up
  in the history popover forever. The active list now has a delete button (with a confirmation),
  backed by `DELETE /api/assistant/sessions/{id}`, which removes the session, its messages, command
  runs, preview requests and attachment files, records an `assistant_session_deleted` audit event,
  and refuses while the conversation is working. Migration `0022` adds that audit kind.

- **Opt-in pipeline for a brief**: when the composer holds a `/speckit-specify` message, a
  **Pipeline** button appears next to Send. One press sends the brief and then `/speckit-plan`,
  `/speckit-tasks` and `/speckit-implement`, each only after the previous run reports `completed`,
  so a brief is taken from specification to *Listo para aplicar* without typing four messages. It
  is never automatic: it needs the button, the progress strip shows `Pipeline n/4`, **Detener**
  cancels the rest, and it stops by itself when a run waits for an answer, fails or is interrupted.

- **Automatic image updates**: the compose file runs `containrrr/watchtower:1.7.1` as
  `bizview-watchtower`. Every `WATCHTOWER_POLL_INTERVAL` seconds (default 300) it pulls a newer
  image of the `BIZVIEW_VERSION` tag and recreates the affected container with rolling restarts, so
  a publish from `deploy.sh` reaches the server without SSH. It is scoped with
  `WATCHTOWER_LABEL_ENABLE` and the `com.centurylinklabs.watchtower.enable` label on the three
  services, so it never touches another stack on a shared host. Both the shipped compose file and
  the one `install.sh` generates include it; remove the service to upgrade by hand instead.
  Documented in `README.md` and `docs/INSTALL.md` (section 8), including the difference between the
  `latest` tag (updates by itself) and a fixed version tag (updates only when edited).

- **Sign in with Google** (feature 027): an installation may now offer sign-in with Google as an
  additional identity for users who already exist. It is off by default (`GOOGLE_AUTH_ENABLED=false`)
  and configured with that installation's own OAuth client — `GOOGLE_CLIENT_ID`,
  `GOOGLE_CLIENT_SECRET`, optional `GOOGLE_ALLOWED_DOMAINS` and optional `GOOGLE_REDIRECT_URI` — so
  no installation depends on a secret held by the vendor. It is invite-only: a Google sign-in
  succeeds only when the verified email matches an existing, active user, and an unknown email gets
  the same failure as a wrong password, so the flow never creates or promotes a user and cannot be
  used to enumerate accounts. The flow is the authorization-code grant for a confidential client
  (`/api/auth/google/start`, `/api/auth/google/callback`), bound to the `state` cookie the start
  endpoint sets, with the ID token's claims validated by the
  backend, and it ends in the same `finish_sign_in()` as every other method — so session shape,
  lockout, audit and the second factor are not reimplemented. It never bypasses the two-step
  requirement that the `internet` profile imposes on administrators, who still enter (or enrol)
  their code. Password sign-in is unchanged and stays available whenever it is today, even with
  Google enabled, so an installation cannot be locked out through its identity provider; with the
  setting off, the sign-in screen and both endpoints behave exactly as before. Constitution
  principle V (**Auth**) is amended to **2.1.0** to list this optional federated identity provider,
  bounded by the four rules: off by default, per-installation OAuth client, invite-only, and the
  administrator second factor kept.

- **Shared-server deployment**: the compose file is now `bizview.yml` with the compose project
  name `bizview`, so its containers (`bizview-*`), network and volumes never collide with another
  stack on the same host. The published host ports default to **8081** (HTTP) and **8443**
  (HTTPS) because 80, 443 and 8080 may already be in use; the containers keep listening on 80 and
  443, and setting `HTTPS_PORT=443` makes the domain answer on the standard port when 443 is free.
  Caddy serves only the `Host` names listed in the new `CADDY_ALLOWED_HOSTS` (space-separated,
  421 otherwise) — when the setting is unset the rule is inactive, so generated installations that
  predate it keep working. Each service now also carries the `image:` it publishes
  (`${BIZVIEW_IMAGE_PREFIX}/bizview-backend` for the backend and the worker, `/bizview-web` for
  Caddy, at `${BIZVIEW_VERSION}`), next to its `build:`, so `up -d --build` builds from the tree and
  `pull` + `up -d` runs the published images. `deploy.sh` builds and pushes those two images to
  Docker Hub, reading `DOCKER_USERNAME` / `DOCKER_PASSWORD` from `.env` and sending the password to
  `docker login` on stdin. `.env.example` now describes an internet-facing install: a domain in
  `SITE_ADDRESS`, the domain in `CADDY_ALLOWED_HOSTS`, the standard-port guidance for
  `HTTPS_PORT`, `COOKIE_SECURE=true`, `SECURITY_PROFILE=internet`, and the image prefix and tag.
  `README.md` is rewritten as the public front page: what the product is, the capabilities with
  their specs, development quick start, both deployment flows, configuration, architecture and
  security.

- **Declarative layouts for dashboards and PDF** (feature 026): a report may now declare `layout`
  in `report.yaml`. `layout.web` fixes the dashboard's composition — a 12-column desktop grid with
  a `span` per component, and a declared order that is also the phone order, the tab order and the
  screen-reader order — and `layout.pdf` fixes the exported document: page size, orientation and
  margins in millimetres, an overflow policy for long tables and the blocks in their order. Every
  component and block binds to a view by its new optional `id`, and by id only — never by position
  and never by view type, so two views of the same type are no longer ambiguous — while a reference
  that resolves to nothing stops the version from applying with the fix hint to declare the id.
  The catalogue is closed: ten web components (`kpi`, `line`, `area`, `bar`, `pie`, `donut`,
  `table`, `text`, `filters`, `spacer`) and seven PDF blocks (`header`, `kpi_row`, `chart`,
  `table`, `text`, `page_break`, `footer`), with semantic colour roles and named fonts so a layout
  never carries a hex colour or an address, and a per-view summary and totals the engine derives
  once so both renderers print the same figures. The Asistente drafts both halves and renders them
  in the preview, `bizview validate` checks them with the same schema the backend uses (warnings,
  such as a chart that does not suit its view, are kept apart from errors), and the authoring guide
  documents every type with an example plus the two golden layouts CI keeps valid. `pdf.enabled`
  still gates the export at all: with a `layout.pdf` present, the legacy `pdf.orientation` and
  `pdf.views` are ignored and reported as a warning. Nothing changes for a report with no `layout` —
  the dashboard keeps its automatic composition and the PDF keeps the fixed template — so every
  existing definition validates and renders unchanged.

- **A left menu that folds away, and tighter gutters** (feature 025): **Contraer el menú** collapses
  the sidebar to an icon rail (the labels stay as tooltips and keep their accessible names, the
  choice is remembered by the browser), so a wide dashboard or the project editor gets the whole
  width back — 208 px become 65 px. The blank space around the content shrank too: the page no
  longer keeps a gutter between itself and the docked chat, the padding next to the sidebar and the
  top bar is a third of what it was, and the collapse control now sits with the menu instead of
  being pinned to the bottom of the screen. The seam between the page and the chat is now the IDE's
  own pane divider — the same `w-1.5` line as the one between the file explorer and the editor, with
  no shadow (the panel's halo used to spill ~10 px into the page and read as empty space) — and the
  content uses the whole remaining column instead of being capped and centered, so no canvas is left
  in front of the chat on a wide screen.

- **A new version says so, and projects are searchable** (feature 025): a tab that was left open —
  a dashboard on a wall screen, a laptop that never reloads — keeps running the bundle it loaded,
  and a self-hosted installation is updated in place, so the app now notices when the deployed
  `index.html` points at another build and shows a dismissible notice with **Recargar**. The check
  runs on a one-minute interval while the tab is visible, runs again the moment the tab comes back,
  is silent when the server cannot be reached, and never fires on a development server (whose entry
  never changes); it is a banner, not a modal, and saying **Ahora no** keeps it away for that tab.
  The projects list gained a search field (`Buscar proyectos`) that filters by name, identifier or
  description ignoring case and accents, states how many matches there are, and — when nothing
  matches — says so with the term and a way to clear it instead of showing the first-run empty
  state. The chat panel is also there in full screen now (it used to disappear with the chrome)
  and it owns the full height of its own column with the chrome visible too — starting it below the
  top bar left an empty band above the chat, because that bar only spans the content column; the
  panel is a side panel from the top of the viewport to the bottom, and the content keeps its
  column so the project's own controls stay reachable. The type scale is the reference's flat
  13 px: the tablet band of 14 px is gone (13 px from 640 px) and the sidebar's brand and
  navigation, which were hardcoded at 15 px and ignored the root scale, now follow it.

- **An image as the report brief** (feature 024): the composer takes a mockup — PNG, JPEG, WebP
  or GIF, up to `ATTACHMENTS_MAX_MB` (5 MB) and `ATTACHMENTS_MAX_PER_MESSAGE` (4) waiting at a
  time — so *"un reporte como este"* can carry the picture of the layout instead of a
  description. Images are stored outside the project folders (`ATTACHMENTS_DIR`, include it in
  backups), travel to the model as content parts of that one message with an untrusted-data
  label, and appear in the conversation as thumbnails. The first image send asks once per account
  for the notice that images go to the configured provider; `AI_VISION` (`auto`: true for
  Anthropic, false for OpenAI-compatible) refuses images with a clear message when the model
  cannot read them (and, when a provider refuses the picture, the text is still answered with the
  reason instead of an invented report), and the audit log and the security overview
  (Administración → Seguridad → *Bocetos del chat*) record the count, the size and a short hash,
  never the bytes or the original file name. The worker sweeps uploads that never became a message
  and purging a project removes its images; a new guide topic ("Boceto con una imagen") explains
  the flow. Migration `0020`.

- **Density and toolbar polish** (feature 024 polish; the tablet band was later aligned with the
  reference in 025): the type scale follows the reference app (Customer A) — 13 px on desktop, half a
  point below the old size — with 15 px on phones so the 16 px form controls stay proportional.
  Every "back" is now the shared control (an arrow and **Volver**, never the destination's name),
  the project header's actions became one flat tool strip of icon controls (36 px with a mouse,
  44 px under a finger) with the primary **Aplicar proyecto** standing out and the destructive one
  quiet (the header sticks below the top bar, so the actions are always reachable), the
  Administración tile for the workspace was removed (its address still works), the
  projects list uses up to four columns on wide screens, and the footer credits the publisher
  (`FOOTER_CREDIT`, `GlobalDV` by default).

- **One chat per screen** (feature 024 polish): the project page used to render the same
  conversation twice on a wide screen — a third resizable pane with its own toolbar *and* the
  docked assistant panel. The chat now lives in the docked panel from 1024 px (the same view the
  rest of the app uses) and stays a pane only on phones and tablets, where the panel cannot dock;
  a `?chat=` link still opens the right conversation, and the project header gained an **Asistente**
  toggle so the chat is reachable in full screen. The docked panel also stopped floating over the
  page: the shell now reserves its column, so the header's actions stay clickable while the chat is
  open. Escape keeps dismissing the innermost thing: it closes the `/` menu and leaves the composer
  as it was, and only closes the panel when nothing else is open.

- **A project on the whole screen, and a quieter composer** (feature 024 polish): the project page
  gains **Pantalla completa**, which hides the app chrome (sidebar, top bar, footer) and asks the
  browser for real full screen so the explorer, the editor and the chat use every pixel; the mode
  is a URL state (`?full=1`), leaving the control or full screen (Esc) brings the chrome back, and
  the control only appears where the browser exposes the Fullscreen API (as the report's TV mode
  already does). The chat's attach control is now a single clip icon — same accessible name and
  tooltip, no visible text — instead of a labelled pill.

- **BI projects** (feature 020): every conversation belongs to a project — a folder
  `projects/<slug>/` with `project.yaml`, numbered specs `specs/NNN-<name>/` (kind line
  `**Tipo**: fuente | integracion | reporte | distribucion`), integrations, reports and
  `distributions/<id>.yaml` (scheduled sends by role, share-link policy). New **Proyectos** page
  and a cloud editor (file explorer, CodeMirror editor, rendered Markdown, problems with file and
  line, live refresh while the assistant edits), per-file history with diff and restore, spec
  timeline, apply / withdraw a project (versions record the owner of every artifact), project
  zip download and import. Git workspaces accept the v2 layout (`projects/<slug>/`) next to the
  legacy one; `bizview init` creates v2 workspaces and `bizview project new` adds a project.
  Upgrading imports the applied workspace as project `principal` and each open draft as its own
  project. Settings `PROJECTS_DIR` and `PROJECT_MAX_MB`; the projects folder is part of backups.

- **Spec Kit commands in the chat** (feature 021): the assistant works only through
  `/speckit-constitution`, `/speckit-specify`, `/speckit-clarify`, `/speckit-plan`,
  `/speckit-tasks`, `/speckit-analyze`, `/speckit-checklist`, `/speckit-implement` and
  `/speckit-converge` (plus `/ayuda`), chosen from a `/` menu in the composer. Each command runs
  with its own prompt and only the tools and project files it may change (enforced by the
  server); plain messages can inspect and answer but never write, and suggest the right command
  with an **Insertar** button. Runs show as chips with status and files, wait for the user's
  answer (**Terminar**), ask before implementing an unapproved spec or with open checklists, and
  resume after an interruption. The chat answers only BI topics: clearly off-topic messages get a
  fixed refusal without calling the AI, and project documents and tool results reach the model
  as untrusted data. Migration `0019` (command runs, revisions linked to their run).

- **App guide in the chat** (feature 023): a maintained guide of 52 topics in Spanish and
  English (`backend/app/assistant/guide/`) covering every screen, Administración tile and
  command. The project chat answers questions about the app from it with the new
  `get_app_guide` tool, explains the current project with `get_project_overview` (stage and next
  command of each spec, decisions with file and line, sources, distributions — role names only,
  no personal data) and adds links that open the right screen, shown only when the viewer may
  open them. `/ayuda` lists the commands, examples and next steps without calling the AI;
  `/ayuda <tema>` answers one topic. New **Ayuda** page (`/ayuda`, sidebar and account menu) with
  search and the topics of each role (`GET /api/guide`, `GET /api/guide/topics/{id}`). Drift
  tests keep the guide's routes, tiles, commands and bold labels equal to the app; an opt-in
  live eval (`tests/live/test_guide_eval.py`) scores 50 reference questions.

- **English and Spanish** (feature 022): add full English support with resolution order
  `account language → browser Accept-Language → DEFAULT_LOCALE`; sign-in and public
  dashboards get their own switcher remembered on-device; per-recipient emails/PDFs,
  Telegram replies, and assistant answers follow the matched language or `DEFAULT_LOCALE`;
  `DEFAULT_LOCALE` defaults to `es`; CLI `--lang`/`BIZVIEW_LANG`; optional English report
  labels (`title_en`, `label_en`, `description_en`) used in UI, PDFs, emails, CSV exports,
  and search; numbers and dates follow the active language.
- Data-source catalogue (PostgreSQL, SOAP/SAP, REST with bearer, basic, API key, OAuth 2.0 client
  credentials) managed by the super user; credentials encrypted at rest (AES-256-GCM) and
  write-only; connection tests with read-only checks.
- Security option `SECURITY_PROFILE` (`private` allows HTTP, `internet` requires HTTPS everywhere),
  two-step sign-in (TOTP + recovery codes), per-address sign-in throttling, step-up password
  confirmation, admin network allow-list, destination address guard (SSRF/DNS rebinding), key
  rotation command, security overview page.

- **Vibe reporting** (feature 005): every integration and report is a GitHub Spec Kit spec in the
  customer's workspace. `bizview` CLI (`init`, `validate --write-lock`, `describe`) with a Spec Kit
  preset and extension (mandatory validation hook); declarative `integration.yaml` /
  `report.yaml` with read-only SQL checked by a parser; workspace validate / apply / rollback with
  step-up and audit; integration worker (`python -m app.worker`) with incremental windows, full
  rebuilds, contract checks, reconciliation and all-or-nothing loads into `ds_<integration>`
  schemas; generic report screen (`/r/<id>`: KPIs with comparison, trend, rankings, tables,
  filters, periods), PDF with the same figures, and an optional AI narrative that receives only the
  spec-declared aggregates; access tokens for structure-only source descriptions.
- Installer: `workspace/` folder, `worker` service, `--timezone` / `TIMEZONE`.
- **Faster PostgreSQL extraction** (feature 008): integrations with a PostgreSQL source stream
  the query result with COPY from the read-only source session straight into the typed staging
  table, with no per-value work in the application (benchmark: `scripts/bench_extract.py`). Same
  read-only session, column and type checks and time limit; sources that refuse COPY fall back to
  the row path automatically. The run history shows the path used. Constitution 1.7.0 describes
  the actual extraction stack (ConnectorX removed).
- **Sign in with Telegram** (feature 007, optional, off by default): the super user registers
  the installation's bot (credential encrypted and write-only, connection test); users link their
  own Telegram from their profile and sign in by approving in Telegram and choosing the code shown
  on screen. Same rules as password sign-in (limits per address, locked/inactive accounts,
  two-step for administrators on the `internet` profile). The worker reads bot updates by long
  polling (outbound HTTPS only). Migration `0006_telegram`.
- Connections to the BI database and to PostgreSQL sources use TCP keepalives and a send timeout,
  so a silently dropped network link fails within about a minute instead of hanging.
- QR codes (two-step setup, Telegram) now carry their own white background, so they scan in dark
  mode too.
- **Dark mode** (feature 006): every screen follows the device appearance by default; each user
  can choose «Sistema», «Claro» or «Oscuro» in Perfil → Apariencia or in the account menu, and the
  choice is saved on the account (`PATCH /api/me/preferences`, migration `0005_user_theme`). Both
  themes meet WCAG 2.1 AA contrast; PDF exports are unchanged. Screens use semantic colour tokens
  (`frontend/src/index.css`), enforced by a unit test.
- **Plus Jakarta Sans typeface** (the typeface of Customer A; replaces Ubuntu): vendored in the
  installation as one variable font per subset (latin, latin-ext; weights 200–800) and served
  from the app itself, with no external font service. SIL Open Font License 1.1. Desktop screens
  (from 1024 px) use a 14 px base size like Customer A; phones keep 16 px. One-time secrets are
  shown in monospace for unambiguous copying.
- **Spec archive** (feature 011): applying a workspace version stores the text of each
  integration and report `spec.md`, `plan.md` and `tasks.md` with the version (the bytes
  fingerprinted in the lock; a spec file that is not UTF-8 now fails validation);
  Administración → Espacio de trabajo lists the active version's specs (type, title, status)
  and "Ver" shows them as plain text in a view; versions applied earlier show "Texto no
  disponible para esta versión"; new super-user endpoint `GET /api/workspace/specs?key=`, and
  `GET /api/workspace` lists spec metadata per version. No migration (JSONB content).
- **Integration controls** (feature 013): super users can pause and resume each integration
  from Administración → Integraciones; a paused integration is not scheduled but manual runs
  are still allowed. A run in progress can be stopped ("Detener") — the worker checks the stop
  request at most every 2 s, records the run as stopped ("Detenida") with who requested it,
  and publishes no data from it. The frequency shown comes from the spec or an override
  (presets with Spanish words or a custom cron expression, validated at most once every 5
  minutes), and the full-rebuild schedule can be overridden separately; scheduled runs can be
  restricted to an allowed-hours window (overnight windows allowed, installation time zone),
  while manual runs ignore pause and window. "Usar la programación del spec" restores the spec
  schedule in one action. The worker applies changes within a minute without restart. Every
  change is audited with before/after values. New endpoints
  `PUT /api/integrations/{id}/control` and `POST /api/integrations/{id}/runs/{run_id}/stop`;
  `GET /api/integrations` now includes `control` and `running_run_id`. Migration
  `0008_integration_control` adds table `integration_control`, run columns
  `stop_requested_at`/`stop_requested_by` and run status `stopped`. Existing integrations keep
  the spec schedule as the default.
- **Dashboard auto-refresh and TV mode** (feature 015): new per-report, per-device
  "Actualización automática" control in the parameters panel with Desactivada / Al llegar
  datos nuevos / Cada 1, 5, 15, 60 min. Data mode polls
  `GET /api/reports/{id}/version` every 60 s and reloads only when the version changes, with
  no report recomputation for unchanged data; refreshes keep applied parameters, pending
  edits and scroll position, pause while the tab is hidden, and show an offline notice on
  network failure. "Modo TV" is reachable via a `tv=1` link or button, hides the app chrome,
  shows full-screen report content with large figures, enables auto-refresh in data mode
  without persisting it, and exits via Esc or "Salir del modo TV", preserving the existing
  sign-in and access rules. No migration.
- **Vibe-reporting chat** (feature 014, needs AI configured): Administración → Asistente lets
  the super user describe an integration or report in a conversation; the AI proposes Spec Kit
  files (specs, `integration.yaml`, `report.yaml`, queries) that are validated with the same
  rules as `bizview validate` against the active version. The AI sees only source structure
  (sanitised descriptions, never row values or credentials). "Vista previa" runs draft
  integrations into temporary `preview_<session>` schemas (never the published datasets, no run
  history) and shows draft reports to the super user only; previews expire after 24 h.
  "Aplicar" (step-up password) creates a workspace version through the same path as a Git apply,
  with audit; rollback works as usual. Conversations, messages and drafts are stored in the
  database with a per-conversation token budget (`AI_CHAT_TOKEN_BUDGET`). The draft is shown as
  cards (Spec de integración, Integración, Spec de reporte, Reporte); the preview outcome (status,
  row counts, errors with values removed) appears in the conversation and is passed to the AI so
  it can fix the draft. An applied conversation links to the version it created and accepts new
  requests, which start a new draft on the active version. Applies are serialised: if another
  version was applied meanwhile, the draft is validated again and the user is told. The menu
  item only appears when AI is configured. On desktop a sparkle button in the top bar opens the
  assistant as a panel docked at the right (Customer A style) that can be expanded to the whole
  content area, collapsed or closed (Esc); it remembers its state and conversation per device.
  On phones the button opens the Asistente page. "Descargar (zip)" in Espacio de trabajo
  (`GET /api/workspace/versions/{id}/export.zip`) downloads a version's files to commit them to
  Git. Migration `0009_assistant` adds `assistant_session`, `assistant_message` and
  `assistant_preview_request`.

- **Supabase data sources** (feature 016): new source type "Supabase" with the project URL
  (`SUPABASE_URL`) and service key (`SUPABASE_SERVICE_KEY`, encrypted and write-only). BizView
  reads the project's REST API (`/rest/v1/`) adding the `apikey` header and Bearer token,
  only with GET requests; the connection test, the structure description (tables, columns,
  types and keys from the API's own description) and integration request files work as for
  REST sources. Migration `0010_supabase_source`.

- **Agentic vibe-reporting chat** (feature 017): the assistant reads an authoring guide served from
  the CLI (the validator's own JSON Schemas, workspace rules, preset templates and complete golden
  examples, `bizview` CLI 0.2.0); validation returns every problem in one pass with file, JSON path,
  expected shape and a suggested fix (shown in the chat banner and the draft cards); `edit_draft` /
  `read_draft` change single files instead of resending the draft and schema-probing drafts are
  answered with the schema instead of being stored; metadata-only origin tools `profile_source` (row
  count, null ratio, distinct count, date min/max) and `check_query` (read-only, `LIMIT 0`, output
  columns or a redacted error) and personal-data flags on source columns (excluded by default, an
  explicit user request plus a `**Datos personales**:` line in the integration spec to keep one);
  the first draft can create the workspace manifest when no version exists yet and pre-011 versions
  report missing spec documents as fixable problems; the agent runs the preview itself and a
  ReportLab "PDF de vista previa" can be downloaded (report.yaml `pdf.orientation` and `pdf.views`);
  "Aplicar" is enabled only when the draft is "Listo para aplicar" (valid, every query checked,
  latest preview succeeded, keys/incremental/checks/PDF present) and apply re-checks the queries;
  working notes per conversation replace old tool results in the history; per-message round limit
  with a progress message; 80% budget warning and automatic, audited budget extension up to
  `AI_CHAT_BUDGET_MAX` (the manual "Ampliar presupuesto" was removed); DeepSeek-safe OpenAI-compatible tool loop (reasoning content, one repair round for
  invalid tool arguments, one retry on rate limit, context-too-long compaction). New settings
  `AI_CHAT_MAX_ROUNDS`, `AI_CHAT_BUDGET_STEP`, `AI_CHAT_BUDGET_MAX`, `AI_CHAT_MAX_PREVIEWS`,
  `AI_TOOL_TIMEOUT_SECONDS`; new endpoints `POST /api/assistant/sessions/{id}/budget` and
  `POST /api/assistant/sessions/{id}/preview/report/{rid}/pdf`; migration `0011_agentic_assistant`
  adds `working_state`, `query_checks` and `stats` to `assistant_session` and the audit kind
  `assistant_budget_extended`. Each agent round commits as it finishes and a conversation is
  marked busy while a turn runs (migration `0012_assistant_busy`, setting
  `AI_CHAT_BUSY_STALE_SECONDS`): a second message, preview, apply, archive or budget extension
  gets 409 `assistant_busy`, and a stale mark is reclaimed with an interruption notice.
  Cached prompt tokens count `AI_CHAT_CACHED_TOKEN_WEIGHT` (default 0.1) against the budget
  (raw input/cached/output totals kept in the stats) and the default `AI_CHAT_TOKEN_BUDGET` is
  400000; the per-round "## Estado" suffix is bounded (compact notes for inspected tables, at
  most ~12 000 characters); `check_query` on a request whose date window is empty re-checks the
  shape on the newest record without the date filter; the assistant header shows a session
  indicator (Trabajando / Lista / Sin presupuesto, model, budget used).
  Opt-in live eval `backend/tests/live/test_agent_eval.py`
  (`AI_LIVE_TESTS=1`).
- **Dashboard sharing** (feature 018, off by default): administrators press **Compartir** on a
  dashboard and create read-only links valid for 1–90 days (default 7; chips 1/7/30/90) with an
  optional note; the link is shown once with a copy button. **Enlaces activos** lists creator,
  expiry, visits, last visit and **Revocar**, with at most 20 active links per dashboard; tokens are
  256-bit and stored only as a hash. The public page `/s/<token>` sits outside the signed-in app and
  shows the dashboard read-only (period, comparison and filters, PDF download, no AI summary, no
  navigation) under "Vista compartida · vence el …"; expired, revoked or unknown tokens get one
  neutral page. `/api/shared/{token}` is throttled per address and sends `X-Robots-Tag: noindex,
  nofollow`, `Cache-Control: no-store` and `Referrer-Policy: no-referrer`; turning links off stops
  every link at once. **Enviar por correo** (any user who can open the dashboard, when email is
  enabled) sends the current period and filters as a PDF (same rendering as the download, up to 10
  MB) to up to 20 recipients — installation users (access re-checked at send time) and external
  addresses within the allowed domains — with an optional subject and message; administrators can
  add a link valid N days; interactive email links count toward the 20 per dashboard while queued or
  active, scheduled sends reuse one uncounted link per subscription, **Enlaces activos** shows the
  origin and allows revoking any link, and PDFs over 10 MB go link-only instead of being attached.
  **Envíos** lists each send with per-recipient status and errors. **Envíos programados**
  (administrators) sends daily, weekly or monthly at an hour of the installation time zone with a
  period preset, and can be paused, resumed, edited or deleted; it is created exactly once even with
  two workers. The worker delivers queued email every 15 s, checks schedules every minute, retries
  failed deliveries after 1, 5 and 15 minutes (3 attempts) and sanitizes errors. Email and shared
  links are configured only in the installation environment, like the AI settings (owner
  amendment 2026-10-07): `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_SECURITY` (`starttls` |
  `ssl` | `none`; default `ssl` on port 465, else `starttls`; `none` refused at startup on the
  `internet` profile), `SMTP_USER`, `SMTP_PASSWORD` (never returned, shown or logged; ASCII only),
  `SMTP_FROM`, `SMTP_FROM_NAME`, `EMAIL_ALLOWED_DOMAINS` (comma-separated) and
  `SHARE_LINKS_ENABLED` (default `false`); email is on when `SMTP_HOST` and `SMTP_FROM` are set.
  There is no email option in Administración; the setup is checked with
  `python -m app.cli mail-test <address>`, and no SMTP secret is stored in the database. There is
  no email endpoint in the API: the former super-user `GET /api/admin/mail` and
  `POST /api/admin/mail/test` were removed (owner decision 2026-10-07); the CLI mail-test still
  records the `email_test_sent` audit event. Endpoints
  `/api/dashboards/{code}/links`, `/api/dashboards/{code}/email`,
  `/api/dashboards/{code}/email/recipients` and `/api/dashboards/{code}/subscriptions`. Migrations
  `0013_dashboard_sharing` (tables `share_link`, `email_subscription`, `email_send`,
  `email_delivery`; audit kinds `share_link_created`, `share_link_revoked`, `sharing_toggled`,
  `email_settings_updated`, `email_test_sent`, `email_sent`,
  `email_subscription_created`/`_updated`/`_deleted`) and `0014_email_settings_env` (drops the
  `email_settings` table that 0013 created; downgrade recreates it empty). Stdlib SMTP, no new
  component. E2E `frontend/tests/e2e/sharing.spec.ts` (test hooks `/api/test/mail*` and
  `/api/test/settings`, which override the email settings in memory).

- **Agent map** (feature 017 Phases 15–16, 2026-10-05/07): new super-user endpoint
  `GET /api/assistant/sessions/{id}/activity` → `{busy, model, run, rounds, background, runs}`
  (current or last run: status running/done/stopped/error/budget/limit/ready, round, tokens and
  the tool in progress, written in its own short transaction so pollers see it mid-round; one
  node per tool call with label, status running/ok/error and duration; background preview; the
  last 10 runs kept in the conversation stats), light enough to poll every 2 s. "Mapa del agente"
  is a floating, non-modal card over the chat (panel and page; × or Esc closes, focus returns):
  agent node (status, title, model · tokens) joined to one node per tool call of the current run
  (click to expand details) and "N tareas en segundo plano"; opened from the session indicator,
  a header button or the "● N herramientas" pill in the composer; full width on phones; polls
  only while open and the agent works.
- `AI_CHAT_MAX_TOKENS` (default 16000, 1024–64000): longest assistant answer per round, so a
  complete draft (specs, YAML, SQL) fits in one reply; documented in `.env.example` and
  `docs/INSTALL.md`.
- **Direct-source reports** (feature 019): a report.yaml can declare `direct` instead of
  `uses` and read a prepared table live (source `bi`, or a PostgreSQL catalogue source
  with "Permitir reportes directos" turned on — step-up confirmation and audit; other
  source kinds are refused). All existing report features — views, filters, periods,
  PDF, shared links, email — work unchanged. Safety: read-only sessions, statement
  deadline `timeout_seconds`, row cap `max_rows`, per-source concurrency with
  single-flight, result cache per `cache_seconds` bucket in `report_cache`, stale
  fallback ≤ 24 h, product-table deny-list plus view dependency walk, structure check
  at validate/apply, five required spec lines, big-table rule requiring an index or
  partitioning by the date column, footer "Datos en vivo · …", workspace page shows
  mode, source and tables, and "Estructura cambiada", security overview of 24 h direct
  reads (`GET /api/security` → `direct_reads`, `GET /api/workspace` →
  `report_details`) and audit. Tooling: CLI 0.3.0
  `bizview validate --describe NAME=FILE | --live`, golden pack `example-direct`;
  agent tools `list_sources` (direct flag), `describe_source` and `profile_source` on
  `bi`, `check_query` on a report, live preview with PDF, readiness. Migration
  `0015_direct_reports` (column `data_source.direct_reports`, table `direct_read_log`
  kept 7 days, audit kind `source_direct_reports_changed`); settings
  `DIRECT_REPORTS_BI`, `DIRECT_REPORT_CONCURRENCY`, `DIRECT_REPORT_WARN_ROWS`,
  `DIRECT_BI_ROLE`; E2E `frontend/tests/e2e/direct-report.spec.ts` (test hooks
  `/api/test/direct/seed` and `/reset`), opt-in `backend/tests/test_direct_perf.py`
  (marker `slow`, `BIZVIEW_SLOW_TESTS=1`).

- Benchmarks (opt-in developer tools, not part of CI): `backend/scripts/bench_rollup.py`
  measures the daily rollup of a materialized report — full build, the 7-day refresh after an
  incremental change, and cold views per view type on the rollup route vs the raw path — in its
  own throwaway `app_test_bench_*` schema (`BENCH_ROWS`, `BENCH_DIMS`, `BENCH_RUNS`); results and
  the machine are in `specs/005-vibe-reporting/research.md` (R11). `backend/scripts/bench_extract.py`
  takes `BENCH_DATABASE_URL` for both sides (default `DATABASE_URL_BI`, never printed) so the
  extraction comparison can run with origin and destination on the same host or LAN, and
  `BENCH_BATCH_ROWS` to measure transform batch sizes; it also fails fast when a path dies before
  reporting. Both tools were run on a same-host local PostgreSQL: SC-001 met (6.0× at 1 M rows) and
  SC-A02 met at 50 M rows; the SC-A01 transform overhead stays open as T042 in feature 005.

### Changed

- **An inserted command is sent only with the Send button**: Enter in the composer used to submit
  whatever it held, so clicking a suggestion (or the new "Siguiente" chip) and then pressing Enter
  put the command in the chat without an explicit send. Enter is now ignored while the text came
  from a button; typing anything — or clicking Send — restores the usual behaviour.

- **Stable container names**: `backend`, `worker` and `caddy` now declare `container_name`
  (`bizview-backend`, `bizview-worker`, `bizview-caddy`), so they no longer carry Compose's `-1`
  replica suffix. `bizview-watchtower` already had one.

- **Validation problems can be put aside, and re-checked on demand**: the problems panel gained a
  **Volver a comprobar** action that recomputes validation without waiting for a file change, and
  each problem has a dismiss button. A dismissed problem is hidden for that project in this browser
  and listed as "N descartados" with **Mostrar** to bring them back; nothing is deleted and the
  server still refuses to apply a project whose validation fails, so dismissing cannot bypass the
  checks.

- **The installer writes the same shape as the repository**: `deploy/install.sh` now generates
  `bizview.yml` (with `COMPOSE_FILE=bizview.yml` in `.env`, so plain `docker compose up -d` works)
  and no longer creates or mounts `branding/` or `workspace/` — the logo ships inside the image,
  and BI projects live in `projects/`. It also passes `CADDY_ALLOWED_HOSTS` and the `CADDY_TLS`
  settings, defaulting the allow-list to the site's own domain.
- **Certificate source is selectable** (`CADDY_TLS`): `auto` keeps automatic HTTPS; `internal`
  serves Caddy's local CA for a proxy in front that does not verify the origin certificate; `file`
  serves a pair you supply in `CADDY_TLS_DIR` (e.g. a Cloudflare Origin CA certificate). The last
  two issue nothing over the network, so an installation whose host ports 80 and 443 belong to
  other services can still serve HTTPS on a published port such as 8443. `README.md` and
  `docs/INSTALL.md` document the three cases, including the Cloudflare **525** that a proxied
  hostname shows while the origin is unreachable on 443.
- **Transform stage speed, memory and batch size** (005 amendment, 2026-10-12): the
  declared-type check of a text batch now reads the materialised typed frame instead of
  re-evaluating every cast (1 M rows: `transform_ms` 654 ms → 287 ms at 200 000 rows per batch), and
  a batch read from COPY text that contains no backslash skips the unescape pass (the splitter
  decides per batch). The default `transform.batch_rows` is **20 000**, down from 200 000: five
  same-host 1 M-row runs give a median +28.6 % extraction time over the COPY path (22.7–36.8 %)
  and ~210 MB peak, against +69 % and 391 MB at the old default. SC-A01 holds at the median; the
  numbers and the spread are in `specs/008-fast-pg-extraction/research.md`.
- **Assistant discovery guard, chat timeout and conversation names** (feature 017 Phase 14,
  2026-10-05): repeated discovery calls on the same normalised target within a run
  (`describe_source`, `profile_source`, `get_authoring_guide`, `check_query`; "tabla", "/tabla"
  and "public.tabla" are one Supabase/REST table) answer the earlier result marked
  `ya_consultado` without contacting the source, `refresh` is honoured once per target per run,
  and after `AI_AGENT_DISCOVERY_LIMIT` (default 15, 3–100) discovery calls without a draft only
  the draft tools are offered; `check_query` with SQL on a non-PostgreSQL source explains how to
  check a request file instead and `profile_source` on Supabase/REST says it only counts rows;
  assistant chat calls use `AI_CHAT_TIMEOUT_SECONDS` (default 180, 10–600; `AI_TIMEOUT_SECONDS`
  keeps the other AI calls) with one retry per run before stopping with a progress summary;
  new `PATCH /api/assistant/sessions/{id}` `{title}` (1–120 characters, trimmed; allowed while
  the assistant works) to rename a conversation.
- **Autonomous assistant runs** (feature 017, 2026-10-05): POST messages returns 202 and the run
  continues in a background thread with its own DB session; `AI_AGENT_MAX_CONCURRENT` (default 4,
  409 `assistant_capacity`); `AI_CHAT_MAX_ROUNDS` default 60 (max 200) per run; new stop
  conditions: "Listo para aplicar", two identical failing tool calls, progress message after
  rounds; automatic budget extension audited with `auto: true`; budget route no longer requires
  step-up; new `POST /api/assistant/sessions/{id}/stop` ("Detener", 409 `not_running`);
  unexpected errors post a message and keep saved rounds.
- **Assistant convergence** (feature 017 Phase 17, 2026-10-07): an unexpected error from a run
  that was stopped ("Detener") is no longer posted, so it never lands in a newer run of the same
  conversation; the Anthropic provider retries one rate limit during the agent loop after the
  provider's `Retry-After` (capped at 10 s, else 2 s; timeouts are not retried by the provider);
  re-checking a query after editing it back to an earlier version (A→B→A) runs the check again
  so the draft can reach "Listo para aplicar"; `bizview validate` reports `pdf.views` indexes
  beyond the report's views (`/pdf/views/<i>`, with the valid indexes as the fix).
- **Faster with a remote BI database** (each round trip ~200 ms): read requests skip
  BEGIN/COMMIT; pooled connections are pinged only after 60 s idle; report queries go in one
  batched round trip; the active workspace version and parsed report definitions are kept in
  memory (`ACTIVE_VERSION_CACHE_SECONDS`, default 5 s); the data version and the report cache are
  read together; the integrations list no longer runs two queries per integration; a larger
  connection pool stays open and 8 connections are opened at start (`DB_POOL_SIZE`,
  `DB_POOL_OVERFLOW`, `DB_POOL_WARM`; a new connection costs ~1.4 s); the home page counters come
  from one request and one query (`GET /api/admin/overview`). Measured: home counters 3.3 s →
  0.7 s, `/api/me` 0.9 s → 0.3 s, a cached report 1.5 s → 0.6 s.

- **Home page (Inicio)**: the greeting banner, then counters — dashboards for everyone, users
  for administrators, data sources and integrations for the super user (moved from
  Administración) — then the user's favorite (★) and recently opened dashboards and a link to
  every dashboard. Favorites and recents are remembered per user and device (browser storage),
  no database change.
- **Tableros menu**: new sidebar and bottom-bar item "Tableros" (`/tableros`) listing every
  dashboard the user can open, as compact cards or as a table (Tablero, Descripción, Estado,
  favorite star), with search by name or description (ignoring case and accents). Every sub-page has a "Volver" button (Usuarios, Fuentes,
  Auditoría, Asistente, Borrador and two-step setup were missing it).

- **Sidebar**: only Inicio, Administración and Perfil; every admin section (Usuarios, Fuentes,
  Espacio de trabajo, Integraciones, Tokens, Seguridad, Auditoría, IA) is opened from the
  Administración page, and the Administración item stays highlighted on all of them. The
  assistant opens only from the top-bar button.

- `DATABASE_URL_ORIGIN` is no longer used; it is imported once as an encrypted data source.
- Dashboards created from workspace reports open at `/r/<id>`; the seeded "Ventas" placeholder is
  adopted by a workspace report with the same id.
- The installation folder's `queries/` is replaced by `workspace/`.
- **Confirmations and results are screens instead of pop-ups** (feature 009): the page stays
  underneath with its typed input preserved; the back button, phone back gesture, and Esc cancel;
  the step-up password confirmation is also a screen and resumes the interrupted action once;
  one-time secrets are discarded when the screen closes.
- **Wider pages on large screens**: content grows up to 1536 px beside the sidebar, and short
  paired form fields flow into two columns from 1280 px. Phone layouts are unchanged.
- **Nuevo diseño (estilo Cliente A)** (feature 010): steel-teal brand colour; full-height
  sidebar with a gradient logo block and a filled active item, white top bar with theme toggle
  and account menu; header cards with large bold titles; welcome banner on the home page and
  hub cards; summary tiles on Administración and report KPIs; filled form inputs with required
  marks; soft status pills, code chips and breadcrumbs with a "Volver" button; light and dark
  themes, phone layouts and accessible names unchanged.
- **Report parameters** (feature 012): "Filtros y controles" panel on desktop (collapsible and
  remembered) and a "Filtros" view on phones; changes apply exactly once via "Aplicar filtros",
  "Limpiar todo", or chip removal; searchable multi-value filters (repeated `filter.<id>` params, up
  to 50 values, `IN` with bound values, backwards-compatible with old links; the filter values
  endpoint accepts `q` and returns `truncated`); context block with period, comparison, freshness,
  and removable chips; PDF/CSV export section and per-table "Descargar CSV" (UTF-8 BOM, `;`, dot
  decimals, ISO dates).

### Removed

- Dead frontend code: the orphan `AssistantPage` (the `admin/asistente` route only redirected to
  `/proyectos`), the unused `todayLong` formatter, the unused `ShareLinkStatus` type, the unused
  `countActiveFilters` helper, and the `setMfaEnrollmentHandler` hook that nothing registered
  (`RequireAuth` already sends administrators who must enrol a second factor to the setup screen).
- The planned in-app assistant and feature 001's built-in sales ETL (superseded by feature 005).
- Caddy no longer trusts `X-Forwarded-For` from private networks by default (`TRUSTED_PROXIES`).

### Fixed

- **A leftover folder no longer poisons a new project**: the database and the project folders live on
  different hosts, so deleting a project's rows while its tree stays on disk (or reusing a database
  with a fresh server) made the next project with the same slug adopt the old files — the editor then
  reported `project.yaml cambió desde que lo abriste (external…)` for files the new project never
  wrote. The old tree is now moved to `.papelera` before the project is created (nothing is lost, the
  audit event records it), so the new project always starts empty.

- **A suggestion cannot carry a whole brief any more**: `suggest_command` rejected nothing, so the
  model packed the entire specification into `arguments`. The chat then showed an unreadable
  paragraph ("Sugirió /speckit-specify Integración de facturación…" with dozens of columns) and the
  turn was spent repeating the same suggestion. Arguments are now capped at 160 characters — the
  tool refuses more instead of truncating silently — the prompt says the detail belongs in the reply
  text and that one suggestion per answer is enough, and the activity pill and the insert button
  clamp to a single line with the full text on hover. Suggesting the **same** command twice in one
  answer is now refused: the button is already on screen, and repeating the call only kept the turn
  spinning until the user pressed Detener. The **Pipeline** button now asks first ("Se enviarán 4
  mensajes… ¿Ejecutar?"), so it is impossible to launch four commands with one stray tap, and it
  survives a question: when a command stops to ask, the chain pauses instead of dying and continues
  by itself once the answer makes that command finish.

- **The shipped templates could not start an internet installation**: `.env.example` and the
  installer both set `SECURITY_PROFILE=internet` while leaving `DIRECT_REPORTS_BI` at its default
  `true` with no `DIRECT_BI_ROLE`, which the startup guard refuses — the backend exits with
  `ProfileError` before serving. The example now ships `DIRECT_REPORTS_BI=false`, the installer
  writes `false` whenever the profile resolves to `internet` and `true` otherwise, and the guard's
  message names the second way out.
- **Projects page and Safari 14** (019–023 final suites, 2026-10-11): the status bar (validation,
  **Listo para aplicar**, save state) sits under every pane, so phones see readiness without
  opening the editor; the explorer renames with F2 and deletes with Delete (the tree holds only
  tree items) and its empty-folder note and the diff line numbers meet contrast; a project's
  preview offers **PDF de vista previa** per report again; English screens no longer show
  "activos", "conectadas" or "fuentes" counts in Spanish; Audit has labels for the project
  events; `Object.hasOwn` and `Array#at` are polyfilled for Safari/iOS 14 (react-markdown and
  the resizable panes use them). The report context cache key carries the version checksum on
  every read path. E2E runs keep their BI projects in a temporary folder.
- **Progress message after the round limit** (features 022/023, 2026-10-12): the closing progress
  message keeps the "type *continue*" hint in the account's language — the guard that avoids
  repeating it matched the word "continue" inside the "Next:" label ("continue with the draft")
  and dropped the hint for English accounts.

## [0.1.0] - 2026-09-29

### Added

- Sign-in with email and password, server-side sessions, lockout after 5 failed attempts.
- Super user created from `SUPER_USER_EMAIL` / `SUPER_USER_PASSWORD` on first start, with a
  recovery command.
- Administration: create users, edit, activate/deactivate, reset passwords, grant dashboards;
  audit log for the super user.
- Home page with the dashboards available to each user; mobile-first blue interface in Spanish,
  tested on Chromium, Firefox, and WebKit at 320 and 375 px.
- Optional AI provider layer: Claude (Anthropic) or any OpenAI-compatible endpoint, off by
  default, with a status page and connection test for the super user.
- Distribution: `deploy/install.sh` creates a customer installation that runs published images;
  multi-arch images on GHCR; CI checks and tagged releases on GitHub Actions.
- Open source under AGPL-3.0-or-later, with version and source-code link on every page.
