# Tasks: Embed a dashboard as a widget in another web page

**Feature**: `065-dashboard-embed-widget` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

## Phase 1 — Schema and the widget service

- [x] T001 `alembic/versions/0059_dashboard_widgets.py`: `dashboard_widget`, `dashboard_widget_site`, checks, indexes, four audit kinds (frozen list + live constraint union)
- [x] T002 `app/models.py`: `DashboardWidget`, `DashboardWidgetSite`; `AUDIT_KINDS` gains the four kinds
- [x] T003 `app/config.py`: `embed_widgets_enabled` (`EMBED_WIDGETS_ENABLED`, off) and `widget_rate_limit` (`WIDGET_RATE_LIMIT`, 300)
- [x] T004 `app/sharing/widgets.py`: key/hash, site parsing (scheme, host, port, path/wildcard/duplicate refusals, development mark), availability, capacity (50), create/update/replace/revoke/list, usage + ceiling, preview ticket, framing CSP, snippet (FR-001/005/006/009/011/015/016/019/020/022/024)
- [x] T005 `app/i18n/es.py` + `en.py`: `widget.*` / `widget_site.*` messages (one neutral unavailable)

## Phase 2 — The public door (sessionless)

- [x] T006 `app/api/widgets.py`: `/api/widgets/{token}` definition — effective `pdf`/`show_filters`, dashboard name, frame origins; no auth dependency (FR-003/004/010/024)
- [x] T007 `/data`, `/filters/{dimension}`, `/assets`, `/images`, `/pdf` mirroring `api/shared.py`, with control gating when filters are off and neutral 404 everywhere else (FR-003/013/024)
- [x] T008 `/frame/{token}` for Caddy's `forward_auth`: CSP from the widget's sites, `'none'` when unknown, `'self'`+sites for a preview, never fails, no cookie, no counting (FR-008/013/014)
- [x] T009 `app/main.py`: include the router, public headers for `/api/widgets/`, CSRF for the PDF POST

## Phase 3 — Admin door

- [x] T010 `app/api/sharing.py`: list/create/patch/revoke/replace/preview under `/api/dashboards/{code}/widgets`, admin-only, audited (FR-001/002/016/021/022)
- [x] T011 Snippet builder: copy-ready iframe + sizing script (no dashboard data, origin-checked both ways) and `public_base` reuse (FR-002/017/025)

## Phase 4 — Backend tests

- [x] T012 `backend/tests/test_widgets.py`: creation flags/limits/validation, hashed key, snippet once, audit
- [x] T013 Security: framing CSP = only the widget's sites; unknown/revoked/expired/replaced → neutral 404; share links and every other route still refuse framing; admin cookie gets the anonymous payload; no `Set-Cookie`
- [x] T014 Security: PDF refused when off; filters/period ignored when off; per-widget ceiling 429 with `retry_after_seconds`; per-address limits still apply
- [x] T015 Preview: test page path without external sites, visits not counted, expired ticket refused; widget ceiling does not affect signed-in reads
- [x] T016 CSP drift test against `deploy/caddy/Caddyfile`

## Phase 5 — Edge and installation

- [x] T017 `deploy/caddy/Caddyfile`: `@not_widget not path /w/*` scoping of the framing refusal; `handle_path /w/*` + `forward_auth` + `copy_headers`
- [x] T018 `deploy/install.sh`: commented `EMBED_WIDGETS_ENABLED` / `WIDGET_RATE_LIMIT`
- [x] T019 `deploy/tests/test_install.sh` + `deploy/tests/test_caddy_widget.sh`
- [x] T020 `docker run … caddy:2-alpine caddy validate` and a live `forward_auth` check against a stub upstream

## Phase 6 — Frontend

- [x] T021 `api/types.ts`: `DashboardWidget`, `WidgetSite`, `WidgetsState`, `CreatedWidget`, `WidgetDefinition`
- [x] T022 `pages/WidgetView.tsx`: `/w/:token`, no chrome, forced theme/language, title/filters/PDF per widget, neutral + retry states, height reporting over `postMessage`, legal links only (FR-017/023/024/025)
- [x] T023 `App.tsx`: `/w/:token` outside `AuthProvider`; `/d/:code/widgets/:id/probar` inside `RequireAdmin`
- [x] T024 `components/sharing/WidgetsPanel.tsx`: create form + FR-012 warning, list with state/sites/creator/usage, edit, replace, revoke, Probar
- [x] T025 `pages/WidgetTestPage.tsx`: preview ticket, 375/768/1280 widths, snippet (when just produced), sites with development badge, warning
- [x] T026 `pages/ReportView.tsx`: "Insertar en un sitio web" view wired to the panel
- [x] T027 `i18n/es.ts` + `en.ts`: every new string

## Phase 7 — Documentation

- [x] T028 Guide topic `insertar-un-widget` (ES/EN) + `index.yaml` + the guide count test
- [x] T029 `docs/WIDGETS.md` + `docs/es/WIDGETS.md`; `docs/INSTALL.md` + `docs/es/INSTALL.md` (switches, ceiling, Caddy, CSP)
- [x] T030 `CHANGELOG.md` under Unreleased

## Phase 8 — Gates

- [x] T031 Backend suites: `test_widgets.py`, `test_sharing_links.py`, `test_i18n_core.py`, `test_guide.py`
- [x] T032 `npx tsc -b`, `npx vitest run`, `npm run build`, `npx playwright test tests/e2e/widgets.spec.ts`
- [x] T033 `deploy/tests/test_install.sh`, `deploy/tests/test_caddy_widget.sh`, `python3 scripts/check_docs_parity.py`
- [x] T034 `run-report.md`
