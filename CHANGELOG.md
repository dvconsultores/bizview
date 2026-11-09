# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Fixed

- **Five defects a 360 px phone exposed (feature 062)**. All five had been marked done by an earlier
  feature, and all five were found by measuring rather than by reading classes:
  **the sign-in providers** are one full-width 48 px row each again, at every width — 059 had put
  Google and Telegram side by side with abbreviated labels on a phone, and the owner reversed it;
  **the filters sheet** reserves its footer's *measured* height instead of a 24 px constant, so the
  last control can be scrolled clear of a ~70 px bar (059's own T003 asked for exactly this);
  **a maximized card's title** is the card's own words — component title, the view's title, a KPI's
  metric label, a text's first words, the report's title — and never `Ampliar «k_ventas»`, the
  component id 056b fell back to; the header is a two-row grid (title + 44 px actions, then the
  period/filter chips) so a long title stays on one line instead of printing one letter per line;
  **the pie/donut** draws with the width its card measured instead of a hard-coded 240 px, and stops
  reading `window.innerHeight` when maximized, so a phone shows a ring at all (200 px in the card,
  300 px maximized) with the legend under it; and **the source form's actions** scroll with the form
  instead of floating 80 px above the bottom on a blurred bar that covered the fields it saves, in
  the order **Guardar**, **Probar conexión**, **Eliminar fuente**. A grep gate refuses
  `sticky bottom-20` and `writing-mode` in `frontend/src` so the two patterns cannot return.
  The sheet's controls are also **wider on a phone**: the body's gutter is 12 px instead of 16, and
  **Período** and **Comparar con** share their row again — the 160 px column floor needed 332 px,
  three more than a 360 px phone has, so the pair had been stacking. The report's own row of
  **Filtros · Parámetros · ⋯** fills the line too: it was a content-sized flex item of 203 px inside
  336 px, so the three controls hugged the left edge and left a third of the row empty; they now share
  it as three equal targets.

### Added

- **The public site the product never had (feature 032)**. It lives in its own private repository,
  `dvconsultores/bizview-site`, because prices and contacts are not part of the AGPL product; what is
  here is the feature's spec. Two pre-rendered React documents —
  `/` in Spanish and `/en/` in English — in Tailwind, one stylesheet, and one deferred bundle that
  hydrates them: the page is finished markup when the first byte arrives, and the bundle then makes
  the **language switch instant** (no reload, `<html lang>`, title, canonical and URL move together,
  a stored choice is remembered and a first visit in another language corrects itself), with the
  switch still a plain link and the FAQ still `<details>` when no script runs (~155 kB over the wire,
  81 kB of it gzip for React, no web font, CSP `script-src 'self'`). It says what the product is *today*: authoring happens outside
  BizView with any AI, the starter zip goes in and the project zip comes back, no chat and no AI key
  to run it — the copy list is grounded in this file, never in the removed agent. Every sentence,
  price, link and flag lives in `content/{es,en}.json`, so a copy change is a commit and no code
  change; **prices and contact details are not in this repository**, they are the git-ignored
  `content/private.json` overlay and the production build refuses to publish while any of them is
  missing. The design tokens are extracted from `frontend/src/index.css` by
  `scripts/sync-tokens.mjs` (with a drift test), and the hero's phone is **drawn** from the tokens
  rather than photographed, because the demo installation it should show does not exist yet —
  `media.useMockups` flips it to a real screenshot when it does. Contact actions are WhatsApp deep
  links whose message is already written in the visitor's language, with `mailto:` beside them. 21
  contract tests cover content parity, token drift, the document contract (one `<h1>`, canonical,
  `hreflang`, JSON-LD), the copy lint and the contact links; at 375×667 the headline, both actions and
  the whole phone shot fit the first screen with no horizontal overflow. `vercel.json` carries the
  build, the redirects, the security headers and the cache policy, and the site's `docs/DEPLOY.md` the
  Vercel project, the environment variables, the exact Cloudflare → Vercel DNS table, the launch
  checks, the rollback and the move to the private `bizview-site` repository that the spec asks for.
  The root README now links to `getbizview.com` instead of a domain the product does not own.
- **Five more kinds of data source (feature 061)**. A customer's ERP on MySQL or SQL Server, a
  desktop system exported to a `.sqlite` file, a consultant's data in BigQuery and a business's
  prices in a Google Sheet could not be read until now. Each of the five behaves exactly like a
  PostgreSQL source for the user — **Probar conexión** with its verdict card, **Ver estructura**, the
  structure pack the starter zip carries and a read-only extraction — and each brings its own
  read-only guarantee: a `READ ONLY` MySQL session, `db_datareader` checked with
  `IS_MEMBER('db_datawriter')` in SQL Server, `mode=ro` for SQLite, the BigQuery role list, and the
  statement rule for everyone. A full origin (MySQL 1040, SQL Server 17809, Google's quota, a locked
  SQLite file) is 060's amber pause, not a defect. The kind is now declared **once**, in
  `app/sources/connectors/registry.py`: the connection test, the structure reader, the extractor, the
  BI-ready check, the sample requests, the AI structure prompt, the worker and the CLI all read it,
  so the next engine (Oracle, `062`) is one module and one row.
- **A cost ceiling for BigQuery**: every query is dry-run first and refused before it runs when the
  estimate exceeds **Máximo de bytes facturados por consulta** (1 GB by default), so a wrong query
  costs nothing.
- **`SOURCES_FILES_DIR`**, the only folder a SQLite source may read from; when it is unset the kind
  is not offered at all, and a path outside it (a `..`, a symlink escaping it, the product's own
  database) cannot be saved.
- **The upgrade repairs the audit constraint 0055 left short.** Two literals of 0055's frozen list
  ran together, so the CHECK it created forbade `starter_downloaded`, the three `mail_list_*` kinds
  and `mail_send_resent`: a starter-pack download and every mailing-list action failed on the audit
  insert. `0056_more_source_kinds` rebuilds that constraint from every kind a database may hold —
  including the removed agent's `assistant_*` rows — and only ever grows it, so an installation that
  failed this upgrade before now completes it.
- **`docs/INSTALL.md` and its Spanish pair gain one section per kind**: the minimum privilege, the
  exact `GRANT`/`CREATE LOGIN` to paste, TLS, and the mounted folder for SQLite — plus a help topic
  «MySQL, SQL Server, SQLite, BigQuery y Google Sheets» in both languages.
- **A dashboard can be mailed to any list of addresses (feature 058)**. "Enviar por correo" reached
  installation users, and outside them only addresses inside `EMAIL_ALLOWED_DOMAINS`, twenty at a
  time, typed one by one; scheduled deliveries addressed roles. A send now takes three kinds of
  recipient, mixed: users, **mailing lists** and free addresses typed or pasted (`Nombre <correo>`,
  separated by comma, semicolon, space or newline, duplicates collapsed, the sender's own address
  dropped, invalid ones shown and blocking). **Listas de correo** keeps reusable lists — name,
  description, members with an optional display name, a paused flag, CSV import and export, up to
  1,000 members — `personal` or `compartida` (only administrators create shared ones), and a list may
  instead be **dynamic by role**, resolving to the installation's users of that role at send time.
  Deleting a list pauses the scheduled deliveries that named it, with the reason, instead of deleting
  them. A project's `distributions/<id>.yaml` still names **roles and list names, never addresses**;
  apply refuses a name with no list, naming it. Every send keeps one status per address under
  **Envíos**, and **Reenviar los fallidos** queues only what failed.

### Added

- **A source declares how many sessions BizView may hold on it (feature 060)**. The origin's
  `max_connections` is shared with the application that owns it, so BizView stops being a greedy
  neighbour: **Conexiones simultáneas** on the source page (1–20, default 1 for a PostgreSQL origin
  and 2 for Supabase) bounds every reader of that source — scheduled runs, manual runs, `describe`,
  structure generation and direct reports — through one permit per source, held across threads and,
  for runs, across processes with a lock on the product's own database. A run holds **one** origin
  session, reused across the datasets of its integration instead of one per dataset, connects within
  10 s, gives up its slot after 30 s idle inside a transaction or 60 s idle where the server knows
  those settings, and names itself `bizview-engine:<integration>` in the origin's session list so a
  DBA can attribute it. A run waiting for its turn says «Esperando turno en la fuente». **Probar
  conexión** now also reports the origin's maximum connections and its current client count when the
  credential may read them, and says "sin permiso para verlo" when it may not.
- **A help topic for the operator who finds an amber run (feature 060)**: «La fuente no admite más
  conexiones» / "The source has no free connection slots", in both languages, linked from the run
  and matched by a section in `docs/INSTALL.md` (and its Spanish twin) — whose limit it is, the two
  queries that show who holds the slots, why `ALTER ROLE … CONNECTION LIMIT` does not reserve
  anything, the four remedies (a pooler, raising the limit with the vendor, reading a replica, moving
  the schedule off-peak) and how to tell it apart from BizView's own database running out of
  connections. The integration page suggests the quietest hour it has observed once an integration
  accumulates three busy runs in a day.

### Changed

- **The product no longer limits how much mail an installation sends (feature 058)**. The ceiling of
  20 recipients per send and the limit of 30 sends per user per hour are gone, and nothing replaces
  them: the volume is the mail provider's call (SES, a corporate relay for several senders). The
  only guard is throughput, which protects the provider rather than the product — `EMAIL_BATCH_SIZE`
  recipients per message via BCC (sender in To, default 50), `EMAIL_SEND_RATE` messages per second
  (default 10, `0` unlimited), and `EMAIL_INDIVIDUAL_MESSAGES` for one message per address, which is
  what SES recommends for per-address bounce handling. `EMAIL_ALLOWED_DOMAINS` becomes optional: unset
  or empty (the default now) accepts any domain, and when set it limits the free addresses and the
  members of a list, never the installation's own users. `EMAIL_SENDING_PAUSED` holds the queue while
  sends keep being accepted, `EMAIL_FROM_MODE` chooses whether mail comes from `SMTP_FROM` with the
  sender as `Reply-To` or from the sender's own address, and `EMAIL_FREE_ADDRESSES_ROLE=admin`
  restricts typed addresses to administrators (lists keep working for everybody). The catalogue keeps
  the change: `docs/INSTALL.md` lists what each provider needs, `.env.example` documents every
  variable, the 018 specification is amended, and a grep gate refuses the two removed constants by
  name.

- **A document that says what BizView does with a `report.yaml`, in both languages (feature 057b)**.
  AUTHORING and REPORTS told an author how to write a report and never how it is executed, so the
  questions that matter — why a figure changes with the period, where the comparison comes from, how
  long a cached answer lives — had no answer outside the source. `docs/RENDERING.md` is that answer:
  six numbered steps with the file behind each one (apply composes an immutable version; `uses`
  resolves to `ds_<integration>.<dataset>` with the integration's column contracts; the request's
  period becomes two local dates and its hash plus the last load is the cache key the `ETag`
  answers; each view is one aggregation per period, with a real generated statement quoted and the
  comparison as a second run over the previous range; `layout.web` binds components by view id and
  the formats are applied in the browser and again in the PDF; freshness is the last load), a
  sequence diagram (`docs/assets/rendering.svg`, source in `docs/assets/rendering.mmd`) and a table
  of what each key controls at run time. Its short form is a block in both READMEs, a topic in the
  guide (**Crear con tu IA → Cómo se dibuja un tablero**) and two documents inside every starter
  zip, `COMO-SE-DIBUJA.md` / `HOW-IT-RENDERS.md`.

- **The product writes the starter pack, so an author without a terminal can start (feature 057)**.
  Authoring moved outside Bizview in 043/045, but the only way to obtain the folder it needs was
  `bizview init workspace` on a machine with the CLI. **Proyectos → Nuevo proyecto → Descargar paquete
  inicial** now builds `bizview-starter-<slug>.zip` on the server from one source,
  `pack/bizview-starter-pack/`: the prompt, `REQUEST.md`, `project.yaml`, the spec, plan and tasks
  skeletons, the integration and report skeletons, the schemas the validator reads, both
  explanatory documents and — when a source is chosen — its structure pack, generated on the fly and
  never carrying a credential or a row. The dialog collects the name, the optional source, the
  language and the kind of the first spec; the result is measured against the two import allowances
  before a byte is served. The same pack is `bizview init project "<name>" [--source <s>]`, what
  `bizview init workspace` seeds, and the published
  [`bizview-starter-template.zip`](bizview-starter-template.zip) built by `make starter-template` and
  served at `GET /api/projects/starter-template`. The rendered project validates with zero errors;
  what is left to write is marked `REEMPLAZA` / `REPLACE`. Every text ships in Spanish and English,
  including `CONTENIDO.md`/`CONTENTS.md` (what each file is for) and
  `QUE-HACE-BIZVIEW.md`/`WHAT-BIZVIEW-DOES.md` (what import and apply do).

- **Importing a project again is a new revision of it, not a second project (feature 055)**. Every
  correction to a project arrived as another zip, and **Importar** treated a taken slug as a
  collision: it appended `-2`, created a different project, and the installation ended up with
  `ventas-marca`, `ventas-marca-2` and `ventas-marca-3` whose ids collided at apply and whose shares
  and grants had been left behind. The import now matches by slug — the manifest's, or the one the
  project's name derives to — and, when the project exists, writes the archive as its **new draft
  revision** with full-replacement semantics (what the zip no longer carries leaves the folder,
  images included) while the project keeps its id, slug, shares, grants, dashboards, audit history
  and loaded data. The incoming `project.yaml` gets the project's own slug (an archive exported from
  the product carries `slug: ""`, which the schema refuses at apply time). Before writing anything
  it answers a **diff** — files added / changed / removed, specs and ids, the two allowances of 049
  — shown in the import card; a dry run writes nothing, and editor changes saved since the last
  import are overwritten only after **Reemplazar borrador**. A project keeps numbered revisions
  (`rev 3 · aplicada`, `rev 4 · borrador`), listed in the project page with their date, author,
  source and diff, each downloadable as a zip; **Aplicar** marks the draft applied and the previous
  one *anterior*, and **Volver a la revisión anterior** writes that revision back as a new draft and
  applies it, audited.
  `PROJECT_REVISIONS_KEEP` (default 20) bounds the history and never prunes the applied or previous
  revisions. `Importar como copia` is now the only way to get a second project, and the copy renames
  its artifact ids so it can apply. `bizview import <zip>` prints the mode and the diff against the
  workspace folder, and the API takes `copy`, `dry_run` and `replace_draft`. Migration
  `0052_project_revisions` adds `project_revision` and `project.revision_seq`.
