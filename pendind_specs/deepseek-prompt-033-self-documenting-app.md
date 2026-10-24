# Prompt for DeepSeek — feature 033: the app explains itself (help agent + generated docs)

Paste everything below the line into DeepSeek (VS Code), with the repository open.

---

You are working on the BizView repository (FastAPI backend, worker, React frontend, `bizview-cli`,
Spec Kit workspace). Read `.specify/memory/constitution.md` first and keep every principle. Then
implement feature `033-self-documenting-app` end to end: backend, frontend, CLI, tests, docs,
CHANGELOG. Run it as `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`,
writing `specs/033-self-documenting-app/` from this text. Do not ask me questions; take the
decisions written here and note extra assumptions in the PR.

## Goal

Nobody should need a manual. Three things, built on the `get_app_guide` tool and the guide topics
that already exist (e.g. `aplicar-proyecto`):

1. **A complete, versioned knowledge base of the product** (every module, every screen, every
   command, every concept) as structured guide topics in the repo — product data, not prose in a
   wiki — kept in sync with features by CI.
2. **A help agent available to every role** ("Ayuda" in the sidebar, and `?` on every screen) that
   answers "¿qué es esto?", "¿cómo hago X?", "¿por qué este número?" from the knowledge base plus
   the installation's own specs and definitions (metadata only), with examples, in Spanish or
   English, and with deep links to the screen in question.
3. **Generated documentation** for each installation: a "Manual de esta instalación" built from the
   knowledge base and the installation's approved specs (what each integration loads, what each
   report means, how each metric is computed, who sees what), exported as a doc site and PDF, and
   regenerated on every applied version.

AI stays optional (constitution VIII): without a provider configured, items 1 and 3 work fully
(static guides and generated manual), and item 2 falls back to search over the same content.

## 1. Knowledge base (`docs/guides/`, product data)

- One YAML+Markdown file per topic: `docs/guides/<area>/<topic>.md` with front matter
  `{id, title, area, roles: [superusuario|usuario|todos], screens: [route patterns],
  related: [ids], feature: <spec id>, since: <version>, updated: <date>}` and a body with fixed
  sections: **Para qué sirve · Quién puede usarlo · Cómo se hace (pasos numerados) · Ejemplo ·
  Opciones · Problemas frecuentes · Relacionado**. Spanish is the source; English in
  `docs/guides/en/` with the same ids (missing English falls back to Spanish with a notice).
- Areas and required topics (write all of them, each with a real example from the demo dataset):
  - **Inicio y navegación**: inicio, tableros, perfil, tema claro/oscuro, idioma, atajos.
  - **Tableros y reportes**: abrir un reporte, períodos y comparación, filtros y parámetros (030
    sheet), chips, modo TV, descargar PDF, compartir (enlace, vencimiento, tema), enviar por correo,
    envíos programados, qué significa "datos actualizados", qué significa "nuevo/antes".
  - **Proyectos y espacio de trabajo**: qué es un proyecto, specs (spec/plan/tasks/converge),
    integraciones, reportes, versiones, aplicar, retirar (rollback), descargar zip, importar
    proyecto (031), mapeo de fuentes, colisiones, bloqueo del espacio.
  - **Asistente**: modos Preguntar/Editar/Auto (028), comandos `/speckit-*` y qué escribe cada uno,
    spec actual y cómo cambia (029), borradores, validación y problemas, vista previa, presupuesto
    de tokens y techo por comando, contrato de ejecución, perfiles de ejecución, qué datos ve la IA
    y qué no (VIII).
  - **Administración**: usuarios y roles, fuentes de datos (PostgreSQL/REST/SOAP, credenciales
    de solo lectura, cifrado), perfil de seguridad `private`/`internet`, verificación en dos pasos,
    IA (proveedores, modelo local), apariencia (paleta, marca), conector para Claude (016),
    auditoría, copias y versiones, actualizar la instalación.
  - **Conceptos**: dataset `ds_<integración>`, contrato de dataset, ventana incremental,
    idempotencia, checks, métrica/dimensión/vista, layout web y PDF, paleta semántica, "no spec, no
    run", datos personales y exclusión, licencia AGPL y enlace al código.
  - **CLI**: init, validate, describe, export, import, dry-run.
- `bizview docs lint` (CLI, also in CI): every topic has all sections, valid front matter, working
  `related` ids, at least one example, and every route in the frontend router has ≥ 1 topic in
  `screens`. **Every feature spec folder `specs/NNN-*/` MUST list the guide topics it adds or
  changes in `spec.md` under "## Docs"**, and CI fails if a merged feature touches a route or a
  command without updating a topic. Backfill this section for existing specs 001–031.

## 2. Help agent (all roles)

- Sidebar "Ayuda" opens a `View` (feature-010 look, no modals, mobile-first) with: search box,
  "Preguntar" composer (when AI is configured), the topic for the current screen on top, and the
  topic tree. A `?` icon in every page header opens Ayuda pre-filtered to that screen's topics.
