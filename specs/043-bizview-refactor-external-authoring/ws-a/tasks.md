# Tasks: 043 WS-A — Remove the authoring agent (+ WS-G)

Batches are DeepSeek briefs (session `bizview-043-ws-a`); each lands with its focused checks
before the next starts. Full suites once, at the end of A4 (code first, test last).

## Batch A1 — detach shared code (behavior-preserving; suites green with the agent still in)
- [ ] T001 `assistant/guide/` → `app/guide/` (package, `index.yaml`, topics, README,
      labels-allow); `api/guide.py` re-pointed; chat-only `ayuda.py`, `_ayuda.md`,
      `prompt_block`/`index_text`/`resolve` left behind; the 14 `agente` topics +
      `perfiles-de-ejecucion` parked in `specs/043-…/drafts/guide-reuse/`;
      `frontend/tests/unit/guide-drift.test.ts` re-pathed.
- [ ] T002 Preview re-keyed by project (D3): `assistant/preview.py` → `projects/preview.py`;
      `preview_request` table (new, keyed by `project_id` + user) written by a migration that
      also migrates pending `assistant_preview_request` rows; `engine/runner.run_preview`,
      `engine/datasets.preview_prefix`, `engine/report.PreviewVersion`, `worker.py`
      queue/cleanup, `projects/apply.drop_for_session` → `drop_for_project`; API routes under
      `/api/projects/{slug}/preview*` unchanged in shape.
- [ ] T003 Readiness deterministic (D4): `assistant/readiness.py` → `projects/readiness.py`;
      `POST /projects/{slug}/validate` runs `origin.run_check` for every query/request file and
      records `project.query_checks`; personal-data confirmation persisted per project;
      apply gate reads both; tests for the new path.
- [ ] T004 Remaining moves (D5): `origin.py` check half → `projects/origin_checks.py`;
      `personal.py` → `projects/personal.py` (`engine/direct.py` re-pointed);
      `tree.bootstrap_manifest` → `projects/compose.py`; `WorkView` project-only; moved i18n
      keys (`readiness.*`, `preview.*`, `origin.*`, `tree.*`) keep their ids.
- [ ] T005 Verify: ruff + full backend suite green (assistant still present), frontend
      `guide-drift` green.

## Batch A2 — delete the backend agent
- [ ] T006 Fix migration 0029 (`upgrade()` must not import `app.assistant`); new drop migration
      per D6 (export applied conversations' spec folders, drop `assistant_*`, `ai_status`,
      revision FKs → plain columns, `app_user.attachments_notice_at`).
- [ ] T007 Delete `app/assistant/`, `api/assistant.py`, assistant testhooks; `main.py` router
      list; `worker.py` notify/watch and attachment sweep; `cli.py` `import_open_drafts`.
- [ ] T008 Provider slim-down (D1): delete `Provider.chat` + chat types + `history_rules.py` +
      `fake.chat` + chat error codes; 035 state machinery and `api/ai.py` slimmed per D2;
      `api/health.py` `ai_block`/vision/attachments fields out of `/api/config`.
- [ ] T009 `models.py` (7 assistant tables, constants, FKs), `config.py` assistant settings,
      `projects/{service,apply,history,importer,workview,zip,fixes}.py` session/busy surfaces,
      `api/{me,security}.py` attachment parts, backend i18n deletions (assistant/commands/
      activity/pipeline/attachments/scope + chat guide keys).
- [ ] T010 Verify: ruff + focused pytest (projects, preview, readiness, migrations incl.
      `alembic upgrade head` on fresh schema).

## Batch A3 — delete the frontend agent + WS-G grid
- [ ] T011 Moves first: `PreviewReports.tsx` → `components/projects/`; `relativeTime` → `lib/`;
      `t.assistant.downloadZip` relocated (Workspace.tsx keeps working).
- [ ] T012 Delete `components/assistant/` (28 files), `AssistantSession.tsx`, `RunProfiles.tsx`,
      `RedirectToProject.tsx`, `api/attachments.ts`, `api/ai.ts`; routes + `routeAccess`;
      `api/projects.ts` session calls; `types.ts` assistant blocks.
- [ ] T013 Edits: `AppShell`, `ShellChrome` (keep the `chat` flag consumer in `ReportView` TV
      mode working or rename), `ProjectWorkspace` (chat pane out, `PreviewReports` stays),
      `Projects.tsx`, `ProjectHistory`, `Help.tsx`, `Security.tsx`, `PaneTabs`, `StatusBar`,
      `BrandingContext`.
- [ ] T014 i18n: delete `assistant` (minus relocated key), `chatAttachments`, slim `ai`;
      `nav.ai`, `help.askAssistant`, project chat keys; keep the 19 `audit.assistant_*` labels
      (historical rows render).
- [ ] T015 WS-G: AI card out of `adminTiles.ts`; pill + `useAIHealth` out of `AdminHome`;
      `tokensText` → "Para la CLI y las herramientas externas"; `projectsText` → "Specs,
      integraciones, reportes y distribuciones: importar, validar y aplicar"; "Fuentes de datos"
      text mentions "Descargar estructura"; grid cols unchanged. ("Paquete de autoría" card
      ships with WS-B — D8.)
- [ ] T016 Verify: tsc + focused vitest (admin-home, projects-page, help-page, ide).

## Batch A4 — tests
- [ ] T017 Delete assistant suites (39 backend files + deepseek/live fixtures; 20+ frontend unit;
      5 e2e + fixture); `conftest.py` cleanup; edit the ~25 touched suites; re-home the
      declarative-content check from `test_draft_content_check.py` into import validation tests.
- [ ] T018 Rewrite `frontend/tests/e2e/projects.spec.ts` around import → validate → preview →
      apply (no fake provider, no commands); `backend.sh` env cleanup.
- [ ] T019 Full backend + frontend + e2e suites green; fresh-schema `alembic upgrade head`.

## Batch A5 — docs, deploy, gate
- [ ] T020 `.env.example`, `deploy/install.sh`, `bizview.yml`, `Caddyfile`,
      `deploy/tests/test_install.sh`; delete `DIAGNOSIS.md`, `prompt_coinmarketcap.md`,
      `prompt_demo.md`, `tmp/dev041`.
- [ ] T021 README + README.es, `docs/INSTALL.md`, `docs/VIBE-REPORTING.md`,
      `docs/guides/proyectos/aislamiento.md`, `.github/copilot-instructions.md`; CHANGELOG
      0.2.0 "Removed" lists 014 015 017 021 024 028 029 035 036 039 040.
- [ ] T022 CI grep gate per D7 (excludes `cli/bizview_cli/workspace_template/`, `specs/`,
      `CHANGELOG.md`, alembic history); green locally.