- **Sign in with Google, branded, and a role policy the superuser can edit (feature 054)**. The
  sign-in page showed a plain outline button next to Telegram's: it is now Google's own action — the
  four-colour **G** inlined in the bundle (no external fetch), a light surface on the light theme and
  a dark one on the dark theme, the same 44 px height as the Telegram button, the mark at the left —
  and the two providers keep the order email → divider → Google → Telegram, each hidden when its
  provider is off. The card in **Administración → Seguridad → Ingreso con Google** turns what used to
  be env-only into policy: **Dominios permitidos** (the first save copies `GOOGLE_ALLOWED_DOMAINS`
  into settings and the settings win from then on), **Alta automática** with a default role — never
  **Superusuario** — and a default dashboard access (none, every public dashboard, or a chosen list),
  **Vincular por correo** with the "apply the rules to existing users too" switch off by default, and
  an ordered list of **Reglas de rol** that matches on `domain` or `email` (the `group` condition is
  shipped greyed as *próximamente*), first match wins. A provisioned account is active,
  `auth_provider=google`, carries no password and cannot sign in with one until an administrator sets
  it. Every change and every sign-in is audited (`google_settings_updated`, `google_rule_created`,
  `google_rule_updated`, `google_rule_deleted`, `google_user_provisioned`, `google_rule_applied`,
  `google_sign_in_refused` with its reason), the page keeps one generic sentence for every refusal,
  and superusers are never created or modified by a rule. Migration `0051_google_rbac` adds the two
  tables (`google_settings`, `google_rule`) and the two columns that make a passwordless account
  possible (`app_user.auth_provider`, `app_user.password_hash` nullable). Principle **V (Auth)** of the
  constitution is amended (3.2.3 → 3.3.0): Google sign-in was bounded as *invite-only — it never
  creates or promotes a user*, which is precisely what this feature needed to lift. The replacement
  keeps every bound that still holds and adds the two installation-owned, audited ones — opt-in
  automatic sign-up on the allowed domains (never a superuser, no password) and an ordered rule list
  that may decide role and access, never for superusers and never for existing accounts unless the
  installation asks for it.
