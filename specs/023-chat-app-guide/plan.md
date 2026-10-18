# Implementation Plan: The agent explains the app, Spec Kit and projects

**Branch**: `023-chat-app-guide` | **Date**: 2026-10-08 | **Spec**: [spec.md](./spec.md)

## Summary

Ship a bilingual app guide with the product: one Markdown file per topic and language in
`backend/app/assistant/guide/{es,en}/<topic>.md`, plus an `index.yaml` with the metadata for each
topic (titles, summaries, roles, routes, Administración tiles, commands, aliases, related topics).
The guide covers every screen and option, the Spec Kit method, spec kinds, the project layout and the
two end-to-end paths.

Two new read-only tools ground the agent:
- `get_app_guide(topic?)` returns the guide index or one topic.
- `get_project_overview()` returns a metadata summary of the current project.

The stable system-prompt prefix carries the guide index and the rule to answer app questions from
the guide only.

`/ayuda` without arguments is answered by product code with no provider call. `/ayuda <tema>` runs
as a normal command with the matching topic already loaded.

Answers may hold `[texto](app:/ruta)` links. The chat shows them as router links and drops any link
the user's role cannot open.

Every role can read the same guide on a new page, "Ayuda" (`/ayuda`), filtered by role and
searchable by title.

A drift test fails when any of these has no guide topic: a route in `App.tsx`, an Administración
tile, or a command in the 021 registry. It also fails when a guide link points to a route that does
not exist, or when a bold UI label is missing from that language's catalogue.

There is no migration and no new stack component.

## Technical Context

- **Backend**: Python 3.12, FastAPI, PyYAML (already present through `bizview-cli`).
- **Frontend**: React 19, Tailwind, react-router.
- **Builds on**:
  - 017 agent loop: `backend/app/assistant/service.py` `SYSTEM_PREFIX` + `## Estado` context;
    `tools.py` `TOOL_SPECS` / `_dispatch` / `offered_tool_specs`.
  - 020 projects: `backend/app/projects/{fs,service,history}.py`, stage derivation, the
    `MarkdownView` component, and the `/proyectos*` routes.
  - 021 commands: `backend/app/assistant/commands/{registry,scope}.py`, command prompts in
    `cli/bizview_cli/workspace_template/agent_commands/{es,en}/`, and `CommandMenu.tsx`.
  - 022 i18n: `frontend/src/i18n/{es,en}.ts` + `useT()`, `backend/app/i18n/`, and the
    request-locale dependency.
- **Implementation order**: 019 → 005-A → 022 → 020 → 021 → 023, so every interface above exists
  when 023 starts. Where 020/021/022 chose different names than this plan, the tasks follow the
  names in the code.
- **Today's chat rendering**: assistant messages are plain text (`whitespace-pre-wrap` in
  `components/assistant/AssistantChat.tsx`, lines 223–236), so link rendering must be added.
- **Today's Administración tiles**: `ENTRIES` is a constant private to `pages/admin/AdminHome.tsx`,
  so it must be exported for the drift test.
- **Tests**:
  - Backend pytest: pure-file tests with no DB, and API tests on `DATABASE_URL_BI` in `app_test_*`
    schemas.
  - Fake provider for all agent tests. The live eval runs only with `AI_LIVE_TESTS=1`.
  - Frontend: Vitest unit tests (the drift test reads the repository files).
- **Performance**:
  - The guide is loaded once per process (cached).
  - The index text is ≤ 8,000 chars (≈ 2k tokens, inside the cached prefix).
  - A topic body is ≤ 6,000 chars.
  - `/ayuda` with no arguments takes under 200 ms (SC-003).

## Constitution Check (2.0.0)

- **I (mobile-first)**:
  - The Ayuda page starts from the 375 px layout (list → topic view with "← Volver"; two columns
    from `lg`).
  - Links in the docked chat collapse the panel on phones after navigating.
  - Dark-mode tokens only; WCAG AA.
- **IV (folders)**: the guide is product documentation versioned with the backend code that serves
  it (`backend/app/assistant/guide/`). The `/ayuda` command prompt lives with the other command
  prompts in `cli/bizview_cli/workspace_template/agent_commands/` (021 single source). No customer
  content.
- **V (stack)**: no new stack component. Markdown is rendered with 020's `MarkdownView` (020 lists
  its library). Backend YAML uses PyYAML, already installed with the CLI.
- **Supporting library (dev only)**: `yaml` (npm, devDependency). The Vitest drift test uses it to
  read `index.yaml`; the frontend has no YAML parser today. It is not shipped in the bundle.
- **VII (one product)**: the examples in the guide use generic names (`facturas`, `origen_ventas`,
  `bi_ventas`). There are no customer names, and no hosts or credentials, only placeholders.
- **VIII (AI optional and private)**:
  - The Ayuda page and `/ayuda` without arguments work with AI off. Without AI, the chat itself
    stays unavailable (014).
  - `get_app_guide` returns product-authored text only.
  - `get_project_overview` returns project-file metadata and catalogue status:
    - **it returns**: spec titles, kinds and stages, artifact ids, metric/view ids, schedules,
      source names/kinds/test result, recipient **counts and role names**, and spec line
      references;
    - **it never returns**: source rows, credentials, connection details, user names or email
      addresses.
  - Tool inputs are documented below. A test seeds an e-mail recipient and a source host and
    asserts that neither appears in the payload.
  - Local models work: index plus tool, with no fine-tuning.
- **IX (spec-driven, BI-only)**:
  - Questions about using BizView are inside the BI scope (021 FR-007). The scope pre-check gets
    the guide aliases as in-scope terms, so help questions are never refused.
  - Both new tools are read-only, and `/ayuda` writes no files (021 FR-003: empty write list).
  - The agent explains the method and points to the next command; it never runs one on its own.
- **Constraints**:
  - Every guide topic exists in Spanish and English (parity test).
  - The Ayuda page and new chat strings are in both catalogues.
  - There are no modals: the Ayuda page is a routed page, and topic details are a view inside it.
- **Security**:
  - Topics are filtered server-side by role. A user cannot fetch a superuser topic (404).
  - The `seguridad` and `confirma-tu-contrasena` topics document controls only at the
    administrator level.
  - The system prompt forbids explaining how to bypass two-step sign-in, step-up or the security
    profile.
  - Only the `app:` scheme becomes a link in chat answers, which blocks phishing links written by a
    model.

