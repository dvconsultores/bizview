# Quickstart & Validation: Dark mode

**Feature**: [spec.md](./spec.md) | **Contracts**: [api](./contracts/api.md),
[theme tokens](./contracts/theme-tokens.md) | **Data**: [data-model.md](./data-model.md)

## Run

```bash
# backend (migration 0005_user_theme on DATABASE_URL_BI, schema public)
cd backend && uv run alembic upgrade head
uv run pytest tests/test_me.py tests/test_migrations.py        # app_test_* schemas on DATABASE_URL_BI

# frontend
cd frontend
npm test                          # unit: theme resolver, guard against raw palette classes
npm run build && npm run e2e      # Playwright 3 engines × 320/375 px, incl. tests/e2e/theme.spec.ts
```

Manual check: open the app, set the OS/browser to dark appearance (or DevTools → Rendering →
*Emulate CSS prefers-color-scheme: dark*), then walk the screens.

## Validation scenarios

| # | Scenario | Expected | Covers |
|---|---|---|---|
| 1 | Fresh user, device dark, open sign-in then home | dark on both; `html[data-theme=dark]` | US1, FR-001, FR-007 |
| 2 | Theme "Sistema", emulate light ↔ dark while a report with an open period picker is shown | theme swaps < 1 s, picker stays open, filters kept | US1, FR-005, SC-002 |
| 3 | Device dark; block `/assets/*.js` in Playwright and load `/` | `data-theme=dark` still set (set by `theme-init.js` before the app) | FR-006, SC-004 |
| 4 | Profile → Apariencia → "Oscuro" | whole app dark immediately, no reload | US2, FR-002, FR-003 |
| 5 | Account menu → "Claro" from a report screen | ≤ 2 taps, applies at once | FR-002, SC-002 |
| 6 | Choose "Oscuro" in context A; sign in with same user in fresh context B (light device) | B dark on first screen after sign-in | US2, FR-004, SC-003 |
| 7 | "Claro" on a dark device; flip device appearance | app stays light | US2 AS3 |
| 8 | `PATCH /api/me/preferences` aborted (Playwright route → 500) | theme applied; toast "no se pudo guardar" | FR-013 |
| 9 | `PATCH /api/me/preferences` with `{"theme":"sepia"}` / without session / without CSRF header | 422 `validation_error` / 401 / 403 | contracts/api.md |
| 10 | axe (`wcag2aa`, `color-contrast`) on every route in dark and light (sign-in, change password, 2FA setup, home, report, profile, all admin screens, open modal, toast) | 0 violations | FR-008, FR-009, SC-001 |
| 11 | Report with KPIs, trend (with previous period), ranking, data table, narrative at 375 px, dark | legible, series distinct (solid vs dashed), no horizontal scroll | US3, FR-010, SC-005 |
| 12 | Export the same report to PDF in dark and in light | identical PDFs (byte-compare after stripping creation date) | FR-012, SC-006 |
| 13 | Configured `LOGO_URL` with a dark logo, dark theme | logo shown on the unchanged hero background (header, sign-in) | FR-011 |
| 14 | `npm test` guard with a stray `text-slate-600` added | test fails naming file:line | contracts/theme-tokens.md guard |
| 15 | Sign out after choosing "Oscuro"; reload sign-in on the same device (light) | sign-in dark (device cache) | FR-007 |
| 16 | Light theme before/after, screenshots of sign-in, home, report, admin, users, sources | byte-identical (only data timestamps and the new Apariencia card differ) | assumption "no redesign" |
