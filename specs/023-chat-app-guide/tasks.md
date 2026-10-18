---
description: "Task list for feature 023 — The agent explains the app, Spec Kit and projects"
---

# Tasks: The agent explains the app, Spec Kit and projects

**Input**: [spec.md](./spec.md), [plan.md](./plan.md).

**Prerequisites**: 019, 005-A, 022, 020 and 021 implemented (fixed order). Where those features
chose other names (registry API, `MarkdownView` props, route paths, catalogue access), follow the
code and keep the intent of the task.

**Roles**:
- Claude thinks: spec, plan, tasks, briefs.
- **Guide content tasks (marked ✍) are drafted by Claude** from the specs and the catalogues, and
  reviewed by the owner (spec Assumption).
- DeepSeek writes all code, tests and fixes from the briefs.
- Claude reviews line by line: the privacy contract of `get_project_overview` (VIII), the role
  filter of the guide API, and link filtering.

**Rules for every task**:
- No modals.
- Every new UI string goes in both `frontend/src/i18n/es.ts` and `en.ts`, and every backend
  message goes in `backend/app/i18n/{es,en}.py`.
- No live AI (fake provider only).
- No customer names (use `facturas`, `origen_ventas`, `bi_ventas`).
- Code first, test last: only focused cheap checks per task; the full suites run once at the end
  of the queue.

**Guide style for ✍ tasks**:
- Follow plan §1 body rules:
  - `# <title>`, then `## Para qué sirve` / `## Quién puede usarlo` / `## Cómo se hace` [/
    `## Opciones`] [/ `## Problemas frecuentes`];
  - the English file uses the mirrored headings in the same order;
  - ≤ 6,000 chars.
- UI labels go in **bold**, copied verbatim from that language's catalogue.
- Links are `[Abrir …](app:/ruta)` and must match a real route without `:param`.
- Say who can do something when the reader may lack the role.
- Environment variable names are allowed only in superuser topics.
- Write the es file first, then the en file with the same facts (not a loose translation).

## Phase 1: Setup

- [X] T001 ✍ Write `backend/app/assistant/guide/index.yaml` per plan §1 schema.
  - Include the 9 sections and all 52 topics of plan §2, in table order, with: `id`, `section`,
    `title {es,en}`, `summary {es,en}` (≤ 140 chars), `roles`, `routes`, `tiles`, `commands`,
    `aliases {es,en}` (3–8 each) and `related` (≤ 5).
  - Use the route, tile and command coverage maps of plan §2.
  - Covers FR-001 and FR-006.
- [X] T002 [P] Create `backend/app/assistant/guide/labels-allow.txt`, one entry per line. It holds
  bold spans that are not catalogue labels:
  - BizView;
  - spec kinds `fuente`, `integracion`, `reporte`, `distribucion`;
  - stage names until 020 puts them in the catalogue;
  - product names Claude, Telegram, Supabase, PostgreSQL, VS Code.

  Add a header comment explaining the file. Covers FR-006.
- [X] T003 [P] Move the `ENTRIES` constant out of `frontend/src/pages/admin/AdminHome.tsx`:
  - export it as `ADMIN_TILES` (same shape: `to`, `title`, `text`, `icon`, `superOnly`) from a new
    `frontend/src/pages/admin/adminTiles.ts`;
  - make `AdminHome.tsx` import it, with no visual change;
  - keep the catalogue-based titles that 022 introduced.

  Covers FR-006.
- [X] T004 [P] Create `frontend/src/lib/routeAccess.ts` with:
  - `ROUTES: {pattern, access: "public"|"user"|"admin"|"superuser"}[]` for every route in
    `frontend/src/App.tsx`. Use these access levels:
    - public: `/ingresar`, `/s/:token`
    - user: the shell routes and `/cambiar-clave`
    - admin: routes wrapped by `RequireAdmin`
    - superuser: routes wrapped by `RequireSuperuser`, including the 020 `/proyectos*` routes and
      the `/admin/asistente*` redirects
    - `*`: user
  - `matchRoute(path)`: `:param` segments match one non-empty segment; the query string and hash
    are ignored; `*` matches only when used explicitly.
  - `canOpen(path, user)`: a superuser passes admin; an admin passes user.

  Covers FR-004.