- **Each source shows its structure, and one button generates the pack an author's AI reads
  (feature 052)**. The source page gains a second tab, **Estructura**: the catalogue as it is
  (schemas, tables, columns, types, keys, estimated rows, date ranges) and, for REST/Supabase, the
  saved **sample requests** with the shape of their responses. On top of that, **Generar estructura
  con IA** runs one internal pass with no input from anybody — Bizview scans the source (describe,
  the samples, the OpenAPI document when the source publishes one), the provider identifies the
  logical tables, fields and semantics, keys, dates, relations, personal data, pagination and the
  notes that say what one row is, and product code verifies every name against the scan before it
  saves the pack. What the model invents is dropped and listed, so a hallucinated table cannot reach
  a spec. **Descargar estructura** produces `structure.md` + `structure.json` from that pack (or from
  the plain scan when no run exists), through one generator shared by the button, the API and
  `bizview describe --pack`; `structure.json` validates against `structure.schema.json`, which also
  ships in the authoring pack.
  A structure *chat* was the first design of this feature and the owner replaced it on production:
  one button, no conversation, nothing typed. Nothing but metadata ever leaves a source — no row
  values, hosts or credentials — and the personal-data flags are heuristics a super user can
  override, carried in the pack. Constitution VIII is amended (3.2.2 → 3.2.3) to name AI-assisted
  structure generation as the second read-only AI surface.

- **Values on demand and full screen, per card (feature 056)**. Hovering or tapping a bar or a slice
  shows a chip with the full name, the formatted value and its share, and dims the other marks
  (`prefers-reduced-motion` keeps the colour and drops the scaling). `labels: true` on a
  `bar`/`line`/`area`, or `labels: values|percent|both` on a `pie`/`donut`, prints the figure
  permanently and hides the labels that do not fit; the key is in `report.schema.json`, the CLI
  validator and `docs/AUTHORING.md`. Every data card offers **Ampliar**, opening it full screen at
  `?ampliar=<component id>` with ← → between the dashboard's cards, a PNG of the view and Esc
  closing back to the card that opened it.

### Fixed

