# Quickstart & Validation: Platform Foundation

**Feature**: [spec.md](./spec.md) | **Contracts**: [contracts/api.md](./contracts/api.md)

## Prerequisites

- Docker + Docker Compose v2; Node 24 and Python 3.12+ (`uv`) for running outside containers.
- `.env` at the repository root (copy `.env.example`): `DATABASE_URL_BI`, `SUPER_USER_EMAIL`,
  `SUPER_USER_PASSWORD`, `PRODUCT_NAME`, `ORGANIZATION_NAME`, `SITE_ADDRESS`, `PUBLIC_BASE_URL`,
  `COOKIE_SECURE`.
- Production recommendation: a dedicated database role that owns the product tables in the BI
  database, instead of the `postgres` superuser (research R5).

## Run

```bash
docker compose up -d --build          # caddy + backend; backend runs migrations + bootstrap first
open http://localhost:8080            # SITE_ADDRESS=:80, HTTP_PORT=8080
```

Production: set `SITE_ADDRESS=dashboard.example.com`, `PUBLIC_BASE_URL=https://dashboard.example.com`,
`COOKIE_SECURE=true`, open ports 80/443; Caddy obtains and renews the certificate.

Super-user recovery: `docker compose exec backend python -m app.cli reset-superuser-password`.

## Tests

```bash
# DATABASE_URL_BI, temporary schema app_test_* (created + dropped); public never written
cd backend && uv run pytest                    # unit + integration
cd frontend && npm test && npm run build && npm run check:compat
cd frontend && npx playwright test             # chromium, firefox, webkit at 320/375 px + axe
```

## Validation scenarios

| # | Scenario | Expected | Covers |
|---|---|---|---|
| 1 | Fresh DB, `docker compose up` | 5 tables + `alembic_version` in `public`; super user exists; other tables unchanged (structure and row counts) | FR-007, FR-031, SC-007 |
| 2 | Restart backend twice | no migration change, no error, super user password unchanged | FR-008, SC-007 |
| 3 | Sign in as super user at 375 px | home shows greeting and "Ventas — Próximamente" card, disabled | US1, FR-018, FR-020 |
| 4 | 5 wrong passwords, then correct | 6th refused with minutes remaining (423) | FR-003, SC-004 |
| 5 | Create admin + user as super user; sign in as each | forced to change password first; other pages → change screen | US2, FR-014 |
| 6 | Admin tries to edit/deactivate another admin or the super user | refused | FR-012, FR-009 |
| 7 | Deactivate a signed-in user | their next request → sign-in; login refused with generic message | FR-004, FR-002 |
| 8 | Regular user opens `/admin` and calls every `/api/admin/*` | "No autorizado" / 403 for all | SC-003 |
| 9 | Grant then revoke "Ventas" to a user | card appears / disappears; `/d/ventas` refused after revoke | US4 |
| 10 | Change own password | other sessions end; old password fails | US3 |
| 11 | Super user opens Auditoría | events for all of the above, no secrets in detail | FR-022, FR-023, SC-009 |
| 12 | Every screen at 320 and 375 px in Chromium, Firefox, WebKit | no horizontal scroll; axe: 0 serious/critical | SC-005, SC-006 |
| 13 | Change `PRODUCT_NAME`, `ORGANIZATION_NAME`, logo; restart | new branding on sign-in, home, tab title | US5, FR-030 |
| 14 | `SITE_ADDRESS` = domain | HTTPS with valid certificate, HSTS header present | FR-032 |
