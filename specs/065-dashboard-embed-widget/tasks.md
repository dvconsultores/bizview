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

## Phase 9: Convergence

- [x] T035 Make the form's own validation the one that runs and speaks: `noValidate` on the create and edit forms so the browser does not hide the product's messages, both fields marked required, every request-model field code (`missing`, `too_short`, `too_long`, …) and every service rejection turned into a readable sentence at its field, the error cleared as the field is corrected per FR-027 (partial)
- [x] T036 Stop the allowed-sites field from looking pre-filled: remove the example placeholder (the hint below already carries the format) or label it explicitly as an example, in both catalogues per FR-027 (partial)
- [x] T037 Complete and prove deletion per FR-028: any state (active, revoked, expired), sites removed with it, it stops serving at once, it works with embedding off, the audit entry keeps name, dashboard, sites, state and visits and never the key, it is scoped to its own dashboard, only admins may delete, and the active count and the 50-per-dashboard limit stay correct (partial)
- [x] T038 Prove the administrator-network restriction covers the deletion route, as it already does for creation and revocation, per FR-028 (partial)
- [x] T039 Verify migration 0060 against the 0056 rule: it grows the audit CHECK from what the live constraint accepts, works on a database built from empty and on one already at 0059, keeps every audit row, is harmless to re-run and has a safe downgrade; add the 0059→head case to `test_audit_constraint_upgrade.py` and run `test_migrations.py` in full per FR-016/FR-028 (partial)
- [x] T040 Make the confirmation for an active widget say plainly that it will stop working on the sites that embed it, with a neutral confirmation for revoked and expired widgets, in both languages per FR-028 (partial)
- [x] T041 Update `docs/WIDGETS.md` and `docs/es/WIDGETS.md`, both guide topics and `CHANGELOG.md` for required fields, per-field messages and deletion, keeping the ES/EN parity per FR-026 (partial)
- [x] T042 Extend `frontend/tests/e2e/widgets.spec.ts`: an empty required field shows its message at the field and sends no request, and a widget is deleted after the plain confirmation (active) and from the revoked state, in Chromium per US1/AC6 and US3/AC6 (missing)
- [x] T043 Review the draft's `.env.example` rewrite and the broken indentation in the two i18n catalogues: keep the documentation if it is accurate, fix the formatting per FR-026 (unrequested)
- [x] T044 Run the whole verification set after the changes (all four backend suites, the frontend type check, unit suite and build, the Chromium e2e spec, the docs parity check and every gate) and record the results in the third-pass section of `run-report.md` (missing)