- **The navigation tells you where you are and how to get back**. The four counters on
  Inicio were dead numbers; each one is now a link to the menu option it counts (Tableros, Usuarios,
  Fuentes de datos, Integraciones). "Mis listas" left the sidebar — lists live in **Administración →
  Listas de correo**, which now carries the same **Volver** and breadcrumb as every other page — and
  the send dialog's "no lists yet" hint points at where they are created instead of at a menu entry
  that no longer exists. **Apariencia** links to the guide (*Crear un tema con tu IA*) that explains
  the file a theme is, and **Proyectos** shows **Volver** to Administración when it was opened from
  its tile, while the sidebar entry still opens it without a back button.

- **A full origin pauses the run instead of failing it (feature 060)**. An hourly run of
  `ventas-medicalvet` failed with `FATAL: lo siento, ya tenemos demasiados clientes` (SQLSTATE
  `53300`): the ERP that owns the origin had taken every connection slot, PostgreSQL refused
  BizView's *connection* before a single row was read, and the product reported a healthy hour as a
  defect — the same red badge as a broken query, the next attempt only on the next cron tick, and no
  word about whose limit it was. A connection-slot refusal (`53300`, `53200`, `57P03`, `08001`,
  `08006`, and the pooler wordings that stand for them) is now its own condition: the run waits and
  retries inside itself with a jittered exponential backoff (`SOURCE_CONNECT_RETRIES`, default 4
  attempts; `SOURCE_CONNECT_BACKOFF_S`, default 15 s → 15 s, 45 s, 2 min, 5 min), a stop request or
  the integration's own time limit interrupts the wait, and only when every attempt is refused does
  the run end `skipped_busy` — amber, "La fuente no admite más conexiones ahora", with the SQLSTATE,
  the attempts and the wait in `integration_run.busy`, and the origin's own words redacted of host
  and credential. Nothing is written: the datasets keep their rows and the reports keep their
  "Datos actualizados" time, and the next tick simply tries again. Three consecutive busy runs send
  one Telegram notice to the superusers who linked the bot (never one per tick), recorded as
  `integration_busy`; a run that is not busy closes the streak.

- **The sign-in page fits a phone, and the language switch stopped covering the product name
  (feature 059)**. On a 393 × 851 Android screen the `Español | English` toggle floated over the
  header and cut "Bizview AI Po…" in half, the hero (logo, name, organisation, tagline) took a third
  of the viewport and the form card overlapped it with `-mt-8`, so "Ingresa a tu cuenta" was half
  hidden under the banner edge and Google and Telegram sat below the fold. The hero is the page's own
  header below 640 px now — logo 40 px, name 18 px, organisation 12 px, tagline only from 600 px of
  height — the toggle is a compact segmented control under it, right aligned, the card starts below
  the header with 16 px gutters and no negative margin, the heading is 20 px and the helper text
  14 px, inputs are 44 px with the password eye as a 44 px target, `Ingresar` is 48 px and full width,
  and the two providers share one row with their short labels (`Google`, `Telegram`) while keeping
  the full sentence as the accessible name, while from 640 px up each takes its own row so
  "Continuar con Google" never wraps to a second line — a single enabled provider takes the whole
  width. The email field declares `autocomplete="email"` (it said `username`), the page keeps
  `scroll-padding-bottom` so a focused field and the button stay in view, and failures are reported
  inside the card instead of a banner that pushes the form down.
- **The Filtros | Parámetros sheet uses the whole screen on a phone (feature 059)**. It opened at
  72 % height behind a drag handle, so the top quarter showed the greyed dashboard and was useless,
  every control repeated its section title (`PERÍODO` above `Período`, `COMPARAR CON` above
  `Comparar con`), 52 px tall cards needed two screens of scrolling for four controls, and the footer
  covered the last one. Below 640 px the sheet is full screen (`100dvh`, no handle, tabs on the left
  and `×` on the right, sticky footer with **Limpiar** and **Listo**, `env(safe-area-inset-bottom)`),
  the repeated titles are only announced to a screen reader, controls are 44 px with 12 px gaps,
  **Período** and **Comparar con** share one row whenever two 160 px columns fit (the custom range
  keeps its own two-column row), and **Paleta** and **Tema del reporte** are single scrolling chip
  rows instead of selects. Tablet keeps the bottom sheet at 85 % and the desktop keeps its 360 px side
  sheet. Opening pushes one history entry, so the phone's back button closes the sheet, **Limpiar**
  restores the report's defaults, and a downward drag only dismisses when it starts outside the
  scrolling body, and the body keeps 24 px (32 px from 640 px) under its last control so the footer
  never looks like it is cutting the content off. Live apply keeps its 250 ms debounce.
- **A KPI fills the width its author gave it, and cards in a row share a height (feature 056)**. A
  `layout.web` `kpi` component rendered through `KpiGrid`, whose `<ul>` kept its `grid-cols-2
  lg:grid-cols-4` even for a single metric: a `span: 6` card drew a ~200 px card at the left of its
  column and left the rest empty, so a dashboard looked broken and could not be fixed from YAML. The
  component now renders one card, `w-full h-full`, with the anatomy the design system asks for:
  icon and label, the value at a fluid size, then a delta row with its own top margin and a reserved
  height — the "antes" line no longer collides with the badge on a two-line value. Every cell and
  every card is `h-full`, a chart's drawing area is `flex-1`, and minimum heights (KPI 150 px,
  chart 320 px) keep four cards in a row on one rhythm.
- **A long category name is shortened, never cut (feature 056)**. `HorizontalBars` capped its label
  column at `min(112, max(64, width * 0.28))` and drew the text right-aligned, so `BIOLOGICOS
  PROVIACOL FORTE` appeared as `OLOGICOS PROVI…`: the reader lost the beginning, the part that
  identifies it. The column is measured from the real font now (at most 220 px and 40 % of the
  chart, at least 96 px), the text is shortened with a trailing ellipsis, `<title>` keeps the whole
  name, and below 480 px the label moves above its bar so nothing is truncated at all.