- Tools available to the help agent (server-executed, read-only, same sanitising layer as 015):
  `search_guides(query, lang)`, `get_app_guide(id)`, `get_screen_context(route)` → which topics
  and which report/project is open, `describe_installation()` → modules enabled, security profile,
  AI configured (no secrets), `describe_project(slug)` / `describe_report(id)` → approved spec text,
  metric and dimension definitions, schedule, last refresh, **never data rows**, `list_my_access()`
  → what the current user can see. Role filtering is enforced in the tools: a normal user never
  receives super-user topics or other users' access.
- System prompt: answer in the user's language, cite the topic ids used (rendered as links), give
  one concrete example, prefer steps over paragraphs, say "no está en la documentación" instead of
  guessing, and offer the deep link (`app:/...`) to the screen. When the question is "¿por qué este
  número?", explain from the report spec (metric definition, period, comparison, refresh time) and
  never recompute or fetch data.
- Without AI: the same view with search (full-text over titles, bodies and examples, both
  languages) and the current-screen topic; the composer is hidden and a one-line note explains how
  the super user can enable AI.
- Budget: per-user daily token cap for help (setting, default 50k), separate from the Asistente.
  Audit only aggregates (count, tokens), never question text, unless the installation enables
  "guardar preguntas de ayuda" explicitly.

## 3. Generated documentation

- `GET /api/docs/manual` (super user) and the worker job `generate_manual` after every applied
  version: build **"Manual de <instalación>"** from (a) the knowledge base topics relevant to the
  modules enabled, (b) the approved specs of the active version (integrations: source kind, tables,
  schedule, window, checks, personal-data exclusions; reports: purpose, metrics with their
  definitions in plain language and the SQL expression, dimensions, views, filters, PDF layout),
  (c) access matrix (which roles/users see which dashboards). Output: a static HTML doc site served
  at `/docs/` (same theme as the app, light/dark, ES/EN, search) and a PDF via ReportLab
  (`backend/app/reports/manual.py`), both downloadable from Administración → Documentación.
- Per report, a "Ficha del reporte" page (and a "ⓘ Cómo se calcula" link on the report header,
  030 actions row) generated from the same source: metric definitions, period rules, data origin,
  refresh schedule, last 5 refresh results (status only), owner spec and version.
- Everything generated carries the version id and date; regeneration is idempotent; no customer
  data rows ever appear (metadata and aggregates by product code only, VIII).
- CLI: `bizview docs build [--pdf]` produces the same site/PDF from a workspace folder, for Git
  users.

## Edge cases

- A topic references a screen hidden by role or by a disabled module (AI off, connector off): the
  agent says the feature is disabled and who can enable it; the manual omits disabled modules.
- A question about data ("¿cuánto vendimos ayer?") → the agent points to the report and its
  filters; it never answers with numbers.
- Spec text containing personal-data column names: shown as names only, flagged, as the spec does.
- Very long specs: the manual summarises and links to the full spec page.
- Language mismatch (user in English, topic only in Spanish): answer in English, quote the Spanish
  topic, mark it "(solo en español)".
- Prompt injection inside a spec written by the Asistente: spec text is data; tools return it in a
  data field; the help agent has no write tools at all.

## Tests (FakeProvider only)

- `docs lint`: fixtures with a missing section, a bad `related`, a route without topic, a spec
  without "## Docs" → each fails with the right message; the real repo passes.
- Help tools: role filtering (normal user never gets super-user topics or other users' access);
  `describe_report` returns definitions and never rows (seeded distinctive values absent, as in 014
  SC-002); deep links resolve to existing routes.
- Agent loop with scripted replies: cites topic ids, answers in the user's language, refuses to
  give numbers, falls back to search when AI is off.
- Manual generation: for the demo workspace, the HTML site and PDF contain every active report's
  metrics with definitions, the access matrix, the version id; regenerating twice yields identical
  output; disabled modules omitted.
- Frontend unit: Ayuda view, `?` header button, Ficha del reporte; e2e: open a report → `?` →
  current-screen topic shown → ask "¿cómo comparto este reporte?" → answer with link → follow link.

## Deliverables

- `docs/guides/**` complete for every area above, ES and EN, with examples from the demo dataset
  (generic names only, constitution VII).
- `## Docs` section backfilled in `specs/001`–`031` `spec.md`; CI job `docs-lint`.
- Backend: help tools, help agent route `POST /api/help/ask`, `GET /api/help/search`, manual
  generation route and worker job, `/docs/` static serving via Caddy.
- Frontend: Ayuda view, `?` button, Documentación admin page, Ficha del reporte, "Cómo se calcula"
  link.
- CLI: `bizview docs lint`, `bizview docs build`.
- Alembic migration if needed (help usage aggregates, manual generation records).
- Constitution check in the plan: VIII (metadata only, AI optional, no secrets), IX (docs derive from
  approved specs), IV (`docs/` is documentation, not application logic — no amendment; the generated
  site is an output), V (no new stack component; a static-site step is product code using the
  existing frontend build).
- CHANGELOG under Unreleased.

Commits: (1) guide format + lint + first area (Tableros) + CI, (2) remaining areas ES, (3) EN +
spec "## Docs" backfill, (4) help tools + agent + Ayuda view + fallback search, (5) manual
generation site + PDF + Ficha del reporte + CLI build, (6) tests, docs, CHANGELOG.