- [X] T005 [P] Add the `yaml` npm package as a devDependency in `frontend/package.json` (dev-only
  supporting library, plan Constitution Check V). Covers FR-006.

## Phase 2: Foundational (blocks all stories)

- [X] T006 Write the loader `backend/app/assistant/guide/__init__.py` per plan §3:
  - `load()` is cached and validates the schema (raises `GuideError` with file and reason).
  - `visible_roles(user)`, `topics_for(user, lang)`, `get(topic_id, lang, user|None)`.
  - `resolve(text, lang)` returns `(id|None, closest[≤3])`. It tries exact id, then
    space→hyphen, then accent- and case-insensitive title, then alias, then
    `difflib.get_close_matches`.
  - `index_text(lang)` is deterministic: a section heading, then `- id — title: summary [roles]`.
  - `prompt_block(lang)`: the rules of plan §5, with es/en text from `backend/app/i18n/`.
  - Locale fallback is `DEFAULT_LOCALE`.

  Covers FR-001, FR-002 and FR-003.
- [X] T007 Add tool `get_app_guide` to `backend/app/assistant/tools.py`:
  - a `TOOL_SPECS` entry (`topic: string|null`, description from the backend catalogue);
  - a `_dispatch` branch;
  - results per plan §4: index / topic / `{found:false, closest, note}`, in the session user's
    locale;
  - not in `DISCOVERY_TOOLS` or `MEMO_TOOLS`;
  - added to the set that `offered_tool_specs` keeps when restricted;
  - summary "Consultó la guía (<id>)" through the catalogue.

  Covers FR-002.
- [X] T008 Add `get_app_guide` to the 021 inspection tool set used by plain messages and every
  command in `backend/app/assistant/commands/registry.py`.
  - Add chip labels `assistant.tools.get_app_guide` = "Guía de la aplicación" / "App guide" in
    `frontend/src/i18n/es.ts` and `en.ts`.
  - Covers FR-002 and 021 FR-004.
- [X] T009 Add the guide to the system prompt in `backend/app/assistant/service.py`:
  - Insert `guide.prompt_block(lang)` as a `## Guía de la aplicación` block into the stable
    prefix for both languages.
  - Place it after the safety rules and before `authoring.summary()`.
  - Add no dynamic data.
  - Extend the existing byte-identical-prefix test (017 T039) so the prefix stays identical across
    two rounds with the block present.
  - Covers FR-003.
- [X] T010 Make the scope pre-check in `backend/app/assistant/commands/scope.py` treat guide
  titles and aliases (es+en, from `guide.load()`) as in-scope terms.
  - Add a focused test: 20 help questions (10 es, 10 en, e.g. "¿cómo activo el tema oscuro?",
    "how do I reset a user's password?") are never refused by the pre-check.
  - Covers FR-003 and 021 FR-007.
- [X] T011 Add the guide API `backend/app/api/guide.py` and register its router in
  `backend/app/main.py`:
  - `GET /api/guide` returns the index filtered by role in the request locale.
  - `GET /api/guide/topics/{topic_id}` returns 404 `guide_topic_not_found` when the topic is
    unknown or not visible.
  - Any signed-in user; `Cache-Control: private, max-age=300`.
  - Messages go in `backend/app/i18n/{es,en}.py`.
  - Covers FR-007.

## Phase 3: User Story 1 — Ask the agent how the app works (P1) 🎯 MVP

**Goal**: any question about an app option is answered from the guide, with exact screen names and
role-aware in-app links.

**Independent test**: `backend/tests/test_guide_answers.py` passes for every topic × {es, en};
`frontend/tests/unit/chat-links.test.tsx` passes.

- [X] T012 [P] [US1] ✍ Write topics `ingreso`, `contrasena`, `navegacion` and `roles-y-permisos` in
  `backend/app/assistant/guide/es/` and `backend/app/assistant/guide/en/`. Covers FR-001.
- [X] T013 [P] [US1] ✍ Write topics `perfil`, `apariencia-e-idioma`, `doble-factor` and `telegram`
  in `backend/app/assistant/guide/{es,en}/`. Covers FR-001.