- **The card opened with Ampliar fills the screen (feature 056, converged)**. The dialog was right
  and the card inside kept its dashboard geometry: it was rendered untouched, so a `span: 6` landed
  in half of a twelve-column grid, the frame around it had no height for `useChartHeight` to
  measure, and the card drew its own title, its own **Ampliar** and its own `⋯` a second time inside
  the dialog. The card is now passed as `span: 12` with the height chain (`h-full min-h-0 flex-col`)
  and a `maximized` flag that drops its title, its controls, its border, its shadow and its padding,
  so the chart is drawn at the size of the dialog: bars grow taller, the label column may take half
  the width and 480 px (`BIOLOGICOS PROVIACOL FORTE` fits whole from 1200 px up), a donut ring is
  `min(60vh, 520px)` with its legend beside it, and a KPI shows its value at up to 96 px. The dialog
  header carries the period, the comparison and the active filter chips, ← → no longer fill the
  history (Back closes the dialog), a tip follows the pointer instead of sitting on the mark, and a
  `line`/`area` with `labels` now prints a value at each point.

### Changed

- **The shell is mobile first, measured at 360 px (feature 059)**. The page title is 22 px with the
  description clamped to two lines and the meta line wrapping; the breadcrumb trail is hidden below
  480 px while **Volver** stays; `Filtros`, `Parámetros` and `⋯` become 72 px icon-above-label buttons
  below 420 px with their full name still as the accessible name; every input, select and combobox is
  44 px under 640 px. `frontend/tests/e2e/mobile-first.spec.ts` measures the sign-in screen at
  393 × 640, the sheet at 393/768/1280, and asserts no route scrolls sideways at 360 px, with axe
  clean at 360/393/414/768/1280 in both themes.
- **Every shipped document exists in Spanish and in English, and a gate keeps them in step (feature
  057b)**. `docs/es/` held three shortened documents while INSTALL, THEMES, DESIGN-SYSTEM,
  CONTRIBUTING, SECURITY, CODE_OF_CONDUCT and DIAGNOSIS had no Spanish at all, so a Spanish reader
  got a summary of one third of the product. Each one now has its counterpart: same heading
  skeleton, same code blocks, same tables, same links, with the prose translated instead of
  summarised, and the pair cross-links at the top of the file. `scripts/check_docs_parity.py`
  measures exactly that — headings, fenced blocks, tables and resolved links — for the root
  documents, `docs/`, the in-app help (`es/` ↔ `en/`) and the starter pack; it runs in
  `make check` and in the gates workflow, and it fails naming the file that drifted. The
  `docs/VIBE-REPORTING.md` stub is gone (REPORTS.md replaced it; the inbound links were repointed),
  and the rule is recorded in CONTRIBUTING and in the 046 governance requirements (FR-020, FR-021).
- **Help, README and docs describe the product that exists (feature 057)**. The guide's *Agente y
  Spec Kit* section is gone; **Crear con tu IA** holds the starter pack, the request, handing it to
  any AI, validating, fixing problems, re-importing and a complete worked example, plus a topic that
  is the same text shipped inside every zip. Every topic now ends with **Relacionados**.
  *Primeros pasos* is the five-step path, and the topics that still described a chat now describe
  import, apply and the optional CLI. `README.md`/`README.es.md` present the five steps with the
  starter download as step three, list what exists after 047–055 and say plainly that no AI key is
  needed in Bizview. `docs/VIBE-REPORTING.md` became `docs/REPORTS.md` (a stub keeps the old path),
  `docs/AUTHORING.md` starts with the starter pack and names the nine checks, and `docs/IMPORT.md`
  links the pack and tells the reader, in plain language, what import and apply do. Spanish mirrors
  live in `docs/es/` for authoring, import and reports.

- **Parámetros lives in the same sheet as Filtros (feature 053)**: the report page still opened a
  second, inline parameters card under the meta line — a large empty area, **EXPORTAR** with its
  format radio on one side and four selects along the bottom — although feature 030 had decided on
  one sheet with two tabs. **Filtros** and **Parámetros** now open the same right sheet (bottom sheet
  on phones) on their own tab, and the open tab's opener closes it. The Parámetros tab is a column of
  five labelled rows — Período, Comparar con, Frecuencia de actualización, Paleta (with a swatch row
  of the chosen theme), Tema del reporte — each applying live, with **Limpiar** and **Listo** in the
  footer. The palette and the light/dark choice join the URL (`theme`, `mode`) and appear as
  removable chips next to the filter chips, so a reload or a shared tab shows the same view; the
  report definition is never written from there. The shared report page gets the same two tabs.
- **Downloads moved to the ⋯ menu**: **Descargar PDF** and **Descargar CSV** export the applied
  selection from the actions row's menu, with the one line that used to explain it inside the card.
- **The installation theme now repaints the whole application (feature 051)**: applying a theme used
  to change the charts and nothing else. The application's own chrome — header band, sidebar, page
  background, cards, buttons, inputs, tables, dialogs, bottom navigation — was one set of literals per
  light/dark mode in `index.css`, and the theme contract could not reach it. Two defects, one cause:
  - a theme is now **data for the chrome too**. Seven optional tokens (`canvas`, `chrome`,
    `chrome_text`, `field`, `line`, `accent`, `warning`) join the published contract, the six new
    `shape` enums (`elevation`, `button`, `nav`, `divider`, `heading`, `card_border`) finally drive
    geometry that was previously inert, and `frontend/src/theme/derive.ts` turns a theme into every
    semantic token the screens already paint with. An uploaded theme authored before this feature
    keeps working and is derived from its palette;
  - **Usar en la instalación applies at once**: the page re-reads `/api/config` and the application
    repaints, with no reload and no sign-out. The confirmation is shown only after the server stored
    the choice, and the theme is cached on the device so a reload never flashes the previous one.
- **Four official identities, and three of them are new**: **Clásico** keeps the appearance the
  installation has today — its whole chrome token set is pinned in the theme file and a test compares
  it token for token against the literals `index.css` carried, so it cannot drift. **Impacto** is the
  modern executive identity (royal blue and cyan, pale canvas, large KPIs, strong elevation, pill
  buttons, solid navigation), **Elegante** the premium one (warm cream canvas, graphite band, bronze
  accent, flat elevation, hairline cards, left-bar navigation) and **Contraste** the high-contrast one
  (white canvas, near-black band, gold accent, 2 px borders, no shadows, outlined navigation).
  Daltónico and Monocromo remain valid and renderable and move to a **Compatibilidad** group.
- **`elegante` is registered everywhere a theme id is**: the schema, the CLI validator, the backend
  registry, the report/PDF renderer and the frontend, with migration `0048_official_themes` seeding
  the six built-ins and widening the `appearance_settings` check.
