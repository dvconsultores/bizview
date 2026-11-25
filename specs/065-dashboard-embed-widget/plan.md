# Implementation Plan: Embed a dashboard as a widget in another web page

**Branch**: `065-dashboard-embed-widget` | **Date**: 2026-11-24 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/065-dashboard-embed-widget/spec.md`

## Summary

A widget is a **standing, revocable permission to show one dashboard inside a named list of sites**,
created from the dashboard's sharing screen. The admin gets the iframe snippet once; the visitor gets
the dashboard read-only, with no account and no session. The public door is `/w/<key>`: a document
whose framing permission (`Content-Security-Policy: frame-ancestors …`) is built from **that
widget's own allowed sites** by the backend, because Caddy cannot know a widget. Caddy asks the
backend on every `/w/*` document request (`forward_auth`) and copies the answer; every other route
keeps the site-wide `X-Frame-Options: DENY` / `frame-ancestors 'none'`.

The backend mirrors feature 018 instead of duplicating it: a new `app/sharing/widgets.py` reuses
`links.report_context`, `links.sharing_enabled`, `links.public_base` and the report rendering path
(`api.reports._data`, `api.reports.filter_values`, `assets`/`images`, `reports.pdf`), and the public
routes are a second, sessionless surface next to `/api/shared/`.

An **admin preview** frames the widget through a short-lived, signed ticket instead of the key, so
the key stays one-way (SHA-256 only) and the snippet really is shown once: the in-product test page
never needs the key, and a lost snippet is replaced.

## Technical Context

**Language/Version**: Python 3.12 + FastAPI/SQLAlchemy/Alembic (backend), TypeScript 5 + React 19 +
Vite + Tailwind (frontend), Caddy 2 (edge).

**Primary Dependencies**: none new. `secrets`, `hashlib`, `hmac` (keys and preview tickets), the
existing `app.security.crypto` key handling (no new library), react-router (`/w/:token`),
lucide-react icons, Playwright + Vitest (frontend tests), pytest + TestClient (backend tests).

**Storage**: two new tables, `dashboard_widget` and `dashboard_widget_site` (Alembic `0059`);
nothing on `share_link` changes. No files, no external service.

**Testing**: `uv run pytest -q tests/test_widgets.py` (backend), the existing sharing suites to prove
018 did not move, `npx tsc -b`, `npx vitest run`, `npx playwright test tests/e2e/widgets.spec.ts`,
`deploy/tests/test_install.sh`, `deploy/tests/test_caddy_widget.sh`, and
`docker run --rm -v … caddy:2-alpine caddy validate` for the Caddyfile.

**Target Platform**: the existing single-origin deployment. The framed page is 375 px and up; the
host page keeps its own scrollbar-free rendering.

**Constraints**:

- The site-wide framing refusal stays on every route except `/w/*`; only the widget's list relaxes
  it, and only for that document.
- A widget request never reads the session cookie: the public API surface uses no auth dependency,
  and the shell skips its `/api/me` bootstrap on `/w/*` (the locale and theme providers need
  `AuthProvider` around them, so the page is not mounted outside it — `AuthProvider.isWidgetPage`
  is the equivalent guarantee, and the widget page proves it by making no session request at all).
- The 90-day maximum and the 20-link limit of feature 018 are untouched (asserted by the existing
  tests, which run unchanged).
- Filters stay a convenience: switching them off makes the widget ignore `period`/`compare`/`from`/
  `to`/`filter.*`; the engine's `filter.<dimension>` freedom is never presented as a restriction.

**Scale/Scope**: 50 active widgets per dashboard, 10 sites per widget, one dashboard per widget,
one request ceiling per widget (installation setting).

## Constitution Check

- **I. Mobile-first**: the widget is designed at 375 px first; the test page starts at phone width.
- **II. Backend as ETL**: nothing new is read from an origin; the widget serves the same cached,
  optimized payload as the signed-in dashboard.
- **III. Source of truth external**: no origin write, no origin session.
- **IV. Separated concerns**: the widget logic lives in `app/sharing/`, the public routes next to the
  shared ones, the Caddy rule in `deploy/caddy/`.
- **V. Fixed stack**: no component added. The Caddyfile gains one standard directive
  (`forward_auth`, part of the edge Caddy already runs). No HTML is rendered by the API: the framed
  document is the SPA, served by Caddy as today, and the backend only answers headers.
- **VII. One product, many installations**: every number (feature switches, ceiling) is an
  installation setting; the allowed sites are data.
- **Constraints**: JSON-only API (the widget endpoints are JSON; the document stays Caddy's), every
  text in ES and EN, secrets never readable, Alembic owns the schema.

No amendment is required. The one deviation worth naming is that a *document* response now depends
on a backend answer (through Caddy), which is what makes a per-widget framing permission possible at
all; it is recorded in Complexity Tracking below and in research R2.

## Complexity Tracking

| Decision | Why it is not a violation |
|---|---|
| Caddy calls the backend (`forward_auth`) for `/w/*` before serving the SPA document | The alternative would be a global exception in Caddy (`frame-ancestors *` for a path) — exactly the weakening the brief forbids — or the backend serving HTML, which the constitution forbids. The backend still renders no HTML: it answers headers only. |
| The shell skips `/api/me` on `/w/*` (`AuthProvider.isWidgetPage`) | FR-010: the widget must not read the session. The locale and theme providers are nested inside `AuthProvider`, so mounting the page outside it would mean rewriting two providers; skipping the bootstrap achieves the same guarantee with one guarded effect, and the browser test asserts that no `/api/me` request is made. |
| A second public API surface (`/api/widgets`) next to `/api/shared` | Share links carry a 90-day rule and a 20-link count; a widget has neither. Sharing the module would make one feature's limit leak into the other. The *code paths* are shared; the doors and their limits are not. |

## Project Structure

```text
specs/065-dashboard-embed-widget/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── tasks.md
└── run-report.md

backend/alembic/versions/0059_dashboard_widgets.py      # two tables + four audit kinds
backend/app/models.py                                   # DashboardWidget, DashboardWidgetSite
backend/app/config.py                                   # embed_widgets_enabled, widget_rate_limit
backend/app/sharing/widgets.py                          # keys, sites, limits, preview, framing, ceiling
backend/app/api/widgets.py                              # /api/widgets/... (sessionless, public)
backend/app/api/sharing.py                              # /api/dashboards/{code}/widgets (admin)
backend/app/main.py                                     # router + public headers for /api/widgets/
backend/app/i18n/es.py / en.py                          # widget.*, widget_site.* messages
backend/tests/test_widgets.py                           # security, limits, preview, ceiling, audit

frontend/src/pages/WidgetView.tsx                       # /w/:token (the framed document)
frontend/src/pages/WidgetTestPage.tsx                   # /d/:code/widgets/:id/probar (admins)
frontend/src/components/sharing/WidgetsPanel.tsx        # create / list / edit / replace / revoke
frontend/src/pages/ReportView.tsx                       # "Insertar en un sitio web" view
frontend/src/App.tsx                                    # /w outside AuthProvider, test page inside
frontend/src/api/types.ts                               # widget types
frontend/src/i18n/es.ts / en.ts                         # sharing.widgets.*
frontend/tests/e2e/widgets.spec.ts                      # create → test page → framed widget

deploy/caddy/Caddyfile                                  # /w/* forward_auth, default DENY scoped
deploy/install.sh                                       # EMBED_WIDGETS_ENABLED, WIDGET_RATE_LIMIT
deploy/tests/test_install.sh                            # the new placeholders
deploy/tests/test_caddy_widget.sh                       # framing rules, textual
backend/app/guide/{es,en}/insertar-un-widget.md         # help topic (FR-026)
backend/app/guide/index.yaml                            # topic entry
docs/INSTALL.md, docs/es/INSTALL.md                     # operator: enabling, ceiling, Caddy
docs/WIDGETS.md, docs/es/WIDGETS.md                     # what a widget is, how to embed it
CHANGELOG.md                                            # Unreleased
```

## Phase 0 — Research decisions

See [research.md](./research.md). The load-bearing ones:

- R1: **a widget is a new table, not a new kind of share link**. The 90-day rule and the 20-link
  count stay literally untouched; the widget has its own 50 count and no expiry.
- R2: **the framing permission is computed where the widget is known and copied by Caddy**
  (`forward_auth`); the default refusal is scoped with a matcher so every non-widget path is
  unchanged. The backend answers `200` always, with `frame-ancestors 'none'` when it knows nothing,
  and Caddy keeps its own refuse-by-default policy on `/w/*` until the backend's answer replaces it,
  so a bug can only fail closed.
- R3: **the public document and the public API are sessionless**. The widget API has no auth
  dependency, the SPA route is outside `AuthProvider`, and the test page proves that a request with
  an admin cookie gets the anonymous payload.
- R4: **the preview uses a signed ticket**, not the key: the key stays SHA-256-only, the snippet is
  shown once, and the test page works with no external site in the list (FR-018/019).
- R5: **the per-widget ceiling is 300 requests per minute by default**, an installation setting,
  counted in the database across workers (one atomic `UPDATE … RETURNING` per widget request), and it
  never blocks the document decision (`/frame`), so the host page always renders the neutral message
  instead of a failed navigation.
- R6: **sites are canonical origins** (`scheme://host[:port]`, no path, no wildcard), and a local
  address is flagged as development when it is `localhost`, `*.localhost` or a loopback/private IP.

## Phase 1 — Data, service and doors

- `0059_dashboard_widgets.py`: `dashboard_widget`, `dashboard_widget_site`, the four audit kinds
  (`widget_created`, `widget_updated`, `widget_key_replaced`, `widget_revoked`).
- `app/sharing/widgets.py`: key generation/hash, site parsing and validation, capacity, create /
  update / replace / revoke / list, availability, usage counters, ceiling, preview ticket signing,
  framing header, snippet text, public base.
- `app/api/widgets.py`: `/api/widgets/{token}` (definition), `/data`, `/filters/{dimension}`,
  `/assets/…`, `/images/…`, `/pdf`, and `/frame/{token}` for Caddy. Every response carries
  `X-Robots-Tag: noindex, nofollow`, `Cache-Control: no-store`, `Referrer-Policy: no-referrer`.
- `app/api/sharing.py`: `GET/POST /api/dashboards/{code}/widgets`,
  `PATCH/DELETE …/{widget_id}`, `POST …/{widget_id}/replace`, `POST …/{widget_id}/frame`
  (the test page's short-lived frame; named `frame` because the routes gate reserves `preview`
  for the removed authoring surface).
- `app/main.py`: include the router; extend the public-header middleware to `/api/widgets/`.

## Phase 2 — The two frontend surfaces

- `WidgetView`: definition + data, theme/language forced by the widget or following the visitor,
  title/filters/PDF per widget, filter sheet when filters are on, no chrome, legal links only,
  content height reported to the host page over `postMessage` with no data in it, neutral
  "not available" and "try again in a moment" states.
- `WidgetsPanel` (in the dashboard sharing view): create form (name, sites, appearance, expiry) with
  the FR-012 warning, the list with state/sites/creator/usage/count, edit, replace, revoke and
  **Probar**.
- `WidgetTestPage`: the widget framed at 375 / 768 / 1280 px through a preview ticket, the snippet
  (when it was just produced), the allowed sites with the development mark, and a warning.

## Phase 3 — Edge, install and documentation

- `deploy/caddy/Caddyfile`: scope the framing refusal with `@not_widget not path /w/*`; add
  `handle_path /w/*` with `forward_auth backend:8000 { uri /api/widgets/frame{uri}; copy_headers … }`
  followed by the existing static file serving.
- `deploy/install.sh` + its test: commented `EMBED_WIDGETS_ENABLED=false` and `WIDGET_RATE_LIMIT=300`
  next to `SHARE_LINKS_ENABLED`.
- Guide topic ES/EN, `docs/INSTALL.md` + `docs/es/`, a new `docs/WIDGETS.md` + `docs/es/`,
  `CHANGELOG.md`.

## Phase 4 — Gates

| Gate | Command |
|---|---|
| Backend feature + 018 untouched | `cd backend && uv run pytest -q tests/test_widgets.py tests/test_sharing_links.py tests/test_i18n_core.py tests/test_guide.py` |
| Types / unit / build | `cd frontend && npx tsc -b && npx vitest run && npm run build` |
| End to end | `cd frontend && npx playwright test tests/e2e/widgets.spec.ts` |
| Installer | `bash deploy/tests/test_install.sh` |
| Edge config | `bash deploy/tests/test_caddy_widget.sh` and `docker run --rm -v "$PWD/deploy/caddy:/etc/caddy:ro" caddy:2-alpine caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile` |
| Docs parity | `python3 scripts/check_docs_parity.py` |