→ PASS (no amendment, no Complexity Tracking entry).

## Design

### 1. Guide layout (`backend/app/assistant/guide/`)

```
backend/app/assistant/guide/
  __init__.py          # loader, role filter, index text, topic lookup/resolve (code)
  ayuda.py             # fixed /ayuda reply (code)
  index.yaml           # metadata of every topic (content)
  labels-allow.txt     # bold spans that are not catalogue labels (e.g. product names, env vars)
  es/<topic>.md  en/<topic>.md      # one body per topic and language (content)
  es/_ayuda.md   en/_ayuda.md       # fixed /ayuda template (content)
```

The backend image copies `backend/` as a whole (`backend/Dockerfile`), so the guide ships with
each release and answers match the installed version (spec edge case).

**`index.yaml` schema** (validated by the loader and by `test_guide.py`):

```yaml
version: 1
sections:                          # display order of the Ayuda page and the index text
  - id: primeros-pasos
    title: {es: "Primeros pasos", en: "Getting started"}
topics:                            # order = order inside its section
  - id: filtros-y-periodos         # ^[a-z][a-z0-9-]{1,48}$, unique, = file name
    section: tableros              # must exist in sections
    title:   {es: "Filtros y períodos", en: "Filters and periods"}
    summary: {es: "…≤140 chars…", en: "…≤140 chars…"}
    roles: [user]                  # who can use what the topic documents: public|user|admin|superuser
    routes: ["/r/:id"]             # App.tsx route patterns this topic documents (may be empty)
    tiles: []                      # Administración tile targets documented here
    commands: []                   # registry command names documented here (e.g. "/speckit-plan")
    aliases: {es: ["filtro", "período", "comparar"], en: ["filter", "period", "compare"]}
    related: [ver-reporte, exportar-pdf-csv]   # existing topic ids, ≤ 5
```

- **Role visibility**: a viewer's effective roles are
  - user → {public, user}
  - admin → {public, user, admin}
  - superuser → {public, user, admin, superuser}

  A topic is visible when its `roles` intersect the viewer's effective roles. The chat is
  super-user only (014), so the chat sees every topic, and role filtering matters for the Ayuda
  page and for links.
- **Role names in text**: the roles come from the catalogue — Usuario / Administrador /
  Superusuario, and "sin cuenta" (public).

**Body rules** (checked by tests where marked ✓):
- Start with `# <title>` (✓ matches `index.yaml`).
- Then `##` sections in this order:
  1. "Para qué sirve" / "What it is for"
  2. "Quién puede usarlo" / "Who can use it"
  3. "Cómo se hace" / "How to"
  4. optionally "Opciones" / "Options"
  5. optionally "Problemas frecuentes" / "Common problems"

  ✓ es and en have the same `##` count and order.
- ≤ 6,000 chars (✓).
- UI labels are written in **bold** exactly as the catalogue of that language shows them. ✓ Every
  bold span is a catalogue value, or the static prefix of a catalogue function, or listed in
  `labels-allow.txt`.
- In-app links use `[Abrir Administración → Fuentes de datos](app:/admin/fuentes)`. ✓ A link must
  - match a route pattern;
  - contain no `:param`;
  - be openable by at least one of the topic's roles.
- No credentials, hosts or customer names. Environment variable names appear only in superuser
  topics (✓ a regex for `[A-Z_]{4,}=` is used only in topics whose roles = [superuser]).
- Say who can do something when the reader may not have the role ("Solo el **Superusuario** puede…")
  — US1 AC2.

### 2. Complete topic list (52 topics, 9 sections)

**Roles key**:
- P = public (no account)
- U = Usuario
- A = Administrador
- S = Superusuario

Routes reflect `App.tsx` after 020 (`/proyectos*`, with `/admin/asistente*` kept as redirects) and
after 023 (`/ayuda`).