- **One design system, and the screens that had drifted from it (feature 050)**: the rules for page
  width, gutters, card padding, page headers, split panes and mutually-exclusive choices now live in
  `frontend/src/lib/layout.ts` and [docs/DESIGN-SYSTEM.md](./docs/DESIGN-SYSTEM.md). Four screens had
  each answered one of them differently:
  - **Administración → Apariencia** sat in a 56 rem column inside a 96 rem container with a fixed
    two-column grid, so a wide screen showed a narrow library with an unexplained empty half and
    over-tall previews. It now fills the container with one, two or three columns and equal-height
    cards, and the selected theme is marked with a word as well as a colour.
  - **Perfil and the account menu** stacked *Sistema / Claro / Oscuro* vertically because the theme
    switcher emitted `grid-cols-3` without `grid`, while the language options sat in a row. Both are
    now the same `SegmentedControl`, so they cannot answer differently again.
  - **Ayuda** had no bounded panel: the page scrolled instead of the article, and the topic list ran
    the full page length. Two panes now scroll on their own from `lg` up, and on a phone a topic
    replaces the list with a Back that keeps the search.
  - **The account menu** mixed identity, appearance, language and links without grouping; it is now
    four labelled groups in a viewport-bounded, scrollable popup that returns focus to its trigger.
- **The page header is a title line, not a hero block**: one compact `<h1>`, an optional subtitle and
  the actions in one wrapping row. On a 375 px phone the old card took a fifth of the viewport before
  any content.

### Added

- **Two readability guarantees in the derivation**: an accent is moved along its own lightness until
  it reads at 4.5:1 on the surface and on its own tint, and `ink-soft` is the lightest shade of the
  theme's muted ink that reaches 4.5:1 on the surface and the canvas. Both are checked for all six
  themes × two modes, in the unit suite and by axe in a real browser.
- **`tests/e2e/theme-application.spec.ts`**: apply-without-reload, persistence across a reload and a
  new session, independence from the user's light/dark preference, the four identities differing
  without labels, no sideways scroll at 320/375/768/1440, and the reference screen captured in all
  eight variants (`docs/assets/theme-application/`).
- **[docs/THEMES.md](./docs/THEMES.md)** documents the widened contract, the derivation and how the
  four identities differ.

- **Import limits that account for project images (feature 049)**: the import is charged to two
  allowances counted apart — **artifacts** (`project.yaml`, `specs/`, `integrations/`, `reports/`,
  `themes/`, `distributions/`: 400 files, 2 MB each, 20 MB total) and **assets** (`assets/`: 2 000
  files, 300 KB each, 25 MB total). Before this, images spent the room the specs needed, so a
  project that shipped a logo set was refused with a message about a budget the author could not
  act on: 483 logos and 40 artifacts could never be imported. Every refusal now names the allowance
  that was exceeded, the folders it counted and the numbers, never a combined figure. All six
  numbers are settings a super user edits in **Administración → Proyectos → Límites de
  importación**; an empty field keeps the deployment default, so an operator's
  `PROJECT_MAX_MB` still applies.
- **The import screen reads the zip before uploading it (049)**: the browser reads the archive's
  table of contents — no decompression, no library — and shows both tallies against their limits.
  Over a limit, the import action is disabled and the reason names which; the server re-checks.
- **`bizview import --dry-run <zip|folder>` (049)**: the same two tallies, the ignored files and the
  verdict from the command line, from the code the server uses (`--json` for a machine). `bizview
  validate` now reports the two allowances too.
- **A project folder that still carries the authoring pack imports (049)**: `PROMPT.md`,
  `REQUEST.md`, `request/`, `sources/`, `.bizview/`, `README.md`, `.DS_Store` and `__MACOSX/` are
  listed as ignored and the project imports. Executable content — by extension or by its first
  bytes — refuses the whole import and names the path.
- **The guide topic *Importar un proyecto* (049)** in both languages.
- **A source can be declared BI-ready (feature 048)**: instead of one installation-wide switch, each
  PostgreSQL source carries its own declaration — the schemas and objects reports may read, the query
  timeout, the cache lifetime, the row cap, the concurrency and the timezone its dates are read in.
  Bizview proves the credential read-only when it is saved and once a day (a write attempted and
  refused, inside a transaction that is rolled back), the source page shows the declaration, the
  limits in force and the last 24 hours of direct reads, and an object outside the declaration is
  refused by the validator and again by the engine.
- **A direct report needs no column list (048)**: for a BI-ready source, `direct.tables` accepts
  `alias: schema.object` and the columns come from the source's structure; the 019 shape and
  `source: bi` keep working untouched.
- **A direct report can keep its figures for a day (048)**: `materialize: daily` makes the worker run
  the report once and store the payload it already produces, so every viewer reads that with the
  notice that it is yesterday's. Figures only — no rows, no `ds_` schema.

### Removed

- **The inline parameters card (feature 053)**: `ParamBar` and `ExportSection` are gone, with
  **Generar reporte**, the PDF/CSV radio and the strings that named them. A reader used to reach
  export through the parameters card; the card also cost a screen of height above the numbers.
- **Manual project creation (feature 049)**: the "Nuevo proyecto" button, its form and
  `GET /api/projects/slug` are gone, and `POST /api/projects` answers `410`
  (`project_creation_removed`) instead of creating anything. Projects are authored outside Bizview
  and arrive only by import — which is what the constitution already said, and what the empty state
  now offers. Existing projects, their files, reports and history are untouched.

### Fixed

- The 512 KB per-file check in the CLI and the 2 MB budget the specification states were two
  different answers to the same question; one shared number now, so `bizview validate` and the
  server cannot disagree about a file.
- **`GET /api/projects/<slug>/tree` answered 500 for any project with a spec folder** since 045:
  the route still read the `converged` flag the in-app agent used, and 045 removed its producer
  while the frontend type had already stopped asking for it. The project editor, the e2e flows and
  the tree the import screen reads were all affected.
- **A project with a flagged personal column could never be applied** since 045: readiness demanded
  an explicit confirmation in the conversation's working state, which 045 removed, so declaring the
  column under `**Datos personales**:` in the integration spec was not enough and "Aplicar
  proyecto" stayed disabled with no way out. The spec declaration is the record again, and the same
  column is no longer reported twice when two datasets share it.