- [X] T014 [P] [US1] ✍ Write topics `inicio-y-favoritos`, `tableros`, `ver-reporte` and
  `filtros-y-periodos` in `backend/app/assistant/guide/{es,en}/`. Covers FR-001.
- [X] T015 [P] [US1] ✍ Write topics `exportar-pdf-csv`, `actualizacion-y-modo-tv`,
  `privacidad-y-ia` and `ayuda` in `backend/app/assistant/guide/{es,en}/`. Covers FR-001 and
  FR-005.
- [X] T016 [P] [US1] ✍ Write topics `compartir-enlace`, `enviar-por-correo`, `envios-programados`
  and `correo-de-la-instalacion` in `backend/app/assistant/guide/{es,en}/`. Covers FR-001.
- [X] T017 [P] [US1] ✍ Write topics `administracion`, `usuarios`, `auditoria` and
  `confirma-tu-contrasena` in `backend/app/assistant/guide/{es,en}/`. Covers FR-001.
- [X] T018 [P] [US1] ✍ Write topics `seguridad`, `ia`, `tokens` and `instalacion-y-ajustes` in
  `backend/app/assistant/guide/{es,en}/`.
  - Security is documented at administrator level only; no bypass steps (spec edge case).
  - Covers FR-001.
- [X] T019 [P] [US1] ✍ Write topics `fuentes`, `fuente-supabase` and `reportes-directos` in
  `backend/app/assistant/guide/{es,en}/`.
  - Include a "¿Directo o integración?" decision list from 019 and constitution II.
  - Covers FR-001.
- [X] T020 [P] [US1] ✍ Write topics `integraciones`, `etl-y-transformaciones` and
  `espacio-de-trabajo` in `backend/app/assistant/guide/{es,en}/`.
  - Include versions and rollback, the spec archive, and the Polars transform stage of 005-A.
  - Covers FR-001.
- [X] T021 [P] [US1] ✍ Write topics `proyectos`, `editor-de-proyecto`, `historial-de-proyecto` and
  `aplicar-proyecto` in `backend/app/assistant/guide/{es,en}/`.
  - Use the labels as implemented by 020.
  - Covers FR-001.
- [X] T022 [US1] Create `frontend/src/lib/appLinks.ts` with:
  - `splitAppLinks(text) -> Array<{text} | {text, to}>` for `[label](app:/path)`;
  - `resolveAppLink(to, user)` using `matchRoute` and `canOpen` from
    `frontend/src/lib/routeAccess.ts`.

  Covers FR-004.
- [X] T023 [US1] Create `frontend/src/components/assistant/ChatText.tsx`:
  - plain text with `whitespace-pre-wrap`;
  - allowed app links → react-router `<Link>` (accent, underline, `ArrowUpRight` with
    `aria-hidden`, touch-friendly padding);
  - disallowed or unknown links → label text only;
  - other schemes → literal;
  - collapse the docked panel below `lg` on click (`AssistantPanelContext`).

  Use it for assistant messages in `frontend/src/components/assistant/AssistantChat.tsx`; user
  messages stay literal. Covers FR-004.
- [X] T024 [US1] Focused tests:
  - `frontend/tests/unit/chat-links.test.tsx`:
    - superuser + `app:/admin/fuentes` → anchor;
    - user role + `app:/admin/fuentes` → plain text;
    - `app:/no-existe` → plain text;
    - `[x](https://…)` → literal.
  - `backend/tests/test_guide_answers.py`, parametrised over every topic × {es, en}, with the fake
    provider scripted to call `get_app_guide(<id>)` and reply with the topic's first bold label and
    first `app:` link. Assert:
    - the tool result body equals the file;
    - the chip label is in the session language;
    - the stored answer contains the link.

    Also: an unknown topic returns `found: false` with `closest`.

  Covers US1 AC1–AC3 and FR-002.

## Phase 4: User Story 2 — Learn the Spec Kit way of working (P1)

**Goal**: `/ayuda` shows the method, the commands and examples at zero provider cost; method
questions are answered from the guide.

**Independent test**: `/ayuda` without arguments makes 0 provider calls and finishes in < 200 ms,
listing every registry command; `/ayuda reporte directo` resolves the topic.