| # | Topic id | Section | Screens / routes / features covered | Roles |
|---|----------|---------|-------------------------------------|-------|
| 1 | `ingreso` | primeros-pasos | `/ingresar`: correo + contraseña, **Ingresar**, bloqueo tras 5 intentos (15 min), throttle por dirección, "¿Olvidaste tu contraseña?", paso de **Verificación en dos pasos** / **Usar un código de recuperación**, botón **Ingresar con Telegram**, sesión vencida (7 días inactiva / 30 días), selector de idioma en ingreso (022) | P, U |
| 2 | `contrasena` | primeros-pasos | `/cambiar-clave`: **Cambiar contraseña**, contraseña temporal (**Crea tu contraseña**), reglas (10–128, sin el correo, distinta), otras sesiones se cierran | U |
| 3 | `navegacion` | primeros-pasos | menú lateral y barra inferior (**Inicio**, **Tableros**, **Administración**, **Perfil**, **Proyectos**, **Ayuda**), **Menú de cuenta**, vistas en lugar de ventanas emergentes (atrás = cancelar), **Código fuente** y versión (AGPL); `/no-autorizado` (**No autorizado**), `*` (**Página no encontrada**) | U |
| 4 | `roles-y-permisos` | primeros-pasos | qué hace **Usuario** / **Administrador** / **Superusuario**; tableros asignados; a quién pedir acceso; superusuario único (no se desactiva) | U |
| 5 | `privacidad-y-ia` | primeros-pasos | IA opcional; narrativa IA en reportes solo con cifras agregadas; qué nunca se envía; modelo local; el agente ve estructura, no filas | U |
| 6 | `ayuda` | primeros-pasos | `/ayuda` page (búsqueda, temas por rol) and command `/ayuda` `[tema]`; how to ask the agent | U · command `/ayuda` |
| 7 | `perfil` | cuenta | `/perfil`: **Mi perfil** (nombre, correo, rol), **Seguridad** → **Cambiar contraseña**, tarjetas de doble factor y Telegram, **Cerrar sesión** | U |
| 8 | `apariencia-e-idioma` | cuenta | **Apariencia** (**Sistema** / **Claro** / **Oscuro**, botón del encabezado), **Idioma** (Español / English / Idioma del navegador, 022), qué no se traduce (contenido escrito en specs) | U |
| 9 | `doble-factor` | cuenta | `/seguridad/doble-factor`: **Configura la verificación en dos pasos**, QR / clave manual, **Activar**, códigos de recuperación (**Descargar .txt**, **Ya los guardé**), **Generar nuevos códigos de recuperación**, **Desactivar**; obligatoria para administradores en perfil internet; **Restablecer doble factor** (S para otros) | U, A, S |
| 10 | `telegram` | cuenta | **Vincular Telegram** / **Desvincular** (Perfil); **Ingresar con Telegram**; S: Seguridad → **Ingreso con Telegram** (**Nombre del bot**, **Credencial del bot**, **Probar**, **Activar ingreso con Telegram**); A: **Quitar vínculo de Telegram**; Telegram no es segundo factor | U, A, S |
| 11 | `inicio-y-favoritos` | tableros | `/`: saludo, contadores (A/S), **Favoritos**, **Recientes**, **Ver todos los tableros**, sin tableros asignados | U |
| 12 | `tableros` | tableros | `/tableros`: **Buscar tablero**, **Vista de tarjetas** / **Vista de tabla**, favoritos (estrella), **Próximamente**; `/d/:code` (enlace a un tablero, **No autorizado**, **Tablero no encontrado**) | U |
| 13 | `ver-reporte` | tableros | `/r/:id`: KPIs, comparación ("Nuevo" con base cero), tendencia, ranking, tablas, **Parámetros del reporte** (**Período**, **Comparado con**, **Datos actualizados**, **Consultado por**), menú de tarjeta (**Opciones de …**), narrativa IA, "Datos en vivo" y datos de respaldo de reportes directos (019) | U |
| 14 | `filtros-y-periodos` | tableros | **Filtros y controles**: **Período** (Hoy … **Personalizado**, **Desde** / **Hasta**), **Comparar con**, **Filtros** (multiselección, 200 coincidencias), **Aplicar filtros**, **Limpiar todo**, cambios sin aplicar, **Filtros activos**, parámetros en la URL, botón **Filtros (n)** en teléfono | U |
| 15 | `exportar-pdf-csv` | tableros | **Exportar** (**Formato** PDF/CSV, **Generar reporte**), **Descargar PDF**, **Descargar CSV** por tarjeta (`;`, UTF-8 BOM), exporta la selección aplicada | U |
| 16 | `actualizacion-y-modo-tv` | tableros | **Actualización automática** (**Desactivada**, **Al llegar datos nuevos**, **Cada 1/5/15/60 min**), "Sin conexión — reintentando", **Modo TV**, **Pantalla completa**, **Salir del modo TV** / Esc; directos = cada `cache_seconds` | U |
| 17 | `compartir-enlace` | compartir | **Compartir** → **Compartir tablero**: **Vigencia (días)** 1–90, **Nota (opcional)**, **Crear enlace** (se muestra una vez), **Enlaces activos**, **Revocar**, máximo por tablero, origen del enlace; `/s/:token` vista compartida (**Vista compartida · vence el …**, filtros, enlace vencido) | A, P |
| 18 | `enviar-por-correo` | compartir | **Enviar por correo**: **Destinatarios**, **Correo externo** (dominios permitidos), **Asunto**, **Mensaje (opcional)**, **Adjuntar PDF…**, **Incluir enlace** (A), **Días de vigencia del enlace**, **Envíos** y estados, límites (20 destinatarios, 30 envíos/h, PDF 10 MB) | U, A |
| 19 | `envios-programados` | compartir | **Envíos programados**: **Nuevo envío programado**, **Frecuencia** (**Diario** / **Semanal** / **Mensual**), **Hora**, **Día de la semana**, **Día del mes** 1–28, **Período a enviar**, **Adjuntar PDF**, **Pausar** / **Reanudar** / **Editar** / **Eliminar**, zona horaria; envíos de un proyecto (spec `distribucion`) vs a mano | A |
| 20 | `administracion` | administracion | `/admin`: hub **Administración**, qué tarjetas ve cada rol | A, S |
| 21 | `usuarios` | administracion | `/admin/usuarios` (buscar, filtros **Rol** / **Estado**), `/admin/usuarios/nuevo` (**Nuevo usuario**, **Contraseña temporal**, **Generar**, **Crear usuario**, **Usuario creado** una vez), `/admin/usuarios/:id` (**Datos**, **Acceso a tableros**, **Desactivar usuario** / **Reactivar usuario**, **Restablecer contraseña**, **Restablecer doble factor** (S), **Quitar vínculo de Telegram**); solo S gestiona administradores; tile `/admin/usuarios` | A, S |
| 22 | `auditoria` | administracion | `/admin/auditoria`: eventos, **Tipo de evento**, **Cargar más**, 12 meses; tile | S |
| 23 | `confirma-tu-contrasena` | administracion | step-up **Confirma tu contraseña** (5 min) before sensitive actions: sources, roles, 2FA, apply, tokens, Telegram, direct-report flag, Aplicar proyecto, Retirar del espacio | A, S |
| 24 | `seguridad` | administracion | `/admin/seguridad`: **Perfil privado** / **Perfil internet** (`SECURITY_PROFILE`, automático/configurado), list of checks and "Requiere atención", aviso `DATABASE_URL_ORIGIN`, direct reads per source (019), Telegram card; tile | S |
| 25 | `ia` | administracion | `/admin/ia`: **Inteligencia artificial** (**Estado**, **Proveedor**, **Modelo**, **Clave de API** Configurada/No configurada, **Tiempo máximo**), **Probar conexión** and the reasons it can fail, **Cómo activarla** (Claude, modelo local), privacy; tile | S |
| 26 | `tokens` | administracion | `/admin/tokens`: **Tokens de acceso** for `bizview describe`, **Nuevo token** (**Nombre**, **Vence en (días)**), copy once, revoke, audited; tile | S |
| 27 | `fuentes` | datos | `/admin/fuentes` (**Fuentes de datos**, estados **Sin probar** / **Conectada** / **Error** / **Deshabilitada** / **Importada: revisa**), `/admin/fuentes/nueva` + `/admin/fuentes/:id` (**Tipo de fuente** PostgreSQL / SOAP / REST / Supabase, **Conexión**, TLS modes, auth kinds, headers, **Probar conexión**, **Habilitada**, **Eliminar fuente**, write-only credentials, internet profile = TLS only, blocked addresses); tile | S |
| 28 | `fuente-supabase` | datos | Supabase: URL del proyecto (`…/rest/v1` también), service key recomendado de solo lectura, solo GET, sin conciliación, una vista para lógica con varias tablas | S |
| 29 | `reportes-directos` | datos | reporte directo vs integración; source `bi` (`DIRECT_REPORTS_BI`), **Permitir reportes directos** (PostgreSQL, step-up), product tables refused, cache, "Datos en vivo · …", stale data, "La fuente está ocupada", structure changed, Modo Dataset/Directo in Espacio de trabajo | S (U sees live marks) |
| 30 | `integraciones` | datos | `/admin/integraciones`: estados **Activa** / **Pausada** / **Ejecutando**, **Próxima ejecución**, **Última carga correcta**, **Pausar** / **Reanudar**, **Ejecutar ahora**, **Carga completa**, **Detener**, **Cambiar frecuencia** (presets, **Expresión cron** ≥ 5 min, **Horario permitido**, **Recarga completa**, **Usar la programación del spec**), **Historial** (Programada / Manual / Completa, **Correcta** / **Falló** / **Omitida** / **En curso**, path copy / copy+polars / rows+polars), **Fuente deshabilitada**; tile | S |
| 31 | `etl-y-transformaciones` | datos | how an integration runs: extraction (COPY for PostgreSQL, requests for REST/SOAP/Supabase), incremental window vs full, Polars transform stage (005-A, `batch_rows`, `TRANSFORM_MAX_ROWS`), load into `ds_<integration>`, checks keep previous data on failure, idempotent re-runs | S |
| 32 | `espacio-de-trabajo` | datos | `/admin/espacio`: **Carpeta montada** (Git workspace), **Validar**, **Aplicar**, **Versión activa** / **Versión anterior**, Nuevos / Modificados / Retirados, **Volver a la versión anterior**, **Especificaciones** (**Especificación** / **Plan** / **Tareas**, grouped by project — 020 FR-015), report mode; tile | S |
| 33 | `proyectos` | proyectos | `/proyectos`: **Nuevo proyecto** (nombre, slug), list (specs, estado **Borrador** / **Aplicado** / **Cambios sin aplicar** / **Retirado**, last activity, integrations and reports), **Descargar**, **Importar proyecto**, delete → trash (30 days), project `principal` after the upgrade | S |
| 34 | `editor-de-proyecto` | proyectos | `/proyectos/:slug`: explorer, tabs (8, unsaved dot), Markdown view / **Ver código**, YAML/SQL/JSON, save, create/rename/delete in allowed paths, problems list → file:line, status bar (**Válido** / **N problemas** / **Listo para aplicar**), chat pane with current spec, phone tabs **Archivos** / **Editor** / **Chat**, **Nuevo chat en este proyecto** | S |
| 35 | `historial-de-proyecto` | proyectos | `/proyectos/:slug/historial`: revisions (actor, command, conversation), diff between two revisions, restore as a new revision, spec timeline, "cambio externo" | S |
| 36 | `aplicar-proyecto` | proyectos | **Aplicar proyecto** (readiness, step-up, new workspace version, rollback in Espacio de trabajo), ids unique across projects, **Cambios sin aplicar**, **Retirar del espacio** | S |
| 37 | `proyectos-en-vs-code` | proyectos | zip download with `.specify/` + preset, opening it in VS Code with the same commands, **Importar proyecto**, Git workspaces (v2 `projects/<slug>/` and legacy layout = `principal`), CLI `bizview validate`, `bizview project new`, `bizview describe` + token, `BIZVIEW_LANG` | S |
| 38 | `chat-del-agente` | agente | chat panel (**Abrir asistente**, **Expandir**, **Abrir en página completa**), conversations (**Nueva conversación** / new chat → project, **Renombrar**, **Archivar**, **Buscar conversaciones**), session indicator (**Trabajando** / **Lista** / **Sin presupuesto**), **Mapa del agente**, **Detener**, budget, **Notas de trabajo**, **Preparación**, **Vista previa** / **PDF de vista previa**, chips; `/admin/asistente`, `/admin/asistente/:id` (redirect to projects, 020); needs IA configured | S |
| 39 | `alcance-del-agente` | agente | BI-only scope and the fixed refusal (021), files change only through commands, content read from sources and files is data, structure-only access, personal-data columns and confirmation, budget and autonomous runs | S |
| 40 | `metodo-spec-kit` | agente | project → numbered specs; flow specify → clarify → plan → tasks → analyze/checklist → implement → converge → **Aplicar proyecto**; stages **Especificada** … **Aplicada** (+ **Convergida**); "no spec, no run"; which command to run next | S |
| 41 | `comandos-especificar` | agente | `/speckit-constitution`, `/speckit-specify`, `/speckit-clarify`: arguments, files written (021 FR-003), current spec, at most 3 open `[NEEDS CLARIFICATION]` markers, refusals | S · commands |
| 42 | `comandos-planificar` | agente | `/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`, `/speckit-checklist`: outputs, warnings (open clarifications), analyze changes nothing | S · commands |
| 43 | `comandos-construir` | agente | `/speckit-implement`, `/speckit-converge`: artifacts per kind, task ticks, `check_query` + preview + readiness, never applies; converge appends tasks only; interrupted runs | S · commands |
| 44 | `tipos-de-spec` | agente | `**Tipo**:` **fuente** / **integracion** / **reporte** (dataset or directo) / **distribucion**, what each produces, when to use each, a project with a single direct `reporte` spec | S |
| 45 | `estructura-de-proyecto` | proyectos | `project.yaml`, `.specify/memory/constitution.md`, `specs/NNN-name/{spec,plan,tasks,research,data-model,quickstart}.md` + `checklists/`, `integrations/<id>/…`, `reports/<id>/report.yaml`, `distributions/<id>.yaml`, allowed paths, size limits, no credentials | S |
| 46 | `definir-una-integracion` | agente | `integration.yaml`: source, `queries/*.sql` (`:window_start` / `:window_end`) or `requests/*.yaml`, dataset columns, `primary_key`, `incremental` (`window_days` / `mode: full`), schedule, checks, `transform` (Polars), personal-data line | S |
| 47 | `definir-un-reporte` | agente | `report.yaml`: `uses` or `direct`, date, joins, metrics, dimensions, periods, compare, views (kpis, trend, ranking, table), filters, access, `pdf` (orientation, views), `ai_narrative`, optional `_en` labels (022), `**Modo**:` line | S |
| 48 | `distribuciones` | agente | `distribucion` spec → `distributions/<id>.yaml` (subscriptions: report, frequency, hour, period, recipients by user or role, PDF, link days; share-link policy), project-owned vs hand-made subscriptions | S |
| 49 | `recorrido-integracion-a-distribucion` | agente | end to end: Fuentes → `fuente` spec → `integracion` spec → `reporte` spec → `distribucion` spec → **Aplicar proyecto** → Integraciones → grant in **Acceso a tableros** → share and send | S |
| 50 | `recorrido-reporte-directo` | agente | end to end: existing table / `bi` → (**Permitir reportes directos**) → `reporte` spec in direct mode → implement → preview → **Aplicar proyecto** → grant (SC-004 path) | S |
| 51 | `instalacion-y-ajustes` | instalacion | `.env` settings by area (branding, `SECURITY_PROFILE`, AI, budgets, `DEFAULT_LOCALE`, `PROJECTS_DIR`, `PROJECT_MAX_MB`, direct reports, `TRANSFORM_MAX_ROWS`, `TIMEZONE`), restart, upgrade by `BIZVIEW_VERSION`, backups (database + `projects/` + secret key), `rotate-secret-key`, `reset-superuser-mfa` | S |
| 52 | `correo-de-la-instalacion` | instalacion | e-mail by `.env` only (`SMTP_*`, `EMAIL_ALLOWED_DOMAINS`, `SHARE_LINKS_ENABLED`, `SITE_ADDRESS`), `mail-test`, what happens when e-mail is off | S |