- **The project editor said nothing while it validated**, and dropped the result when the request
  failed: Apply stayed greyed out under "Sin problemas de validación" with no visible reason. The
  status bar now says **Comprobando el proyecto…** and, when the check cannot run, says so.
- **A column named `name` was treated as personal data everywhere** — a coin, product or category
  name included — so `panorama-cripto`-style reports could not be applied and the only way out was
  to declare a falsehood in the spec. A bare `name`/`nombre` is personal only when its dataset is
  about people (customers, users, patients…); `customer_name`, `full_name` or `email` are unchanged.
- **The two rules that block an apply were invisible to the author's AI**: `bizview validate` said
  "ok" while the server refused the project for a personal column, and said nothing about a report
  with no filters. Both are reported now — the personal column as an error, the missing filters as a
  warning — and the pack's agent instructions state them.
- **«Volver a comprobar» never answered** since 045: `POST /projects/<slug>/validate` stored the
  validation on the project row, and the origin checks store their result on that same row through
  `WorkView._persist`, in a separate transaction — while the write also left the mapped attribute
  dirty, so the caller's session flushed it again. The second write waited on the lock the first
  one held, for as long as the HTTP client stayed connected: the button spun forever, every click
  parked a database connection and the rest of the installation slowed down with it (it was already
  holding two connections and the project row for twenty minutes on the owner's server). The
  checks now run before anything is written, the value they store is taken in memory as committed
  instead of dirty, and their own write waits at most 5 s. The editor also refreshes problems and
  readiness with `check_origin=false`: re-checking every query against its source belongs to the
  button, not to every file change the poller notices.

### Changed

- `DIRECT_REPORT_CONCURRENCY`, `DIRECT_REPORT_WARN_ROWS` and the rest of the `DIRECT_*` variables are
  now the defaults a source inherits, not the whole truth of what may be read.


- **Themes are data an author writes outside Bizview (feature 047)**: the five looks the product
  shipped are now themes in a published format
  ([`cli/bizview_cli/schemas/theme.schema.json`](./cli/bizview_cli/schemas/theme.schema.json)) — a
  file of colour tokens and shape choices, never CSS — that a person or any AI can write, validate
  and preview without a server (`bizview theme validate`, `bizview theme preview`). The validator
  refuses a shape and a look alike: contrast of text, accents and every series against its own
  surface, series separation, polarity, a grid that stays out of the way, each refusal naming the
  tokens and the measurement.
- **A theme library (047)**: Administración → Apariencia lists the product's themes, the ones
  uploaded there and the ones a project brought, each with a light and a dark preview, its origin
  and its version; upload, download, duplicate, delete and apply, with the upload printing every
  problem it found and a collision asking before replacing. A theme a report uses cannot be deleted.
- **A report chooses its theme and its own mode (047)**: `layout.theme.id` names any theme of the
  installation and `layout.theme.mode` (`auto|light|dark`) decides the report's area, so a dashboard
  can be dark inside a light application while the chrome stays as the viewer chose; a sun/moon
  action overrides it for the session and a share link opens in the report's mode. The PDF always
  uses the theme's light variant. A report naming a theme that exists nowhere is a validation
  problem instead of a silent fallback.
- **A project carries its themes (047)**: `themes/<id>.yaml` inside a zip is validated and enters
  the library with the project as origin; a collision offers skip, replace or rename (the project's
  own references follow the rename), and the themes leave with the project when it is deleted.
- `THEME.md` in the authoring pack and [docs/THEMES.md](./docs/THEMES.md), plus the guide topic
  *Escribir un tema* in both languages.

### Removed

- **The placeholder "Ventas" dashboard**: a new installation used to open on a board marked
  *coming soon* that led nowhere, and the catalogue showed it to every user. The product ships no
  dashboard — one appears when a project is applied or when an administrator creates it, and the
  home screen says so — so migration `0002` no longer seeds it and `0046` removes the row from the
  installations that already ran it. Only the seeded row is deleted (`managed_by = 'product'`, no
  report behind it): a board a workspace or a person owns is never touched.

### Changed

- `layout.theme.palette` is the deprecated alias of `layout.theme.id`, accepted for one version so
  every project written before this release keeps applying.
- An installation's choice is stored as a theme (`appearance_settings.theme_id`), with the old
  `palette_preset` read as the fallback: the five ids are unchanged, so nobody's look moves.

## [0.2.0] - 2026-10-31

Bizview stops authoring. The in-app agent never worked well enough to trust (owner, 2026-10-29:
"the in-app agent never worked; better to use a powerful AI dedicated to this, externally"), so
authoring moved outside the product (features 043 and 045) and everything that existed only to
serve it is gone. Reading, running and sharing are untouched. This release is also the one that
makes the written product match the shipped one (feature 046).

### Added

- **Images travel inside the project (feature 044)**: the project's `assets/` folder accepts
  `.png`, `.jpg`, `.webp` and `.svg` (≤ 300 KB each, ≤ 25 MB per project), with the bytes checked
  against the extension and the SVG cleaned on import (no scripts, no external references). A
  report declares `images: {coins: {folder: assets/coins, key: symbol}}` and a component uses it
  with `image: coins`: the row's key finds `BTC.png`, `btc.png` or `BTC.svg` without anyone writing
  a path, and the image is served at `/api/reports/<id>/assets/…` with `ETag` and immutable. With
  no file, or with `fallback: none`, the tile draws the initial on a palette colour. `assets/`
  travels in the project's export and back through import.
- **Four visual blocks in the PDF (feature 044)**: `gauge`, `index`, `share` and `asset` are no
  longer screen-only. The PDF draws the arc with its bands and needle, the index bar with both
  ends, the share as its parts and the tile with the logo, the figure and the signed badge, and
  the numbers match the screen. Images are embedded from the project itself; a set with only SVG
  prints the initial circle, as the validation already warns.
- **Images from a URL column are cached once (feature 044)**: after a successful load, the worker
  downloads the new addresses of the column the report declares (under the sources' address guard,
  10 s, 300 KB, PNG/JPEG/WebP only) and stores them named by their hash. The row is rewritten to
  point at Bizview, so whoever opens the dashboard never calls the third party, two URLs with the
  same bytes share one file, and a failure is recorded without breaking the load (retried at most
  once a day).
- **The authoring pack (feature 043)**: `bizview init` writes the presets, the rules, the schemas,
  `PROMPT.md`, `REQUEST.md` and a golden example into a workspace, so a customer can build a
  project with any AI — or by hand — against the published contract.
- **Structure packs (feature 043)**: `bizview describe` and the workspace rules hand an external AI
  a source's structure, counts and shapes — never credentials, hosts or row values.
- **Import as the front door (features 020 and 046)**: **Proyectos → Importar** takes a zip, maps
  the folders, reports collisions, validates and shows the tree before anything is applied. The
  path is documented in [`docs/IMPORT.md`](docs/IMPORT.md).
- **`docs/AUTHORING.md` (feature 046)**: the contract in one document — folder layout,
  `PROMPT.md`/`REQUEST.md`, the schemas, the rules, lite specifications, validation and its
  `problems.json`, images, and a complete worked example.

### Changed

- **Principle IX of the constitution, and its preamble, folders and constraints (amendment
  3.0.0 → 3.1.0)**: projects are authored outside Bizview against the published contract and enter
  only through validation and import; the AI boundary names the structure-pack rule; the CLI's
  schemas are the single source of the contract; the import limits are written down.
- **The product is called `Bizview`** (0.2.0): `PRODUCT_NAME`'s default, the page title, the
  manifest, the package descriptions and every document drop the "AI Powered" suffix. An
  installation still chooses its own name.
- **`VERSION` is the single source of the version**, and `scripts/gates/07-version.sh` proves the
  backend, the frontend, the CLI package and `bizview version` agree with it — the four copies had
  drifted to 0.1.0, 0.2.0, 0.3.0 and 0.4.0 before this release.
- **Both READMEs are rewritten around the loop** (feature 046): what the product does, a one-screen
  install, the eight authoring steps with the commands a reader types, the capabilities table, the
  configuration groups and the architecture — with the same structure in Spanish and English, which
  `scripts/gates/08-markdown.sh` checks.
- **`SECURITY.md`, `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`** (feature 046): the reporting
  channel, the supported versions, the in-scope and out-of-scope surface, the protections that are
  true now; the development stack, the specification workflow, how to add a help topic and how to
  propose a schema change; the Contributor Covenant's contact address.
- **The authoring contract (feature 044)**: `report.yaml` gains `images:`; the `table`, `kpi` and
  `asset` components accept `image:`; `layout.pdf.blocks` accepts the four visual types, and the
  validation rejects a block bound to a view it cannot draw. `docs/REPORTS.md`
  (then `docs/VIBE-REPORTING.md`) is the field-by-field reference the authoring guide links to.
- **Administración**: the AI card and the "IA funcionando" pill are gone; the access-tokens and
  projects cards say what they now do; the grid is 3/2/1.
- **Upgrading from 0.1.x**: migration `0041_drop_authoring_agent` copies every draft spec document
  into its project folder and verifies each copy by SHA-256 **before** dropping a single table. A
  copy that fails aborts the upgrade with the tables intact. The downgrade refuses on purpose:
  recreating the tables empty would pretend the rows came back. Recovering them means restoring the
  database backup taken before the upgrade.

### Removed

- **Feature 014 — vibe chat**: the conversation, its composer, the "Asistente" panel and its
  routes, the draft preview and its temporary schemas, the tables `assistant_session`,
  `assistant_message` and `assistant_preview_request`.
- **Feature 015 is NOT removed**: the brief that listed it among the agent's specs was wrong — the
  folder is dashboard auto-refresh and TV mode, which this release still ships.
- **Feature 017 — the agentic loop**: `app/assistant/**` (loop, tools, tree and history builders,
  context compression, repair), the run activity map and the token-budget widgets.
- **Feature 021 — Spec Kit commands in the app**: the in-app `/speckit-…` and `/ayuda` commands, the
  command registry, its guards and the `assistant_command_run` table. The Spec Kit flow itself
  lives in the author's repository, driven by the CLI.
- **Feature 024 — image briefs**: `ATTACHMENTS_DIR`, `ATTACHMENTS_MAX_MB`,
  `ATTACHMENTS_MAX_PER_MESSAGE`, `AI_VISION` and the attachment sweep in the worker.
- **Feature 028 — Auto mode**: the mode selector, run contracts and profiles, "Pasar a Auto", the
  post-apply watch with its automatic rollback, and the tables `assistant_auto_run` and
  `assistant_run_profile`.
- **Features 039 and 040 — `/speckit-all`**: the state machine, its stage bounds and tool groups,
  its stage token ceiling, the run report as a product output and the `--only` task guard. Feature
  029 was a numbering gap and never existed.
- **Features 035 and 036 — the chat's AI status and history**: the narrative generator and the
  repair of conversation history. `report.yaml`'s `ai_narrative` key stays accepted and ignored
  (deprecated since 0.2.0) so a project written for an older installation still validates.
- **Feature 037 — the project preview work order**: `POST /api/projects/{slug}/preview` and its
  report, data and PDF endpoints. Published report rendering, PDF, sharing and email remain.
- **Settings and dependencies**: `AI_CHAT_*`, `AI_COMMAND_TOKEN_CEILING`, `AI_CONTEXT_COMPACT_CHARS`,
  `AI_STAGE_TOKEN_BUDGET`, `AI_AGENT_*`, `AI_AUTO_*` and `AI_TOOL_TIMEOUT_SECONDS` (replaced by
  `ORIGIN_CHECK_TIMEOUT_SECONDS`). `AI_PROVIDER` stays, defaults to `none` and is documented as
  help only. Provider tool-calling code, `app/ai/fake.py` and `app/ai/history_rules.py` are gone.
- **Specifications**: 014, 017, 021, 024, 028, 035, 036, 039 and 040 moved to `specs/_deprecated/`,
  each with a `DEPRECATED.md`.
- **The draft preview's readiness gate**: a project is ready on validation, query checks and the
  composition of the other applied projects; it no longer needs a preview before applying.

### Security

- **Import validates before anything runs** (features 044 and 046): file types, per-file and
  per-project sizes, path traversal, byte sniffing for images, SVG sanitisation and the same JSON
  Schemas the CLI validated against. A rejected import leaves nothing half-imported.
- **The image fetch follows the sources' address rules**: loopback, link-local, cloud-metadata and
  internal addresses are refused, redirects are not followed, the size is capped and the bytes are
  content-sniffed.
- **No AI authors inside the product**: the optional provider serves the read-only help page, and
  the structure packs a customer hands to an external AI carry no data.

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