- [X] T025 [P] [US2] ✍ Write topics `chat-del-agente`, `alcance-del-agente` and `metodo-spec-kit`
  in `backend/app/assistant/guide/{es,en}/`. Covers FR-001.
- [X] T026 [P] [US2] ✍ Write topics `comandos-especificar`, `comandos-planificar`,
  `comandos-construir` and `tipos-de-spec` in `backend/app/assistant/guide/{es,en}/`.
  - Follow the files-per-command table of 021 FR-003.
  - Covers FR-001.
- [X] T027 [P] [US2] ✍ Write the fixed `/ayuda` templates `backend/app/assistant/guide/es/_ayuda.md`
  and `backend/app/assistant/guide/en/_ayuda.md`.
  - Content: a method paragraph and the flow line, then the placeholders `{commands}`,
    `{examples}` (3 examples, including "Reporte directo sobre la tabla bi_ventas, sin ETL"),
    `{next_steps}` and `{help_link}`.
  - Covers FR-005.
- [X] T028 [P] [US2] ✍ Write the `/ayuda` command prompt
  `cli/bizview_cli/workspace_template/agent_commands/es/ayuda.md` and its `en/ayuda.md` (create
  them, or complete the 021 placeholder).
  - "Answer the resolved topic from the guide; use `get_app_guide` for related topics; if no topic
    matches, say so and offer the closest ones; never change files."
  - Covers FR-005.
- [X] T029 [US2] Create `backend/app/assistant/guide/ayuda.py`:
  - `fixed_reply(session, lang) -> str` renders `_ayuda.md`:
    - `{commands}` from the 021 registry, in registry order, with descriptions in `lang` and args
      hints;
    - `{next_steps}` from `overview.next_steps(project)` when there is a project (empty otherwise;
      until T033 lands, an empty string);
    - `{help_link}` = `[Abrir la Ayuda](app:/ayuda)` (en: "Open Help").
  - `topic_block(args, lang)` → `Tema resuelto: <id>` + topic body, or the closest list.

  Covers FR-005.
- [X] T030 [US2] Wire `/ayuda` in `backend/app/assistant/service.py` and the 021 registry
  `backend/app/assistant/commands/registry.py`:
  - Registry entry: `handler "ayuda"`, `writable_paths []`, inspection tools.
  - With empty arguments: store the user message and the fixed reply (`command "/ayuda"`, tokens
    0), record a command run with status `completado` and no files, and return 200. No provider
    call, no thread, no claim.
  - With arguments: a normal command run with the `ayuda.md` prompt + `topic_block`.

  Covers FR-005 and US2 AC1–AC2.
- [X] T031 [US2] Focused tests in `backend/tests/test_guide_answers.py`:
  - `/ayuda` without arguments:
    - the fake provider records 0 calls;
    - tokens stay unchanged;
    - the reply contains every registry command and 3 examples in the session language;
    - it finishes in < 200 ms (SC-003).
  - `/ayuda reporte directo` → the prompt sent to the fake provider contains
    `Tema resuelto: reportes-directos`.
  - `/ayuda` in a project with a spec at stage Planificada → `{next_steps}` names
    `/speckit-tasks`.

  Covers FR-005 and SC-003.

## Phase 5: User Story 3 — Explain a concrete project (P2)

**Goal**: "explícame este proyecto", "¿qué falta?" and "¿por qué es directo?" are answered from the
project's files, with cited lines and no data values.

**Independent test**: on a synthetic project (fuente + direct reporte + distribucion specs),
`get_project_overview` returns the plan §7 payload, the right next commands and decision lines,
with no recipient address or host in it.

- [X] T032 [P] [US3] ✍ Write topics `estructura-de-proyecto`, `proyectos-en-vs-code`,
  `definir-una-integracion` and `definir-un-reporte` in `backend/app/assistant/guide/{es,en}/`.
  Covers FR-001.
- [X] T033 [P] [US3] ✍ Write topics `distribuciones`, `recorrido-integracion-a-distribucion` and
  `recorrido-reporte-directo` in `backend/app/assistant/guide/{es,en}/`.
  - The direct path must be a complete step list that a first-time super user can follow (SC-004).
  - Covers FR-001.