**Sections** (in order):

| id | es | en |
|----|----|----|
| `primeros-pasos` | Primeros pasos | Getting started |
| `cuenta` | Tu cuenta | Your account |
| `tableros` | Tableros y reportes | Dashboards and reports |
| `compartir` | Compartir y enviar | Share and send |
| `administracion` | Administración | Administration |
| `datos` | Datos e integraciones | Data and integrations |
| `proyectos` | Proyectos | Projects |
| `agente` | Agente y Spec Kit | Agent and Spec Kit |
| `instalacion` | Instalación | Installation |

**Coverage maps** (what the drift test enforces):

- **Routes**:

  | Route(s) | Topic |
  |----------|-------|
  | `/ingresar` | `ingreso` |
  | `/s/:token` | `compartir-enlace` |
  | `/cambiar-clave` | `contrasena` |
  | `/` | `inicio-y-favoritos` |
  | `/tableros`, `/d/:code` | `tableros` |
  | `/r/:id` | `ver-reporte` |
  | `/perfil` | `perfil` |
  | `/admin` | `administracion` |
  | `/admin/usuarios`, `/admin/usuarios/nuevo`, `/admin/usuarios/:id` | `usuarios` |
  | `/admin/auditoria` | `auditoria` |
  | `/admin/ia` | `ia` |
  | `/admin/fuentes`, `/admin/fuentes/nueva`, `/admin/fuentes/:id` | `fuentes` |
  | `/admin/seguridad` | `seguridad` |
  | `/admin/espacio` | `espacio-de-trabajo` |
  | `/admin/integraciones` | `integraciones` |
  | `/admin/tokens` | `tokens` |
  | `/admin/asistente`, `/admin/asistente/:id` | `chat-del-agente` |
  | `/seguridad/doble-factor` | `doble-factor` |
  | `/no-autorizado`, `*` | `navegacion` |
  | `/proyectos` | `proyectos` |
  | `/proyectos/:slug` | `editor-de-proyecto` |
  | `/proyectos/:slug/historial` | `historial-de-proyecto` |
  | `/ayuda` | `ayuda` |

  Any route added by 020/021/022 that is not listed here makes the drift test fail until a topic
  claims it — this is intended.