- [X] T034 [US3] Create `backend/app/assistant/overview.py`:
  - `build(db, project) -> dict` per plan §7, from the 020 project folder (`projects/fs.py`) and
    the stage/status functions (`projects/service.py`, `projects/history.py`) plus the catalogue.
    The catalogue provides name, kind, exists, last test ok and direct-reports flag — never
    connection fields.
  - `decisions`: 1-based `spec.md` lines matching `**Tipo**:`, `**Modo**:`, `**Fuente**:`,
    `**Tablas**:`, `**Mantiene**:`, `**Volumen**:` or `**Datos personales**:`, each text ≤ 200
    chars.
  - `next_command` / `next_action` follow the plan §7 table, including the `fuente`-spec
    `app:/admin/fuentes/nueva` action.
  - Recipients appear only as `{users: n, roles: [...]}`.
  - 20,000-char cap with counts.
  - `next_steps(project)` (≤ 5 lines).

  Covers FR-008 and US2 AC3.
- [X] T035 [US3] Add tool `get_project_overview()` (no arguments; the conversation's project):
  - in `backend/app/assistant/tools.py`: a `TOOL_SPECS` entry and a `_dispatch` branch;
    `ToolError` "La conversación no tiene proyecto." comes from the backend catalogue; the tool is
    not discovery;
  - add it to the inspection set in `backend/app/assistant/commands/registry.py`;
  - add chip labels `assistant.tools.get_project_overview` = "Resumen del proyecto" / "Project
    overview" in `frontend/src/i18n/es.ts` and `en.ts`.

  Covers FR-008 and US3 AC1–AC2.
- [X] T036 [US3] Focused tests in `backend/tests/test_project_overview.py`, using a synthetic
  project in a temporary `PROJECTS_DIR` and `app_test_*` schema with three specs:
  - `001-fuente-origen-ventas`: source exists, test passed;
  - `002-reporte-ventas-directo`: `**Modo**: directo`, stage Planificada;
  - `003-envio-semanal`: a distribution with recipient `ana@example.com` and role `admin`.

  Assert:
  - the stages;
  - `next_command` = `/speckit-tasks` for 002;
  - the `decisions` line number of `**Modo**:`;
  - the recipients are `{users: 1, roles: ["admin"]}`;
  - the JSON payload contains neither `ana@example.com` nor the source host;
  - the cap trims long lists with counts.

  Covers FR-008 and constitution VIII.

## Phase 6: Ayuda page for every role (FR-007)

**Independent test**: as a Usuario, `/ayuda` lists only topics with role `user` or `public`, search
filters by title, `?tema=` opens a topic, and links to admin screens render as plain text.

- [X] T037 Give 020's `frontend/src/components/ide/MarkdownView.tsx` an optional
  `resolveLink(href) -> string | null` prop:
  - `app:` hrefs → react-router `<Link>` when resolved, else plain text;
  - other schemes → plain text (in the Ayuda context);
  - no behaviour change when the prop is absent.

  Covers FR-004 and FR-007.
- [X] T038 Create the page `frontend/src/pages/Help.tsx` per plan §9:
  - header **Ayuda**;
  - search **Buscar en la ayuda** (accent- and case-insensitive on title and summary);
  - list grouped by section;
  - topic view through `?tema=<id>` with `MarkdownView` + `resolveLink` (`resolveAppLink`),
    **Temas relacionados** and **← Volver**;
  - superuser-only **Preguntar al asistente**, which opens the panel with `/ayuda <id>` in the
    composer;
  - empty and error states;
  - layout: list → topic on phones, two columns from `lg`;
  - no modal.

  Add API types to `frontend/src/api/types.ts`. Covers FR-007.
- [X] T039 Navigation changes:
  - add the route `ayuda` (inside `RequireAuth` + `AppShell`) to `frontend/src/App.tsx`;
  - add the entry `/ayuda` with access user to `frontend/src/lib/routeAccess.ts`;
  - add **Ayuda** after **Perfil** in the desktop sidebar and the **Menú de cuenta** in
    `frontend/src/components/AppShell.tsx` (the phone bottom bar is unchanged);
  - add the keys `nav.help` and `help.{title, subtitle, search, searchPlaceholder, noMatch, related,
    back, askAssistant, loadFailed}` to `frontend/src/i18n/es.ts` and `en.ts`.

  Covers FR-007.
- [X] T040 Focused tests:
  - `frontend/tests/unit/help-page.test.tsx`:
    - a role-filtered list from a mocked API;
    - search narrows the list and shows the no-match text;
    - `?tema=` renders the body;
    - the back link;
    - an `app:/admin/fuentes` link is plain text for a Usuario;
    - no `role="dialog"`.
  - `backend/tests/test_guide_api.py`:
    - Usuario, Administrador and Superusuario each see their own topic sets;
    - `GET /api/guide/topics/seguridad` as a Usuario → 404;
    - English locale → English titles.

  Covers FR-007.

## Phase 7: Drift checks (FR-006, SC-001)

- [X] T041 Write `backend/tests/test_guide.py` (no DB), with plan §10 backend checks 1–6:
  - schema;
  - es/en files and no orphans;
  - `_ayuda.md` placeholders;
  - heading parity and the 6,000-char cap;
  - env-var names only in superuser topics;
  - registry commands ↔ topic `commands`;
  - `index_text` deterministic and ≤ 8,000 chars;
  - `prompt_block` present in the system prefix for es and en.

  Covers FR-006 and FR-001.
- [X] T042 Write `frontend/tests/unit/guide-drift.test.ts`, with plan §10 frontend checks 1–5,
  reading `frontend/src/App.tsx`, `frontend/src/pages/admin/adminTiles.ts`,
  `frontend/src/lib/routeAccess.ts`, `backend/app/assistant/guide/index.yaml` (with `yaml`),
  `backend/app/assistant/guide/{es,en}/*.md` and `labels-allow.txt`:
  - routes ↔ topic `routes`, in both directions;
  - tiles ⊆ topic `tiles`;
  - `ROUTES` equals the App.tsx guards;
  - every `app:` link is valid, parameter-free and openable by the topic's roles;
  - every bold label is in the same language's catalogue, a static prefix of a catalogue function,
    or the allow-list.

  Each failure message names the item and the fix. Covers FR-006 and SC-001.
- [X] T043 ✍ Fix the guide content and `index.yaml` until T041 and T042 pass. Run only these two
  tests (focused check), and record any label renamed in the catalogues.
  - Covers FR-006 and FR-003.

## Phase 8: Polish & Cross-Cutting

- [X] T044 [P] ✍ Write the live eval set `backend/tests/live/guide_eval.yaml`: 50 questions,
  25 es + 25 en, in the plan §12 format and mix:
  - ≥ 1 question per section;
  - 6 on the method and commands;
  - 6 `overview` questions on the synthetic project `facturas-demo`;
  - 4 `unknown`;
  - 4 `restricted`;
  - the rest `answer`.

  Generic names only. Covers SC-002.
- [X] T045 Write `backend/tests/live/test_guide_eval.py`:
  - skipped unless `AI_LIVE_TESTS=1`; uses the `AI_LIVE_*` variables of `test_agent_eval.py`;
  - seeds the synthetic `facturas-demo` project in an `app_test_*` schema and a temporary
    `PROJECTS_DIR`;
  - runs each question as a superuser in its language;
  - scores deterministically: expected tool/topic called, `must_include` / `must_not_include`,
    `app:` links matching the union of `index.yaml` routes, required link present;
  - prints a per-question table and token use;
  - asserts ≥ 45/50.

  Covers SC-002.
- [X] T046 [P] Write `specs/023-chat-app-guide/quickstart.md`:
  - prerequisites;
  - how to run the drift tests (`uv run pytest tests/test_guide.py`,
    `npm test -- guide-drift`) and the opt-in eval;
  - the manual usability check for SC-004: a first-time super user, a timer, the task "crear un
    reporte directo sobre una tabla existente" guided only by the chat, a < 10 min target, and
    what to record.

  Covers SC-004 and SC-001.
- [X] T047 [P] Docs:
  - `README.md`: a "Ayuda y guía del agente" paragraph;
  - `docs/VIBE-REPORTING.md`: a pointer to `/ayuda` and the guide topics;
  - `CHANGELOG.md`: an entry (guide, `get_app_guide`, `get_project_overview`, `/ayuda`, Ayuda page,
    drift test);
  - a contributor note in `backend/app/assistant/guide/README.md`: how to add a topic, plus the
    style rules of plan §1.

  Covers FR-001.
- [X] T048 Full backend, CLI and frontend suites, deferred to the end of the whole 019–023 queue and
  run once, detached (backend on `DATABASE_URL_BI` in `app_test_*` schemas; no live AI); then
  `/speckit-converge` for 023.

## Dependencies & Execution Order

- **Setup (T001–T005)**:
  - T001 first: the loader, the tests and the content all depend on it.
  - T002–T005 can run in parallel.
- **Foundational (T006–T011)**:
  - T006 needs T001.
  - T007–T011 each need T006.
  - T008 and T030/T035 edit the same registry file: run them in order T008 → T030 → T035.
  - T009 needs T006.
  - T010 needs T006.
- **US1**:
  - The content tasks T012–T021 are independent of each other and can run in parallel (different
    files). They need T001.
  - T022 needs T004.
  - T023 needs T022.
  - T024 needs T007, T012–T021 and T023.
- **US2**:
  - T025–T028 can run in parallel.
  - T029 needs T006 and T027.
  - T030 needs T029 and T008.
  - T031 needs T030.
- **US3**:
  - T032 and T033 can run in parallel.
  - T034 needs the 020 project services.
  - T035 needs T034 and T030 (registry order).
  - T036 needs T035.
  - T029's `{next_steps}` gets its data once T034 exists.
- **Ayuda page**:
  - T037 needs 020's MarkdownView.
  - T038 needs T011, T022 and T037.
  - T039 needs T038 and T004.
  - T040 needs T039.
- **Drift**:
  - T041 needs all content tasks (T012–T021, T025–T027, T032–T033) and T030.
  - T042 needs T003, T004, T005, T039 and all content.
  - T043 needs T041 and T042.
- **Polish**:
  - T044 and T046–T047 can run in parallel after T043.
  - T045 needs T044 and T035.
  - **T048 is last**.

## Parallel opportunities

- The 16 ✍ content tasks (T012–T021, T025–T028, T032–T033; 52 topics + `/ayuda` texts) are independent of each other: Claude
  drafts them in parallel batches while DeepSeek builds T006–T011.
- T022/T023 (chat links) and T034 (overview) touch different files and can run alongside the
  content.

## MVP

Phase 1 + Phase 2 + Phase 3 (US1): grounded answers about every screen, with role-aware links.

Then come US2 (`/ayuda`), US3 (project explanation), the Ayuda page and the drift checks.

## Phase 9: Convergence

- [X] T049 Make `get_project_overview` return actionable `next_action` values in `backend/app/assistant/overview.py`: for `fuente` specs with a missing or untested source, return the readable action ("Crear o probar la fuente en Administración → Fuentes de datos" / en mirror) plus the in-app link `app:/admin/fuentes/nueva` (reuse `source_missing.link` from `projects/specs.py:list_specs`, which `_spec_item` currently drops); return "Aplicar proyecto" / "Apply project" instead of the bare keys `source`/`apply`; add the `/speckit-analyze` hint for stage Tareas; extend `backend/tests/test_project_overview.py` per FR-008, plan §7 next_command table, T034 (partial)
- [X] T050 Move the hard-coded 023 backend texts into `backend/app/i18n/{es,en}.py`: the `get_app_guide` and `get_project_overview` tool descriptions in `backend/app/assistant/tools.py` (Spanish-only literals), the `/ayuda` link labels `HELP_LINK` in `backend/app/assistant/guide/ayuda.py`, and `NEXT_ACTIONS` plus the "Qué sigue en / What is next in" heading in `backend/app/assistant/overview.py` per plan §4, plan §9 Backend catalogue, T007, tasks.md rules (partial)

## Closure 2026-10-12

T049 and T050 are implemented (actionable `next_action` values with in-app links in
`backend/app/assistant/overview.py`; every 023 backend text, including the `get_app_guide` and
`get_project_overview` tool descriptions, lives in `backend/app/i18n/{es,en}.py`) and covered by
`backend/tests/test_project_overview.py` and `test_guide_answers.py`. Feature closed: backend,
CLI, frontend and e2e suites green.