- **Administración tiles**: each tile target is claimed by the topic of the same screen:
  `/admin/usuarios`, `/admin/fuentes`, `/admin/espacio`, `/admin/integraciones`, `/admin/tokens`,
  `/admin/seguridad`, `/admin/auditoria`, `/admin/ia`, plus any tile 020 adds (for example
  `/proyectos` → `proyectos`).
- **Commands**:

  | Command(s) | Topic |
  |------------|-------|
  | `/speckit-constitution`, `/speckit-specify`, `/speckit-clarify` | `comandos-especificar` |
  | `/speckit-plan`, `/speckit-tasks`, `/speckit-analyze`, `/speckit-checklist` | `comandos-planificar` |
  | `/speckit-implement`, `/speckit-converge` | `comandos-construir` |
  | `/ayuda` | `ayuda` |

### 3. Loader (`backend/app/assistant/guide/__init__.py`)

- `load() -> Guide`, cached with `functools.lru_cache`. It:
  - parses `index.yaml` and validates the schema of §1;
  - reads every body file;
  - raises `GuideError` with the file and a reason when something is wrong (tests call `load()`
    to fail fast).
- `visible_roles(user) -> set[str]` (U/A/S effective sets, as in §1).
- `topics_for(user, lang) -> list[TopicMeta]`: ordered by section, then topic.
- `get(topic_id, lang, user | None) -> Topic | None`: `None` when unknown or not visible.
  `user=None` means the agent (superuser).
- `resolve(text, lang) -> (topic_id | None, closest: list[str])`. Matching is tried in this order:
  1. exact id;
  2. id with spaces → hyphens;
  3. case- and accent-insensitive title;
  4. alias.

  When there is no match, `closest` holds up to 3 ids ranked by `difflib.get_close_matches` over
  titles + aliases.
- `index_text(lang) -> str`: a deterministic block. Each section is a heading followed by one line
  per topic: `- <id> — <title>: <summary> [<role names>]`. It is ≤ 8,000 chars (test) and is part
  of the stable prefix.
- `prompt_block(lang) -> str`: the rules + `index_text(lang)` (see §5).
- Language: `lang ∈ {es, en}`, anything else → `DEFAULT_LOCALE` (022).

### 4. Tool `get_app_guide` (`backend/app/assistant/tools.py`)

- **Spec**:

  ```
  {name: "get_app_guide",
   description: "Guía de la aplicación BizView: sin tema devuelve el índice; con tema (id del
     índice o texto) devuelve ese tema en el idioma del usuario.",
   parameters: {topic: string|null}}
  ```

  The description comes from the backend catalogue (es/en).
- **Result**:
  - no topic → `{index: [{id, section, title, summary, roles}]}`
  - topic found → `{id, title, roles, routes, related: [{id, title}], body}`
  - no match → `{found: false, closest: [{id, title}], note: "El tema no existe en la guía; responde
    que no lo sabes y sugiere el más cercano."}`

  The language is the session user's locale (022).
- **Behaviour**:
  - Not a discovery tool: not in `DISCOVERY_TOOLS`, does not count toward
    `AI_AGENT_DISCOVERY_LIMIT`, not memoised.
  - Added to the set that `offered_tool_specs` keeps when restricted, so it is always offered.
  - Allowed in plain messages and in every command through the 021 registry's inspection tool set
    (021 FR-004).
  - Chip label: **Guía de la aplicación** / **App guide**.
  - Summary line: "Consultó la guía (<id>)".
- **Privacy (VIII)**: inputs are a topic string; the output is product text only.

### 5. System prompt index prefix (`backend/app/assistant/service.py`, FR-003)

- The stable prefix (per language, as 022/021 made it) gains a `## Guía de la aplicación` block from
  `guide.prompt_block(lang)`. It sits after the safety rules and before `authoring.summary()`.
- The block holds no dynamic data, so the prefix stays byte-identical between rounds (017 T039
  test extended).
- **Rules (es; en mirrors them)**:
  1. For any question about how to use BizView (screens, options, roles, Spec Kit method, project
     layout, commands), call `get_app_guide` with the index id, and answer only from what the topic
     says. Answer in short steps.
  2. Name screens and buttons exactly as the guide writes them in bold.
  3. When the topic has an in-app link that applies, include it as `[Abrir …](app:/ruta)`. Never
     invent routes, and never use other link schemes.
  4. If the user's role cannot use the option, say who can (the guide states it).
  5. If no topic covers the question, say you do not know and suggest the closest topic. Never
     invent options.
  6. Never explain how to bypass two-step sign-in, step-up, the security profile or the BI-only
     scope. Never ask for or show secrets.
  7. For "explícame este proyecto" / "¿qué falta?" / "¿por qué…?" about the current project, call
     `get_project_overview` and cite the spec lines it returns (`archivo:línea`).
- **Scope gate (021 FR-007)**: the deterministic pre-check treats guide titles and aliases (both
  languages) as in-scope terms, so "¿cómo activo el tema oscuro?" never gets the fixed refusal.
  `commands/scope.py` imports the aliases from `guide.load()`.

### 6. `/ayuda` (FR-005, US2)

- **Registry entry (021)**:

  ```
  {name: "/ayuda", description: {es: "Cómo trabajar con BizView y Spec Kit", en: "How to work with
   BizView and Spec Kit"}, args_hint: "[tema]", needs_current_spec: false, writable_paths: [],
   allowed_tools: INSPECTION_TOOLS (incl. get_app_guide, get_project_overview), handler: "ayuda"}
  ```
- **No arguments**: `guide/ayuda.py:fixed_reply(session, lang) -> str` renders
  `guide/{lang}/_ayuda.md`. The template has these placeholders:
  - `{method}`: fixed text in the template — the one-paragraph method plus the flow line
    "specify → clarify → plan → tasks → analyze/checklist → implement → converge → Aplicar
    proyecto".
  - `{commands}`: one line per command from the 021 registry, with its description in `lang` and
    args hint, in registry order.
  - `{examples}`: 3 example requests from the template. One of them is
    "Reporte directo sobre la tabla bi_ventas, sin ETL".
  - `{next_steps}`: only when the conversation has a project. It holds up to 5 specs with stage →
    next command, from `overview.next_steps(project)`, deterministic.
  - `{help_link}`: `[Abrir la Ayuda](app:/ayuda)`.
- **Command flow** (in `service.start`, before claiming a run): when the message is `/ayuda` with
  empty arguments, the backend
  - stores the user message and the assistant reply (`command: "/ayuda"`, `tokens: 0`);
  - records a command run with status `completado` and no files (021 FR-006 chip "Ejecutó
    /ayuda");
  - returns 200 with the session.

  There is no provider call and no thread. It also works while the provider is failing.
- **With arguments**: `guide.resolve(args, lang)`. The command prompt
  `agent_commands/{lang}/ayuda.md` (021 single source) runs as a normal turn:
  - On a match, the prompt includes a block `Tema resuelto: <id>` with the topic body, so one
    provider round is enough.
  - With no match, the prompt includes the `closest` list.

  This is a normal 021 command run, which writes nothing.
- **"¿qué falta en este proyecto?"** (US2 AC3): a plain message. The model calls
  `get_project_overview` and answers with `next_command` per spec.

### 7. Project overview (`backend/app/assistant/overview.py`, FR-008, US3)

- `build(db, project) -> dict` is computed from the 020 project folder and status. It does not call
  the provider or read source rows. Payload:

  ```
  {project: {name, slug, status, language, description(≤ 300)},
   specs: [{number, folder, title, kind, mode: dataset|directo|null, stage,
            open_clarifications: int, tasks: {done, total}, next_command, next_action,
            decisions: [{file, line, text(≤ 200)}]}],
   sources: [{name, kind, exists, last_test_ok, direct_reports}],
   integrations: [{id, spec, source, schedule, transform: bool, checks: [type], datasets: [id]}],
   reports: [{id, spec, mode, source_or_uses, tables_or_datasets, metrics: [id], views: [type],
              pdf: bool}],
   distributions: [{id, spec, report, subscriptions: [{frequency, hour, period, pdf, link_days,
                    recipients: {users: n, roles: [role]}}], share_link_max_days}],
   applied: {version_id, at} | null, pending_changes: [path] (≤ 50, + count),
   validation: {valid, problems: n}, ready: bool}
  ```

- `decisions`: lines of `spec.md` that match `**Tipo**:`, `**Modo**:`, `**Fuente**:`,
  `**Tablas**:`, `**Mantiene**:`, `**Volumen**:` or `**Datos personales**:` (019 FR-003), with
  1-based line numbers. This lets the agent cite them (US3 AC2).
- **`next_command(spec)`**, deterministic:

  | Stage | Next command / action |
  |-------|-----------------------|
  | Especificada with open `[NEEDS CLARIFICATION]` | `/speckit-clarify` |
  | Especificada without open markers | `/speckit-plan` |
  | Aclarada | `/speckit-plan` |
  | Planificada | `/speckit-tasks` |
  | Tareas | `/speckit-implement` (hint `/speckit-analyze`) |
  | Convergida | `/speckit-implement` |
  | Implementada, not ready | `/speckit-converge` |
  | Implementada, project ready | `next_action` = "Aplicar proyecto" (human button) |
  | Aplicada with pending changes in its artifacts | `next_action` = "Aplicar proyecto" |
  | Aplicada, otherwise | none |

  `fuente` specs whose catalogue source is missing or untested get `next_action` = "Crear o probar
  la fuente en Administración → Fuentes de datos" + link `app:/admin/fuentes/nueva`.
- `next_steps(project)` is the compact form used by `/ayuda`.
- **Tool `get_project_overview()`** (no arguments; the conversation's project):
  - result = `build(...)`, capped at 20,000 chars (lists trimmed, with counts);
  - chip label **Resumen del proyecto** / **Project overview**;
  - an inspection tool (021 FR-004), not discovery;
  - with no project → `ToolError` "La conversación no tiene proyecto."
- **Privacy test**:
  - **seeds**: a distribution with recipient `ana@example.com` and a source host `db.interno`;
  - **asserts**: neither string appears in the payload, and a role name does.

### 8. In-app links and role filtering (FR-004)

- **`frontend/src/lib/routeAccess.ts`**:
  - `ROUTES: {pattern: string, access: "public"|"user"|"admin"|"superuser"}[]` — the single table
    for App.tsx guards (public = outside `RequireAuth`; `RequireAdmin` → admin;
    `RequireSuperuser` → superuser).
  - `matchRoute(path)` matches `:param` segments and ignores the query string.
  - `canOpen(path, user)`: a superuser passes admin; an admin passes user.
  - The drift test checks the table against App.tsx.
- **`frontend/src/lib/appLinks.ts`**:
  - `splitAppLinks(text) -> Array<{text} | {text, to}>` parses `[label](app:/path)`. Labels hold
    no brackets.
  - `resolveAppLink(to, user)` returns the path when `matchRoute` and `canOpen` both pass, else
    `null`.
- **`frontend/src/components/assistant/ChatText.tsx`**:
  - Renders an assistant message with `whitespace-pre-wrap` as today.
  - Each allowed app link becomes a react-router `<Link>` (accent colour, underline, an
    `ArrowUpRight` icon with `aria-hidden`, min touch height through padding).
  - Disallowed or unknown links render as the label text only.
  - Any other `[x](http…)` stays literal text.
  - On click inside the docked panel below `lg`, the panel collapses (`AssistantPanelContext`).
  - `AssistantChat.tsx` uses `ChatText` for assistant messages only. User messages stay literal.
- **Ayuda page bodies**: 020's `MarkdownView` gets an optional `resolveLink(href) -> string | null`
  prop. `app:` hrefs go through `resolveAppLink`: allowed → `<Link>`, else plain text. Other
  schemes → plain text. Raw HTML stays disabled or sanitised as 020 decided.

### 9. Ayuda page (`/ayuda`, FR-007)

- **API** (`backend/app/api/guide.py`, router under `/api/guide`, any signed-in user, GET only, no
  CSRF needed):
  - `GET /api/guide` → `{version, sections: [{id, title}], topics: [{id, section, title, summary,
    roles, related}]}`, filtered by role, in the request locale.
  - `GET /api/guide/topics/{topic_id}` → `{id, title, body, roles, routes, related: [{id,
    title}]}`. Returns 404 `guide_topic_not_found` when unknown **or not visible** (same answer
    either way).
  - Both responses send `Cache-Control: private, max-age=300`.
- **Page** (`frontend/src/pages/Help.tsx`, route `ayuda` inside the authenticated shell, access
  user):
  - Header: **Ayuda** + subtitle.
  - Search field **Buscar en la ayuda**: a client-side filter on title (accent- and
    case-insensitive), also on summary.
  - The list is grouped by section. Selecting a topic shows it in a view on the same page via
    `?tema=<id>` (no extra route; browser back returns to the list; deep links work).
  - The topic view shows the title, the `MarkdownView` body, **Temas relacionados** and
    **← Volver**.
  - Superuser only: **Preguntar al asistente**, which opens the panel with `/ayuda <id>` in the
    composer.
  - Empty search → "Ningún tema coincide con «…»."
  - Phones: list and topic replace each other. From `lg`: two columns.
- **Navigation**: **Ayuda** in the desktop sidebar (after **Perfil**) and in the **Menú de cuenta**.
  The phone bottom bar keeps 4 items.
- **Catalogue keys** (both languages): `nav.help`, `help.{title, subtitle, search,
  searchPlaceholder, noMatch, related, back, askAssistant, loadFailed}`,
  `assistant.tools.{get_app_guide, get_project_overview}`.
- **Backend catalogue**: `guide_topic_not_found`, the tool descriptions, `ayuda` fixed headings,
  and `no_project`.

### 10. Drift test (FR-006, SC-001)

**Backend `backend/tests/test_guide.py`** (no DB):
1. `guide.load()` succeeds. Ids are unique and match the pattern, sections exist, `related` ids
   exist, and roles come from the vocabulary.
2. Every topic has `es/<id>.md` and `en/<id>.md`, and there are no orphan files. `_ayuda.md` exists
   in both languages with the 5 placeholders.
3. Headings: `#` equals the index title per language, and the `##` count and order match between
   es and en. Bodies are ≤ 6,000 chars.
4. Env-var pattern only in superuser topics. No `password=`/`token=` literals.
5. Every command name in the 021 registry appears in some topic's `commands`, and every `commands`
   entry exists in the registry.
6. `index_text(lang)` is deterministic (two calls equal) and ≤ 8,000 chars. `prompt_block` appears
   in the system prefix for both languages.

**Frontend `frontend/tests/unit/guide-drift.test.ts`** (Vitest, reads repository files with `fs`):
1. Route patterns parsed from `src/App.tsx`:
   - `path="…"` with nested paths made absolute;
   - the index route is `/`;
   - redirects count too.

   Each must be in some topic's `routes` in `backend/app/assistant/guide/index.yaml` (parsed with
   the `yaml` dev dependency). Every `routes` entry must also exist in App.tsx (no stale routes).
   Because of this check, the union of `routes` in `index.yaml` equals the App.tsx route set, so
   Python code can use it as the route list.
2. Every `ADMIN_TILES[].to` (exported from `src/pages/admin/adminTiles.ts`) is in some topic's
   `tiles`.
3. `ROUTES` in `src/lib/routeAccess.ts` equals the App.tsx route set, and each entry's access
   equals the guard element wrapping that route in App.tsx.
4. Every `app:` link in the `es/*.md`, `en/*.md` and `_ayuda.md` files:
   - matches a route through `matchRoute`;
   - has no `:param`;
   - is openable by at least one of the topic's roles (as computed by `canOpen`).
5. Every `**bold**` span of `es/*.md` is a string value of the `es` catalogue, the static prefix of
   a catalogue function, or a line of `labels-allow.txt`. The same check runs for `en/*.md`
   against `en`.
6. **Failure messages**: each failure names the route, tile, command, file or label, and the fix
   ("añade la ruta a `routes` de un tema en index.yaml").

### 11. Fake-provider answer tests (US1 Independent Test)

`backend/tests/test_guide_answers.py`, parametrised over every topic × {es, en}:
- **Setup**:
  - a fake provider scripted to call `get_app_guide(<id>)`, then reply with text that quotes the
    topic's first bold label and its first `app:` link;
  - a superuser session with the matching locale.
- **Assertions**:
  - the tool result body equals the file;
  - the chip label is in the right language;
  - the stored answer contains the link.
- **Extra cases**:
  - unknown topic → `found: false` with `closest`;
  - `/ayuda` without arguments → 0 provider calls, tokens 0, the reply lists every registry
    command, timing < 200 ms (SC-003);
  - `/ayuda reporte directo` → the command prompt contains `Tema resuelto: reportes-directos`;
  - scope pre-check: 20 help questions (both languages) are not refused.

**Unit tests** (`frontend/tests/unit/`):
- `chat-links.test.tsx`:
  - allowed link → anchor to `/admin/fuentes`;
  - user role + superuser route → plain text;
  - unknown route → plain text;
  - `https:` → literal.
- `help-page.test.tsx`:
  - the list is filtered by role (a mocked API returns the role-filtered list);
  - search;
  - `?tema=`;
  - back;
  - no `role="dialog"`.

### 12. Live eval (SC-002, opt-in)

- **Files**:
  - `backend/tests/live/guide_eval.yaml`: 50 questions, 25 es + 25 en, written by Claude and
    reviewed by the owner.
  - `backend/tests/live/test_guide_eval.py`: skipped unless `AI_LIVE_TESTS=1`. Uses the same
    `AI_LIVE_*` variables as `test_agent_eval.py`.
- **Entry format**:

  ```yaml
  - id: es-07
    lang: es
    project: facturas-demo        # optional synthetic fixture project for overview questions
    question: "¿Cómo comparto un tablero por correo cada lunes?"
    topics: [envios-programados]  # accepted get_app_guide topics (≥ 1 must be called)
    must_include: ["Envíos programados", "Semanal"]   # case/accent-insensitive
    must_not_include: []
    link: "/r/"                   # route prefix of a required app: link, or null
    kind: answer                  # answer | unknown | restricted | overview
  ```

- **Mix**:
  - ≥ 1 question per section;
  - 6 about the Spec Kit method and commands;
  - 6 `overview` questions on a synthetic project fixture (3 specs: fuente, reporte directo,
    distribucion);
  - 4 `unknown` (expect "no lo sé" / "I don't know" + a closest topic id or title);
  - 4 `restricted` (bypass two-step, read the AI key, disable the scope, see another user's
    password) → expect no steps and a pointer to the administrator topic;
  - the rest are plain `answer` questions.
- **Scoring** (deterministic, no LLM judge):
  - expected topic fetched (`overview` → `get_project_overview` called);
  - `must_include` present and `must_not_include` absent;
  - every `app:` link valid — it matches a pattern in the union of `index.yaml` `routes`, which
    the drift test keeps equal to App.tsx — and the required link present.
- **Pass**: ≥ 45/50 (90%). The test prints a per-question table and the token use.

### 13. Validation guide

`specs/023-chat-app-guide/quickstart.md` (written in tasks) holds:
- the manual usability check SC-004: a first-time super user is timed on "crear un reporte directo
  sobre una tabla existente" guided only by the chat (target < 10 min);
- the commands for the drift tests and the opt-in eval.

## Risks

| Risk | Mitigation |
|------|------------|
| Guide drifts from the UI (renamed button, new route) | Drift test on routes, tiles, commands and bold labels against the catalogues; failures name the fix. Guide content is part of each release's review. |
| 020/021/022 land with names different from this plan (route paths, registry API, `MarkdownView` props) | Tasks reference the concept and say "as implemented by 020/021/022". The drift test is written against the real App.tsx and registry. |
| Model answers from memory instead of calling the tool (small local models) | Rule 1 in the prompt. `/ayuda <tema>` pre-resolves and injects the topic. The eval measures it. If the eval is below 90% on a local model, add a deterministic hint ("Tema probable: <id>") from `resolve()` into the context block. This is a follow-up only if measured. |
| Prompt growth (index ≈ 2k tokens on every round) | Index cap test (≤ 8,000 chars). It is in the cached stable prefix (017 T039/T040). |
| Superuser-only topics leak to users | Server-side filter, a 404 that does not reveal existence, and an API test per role. |
| Links used for phishing or to dead screens | Only `app:` scheme, route match + role check; drift test on guide links. |
| Overview exposes personal data (recipients) | Counts and role names only. Seeded privacy test. |
| Large projects make the overview huge | 20,000-char cap with counts. Lists sorted by spec number. |
| Guide text is long to write and review | 14 content tasks of 3–4 topics each, in parallel. Owner review gates the release (spec Assumption). |
