# Data Model: Dark mode

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md) R3

## Theme preference (column on `app_user`)

| Field | Type | Rules |
|---|---|---|
| `theme` | `text NOT NULL DEFAULT 'system'` | CHECK `theme IN ('system','light','dark')` (constraint `ck_app_user_theme`) |

- Owned by exactly one user; every existing row gets `system` from the default (no data
  migration, spec assumption).
- Written only by the user themself (`PATCH /api/me/preferences`); administrators do not set it
  and it is not shown in admin user screens.
- `updated_at` moves on change (existing `onupdate`).
- Migration: `backend/alembic/versions/0005_user_theme.py`, revises `0004_vibe_reporting`;
  downgrade drops the column. Runs on `DATABASE_URL_BI`, schema `public`.

## Client-side state (not persisted on the server)

| Item | Where | Values | Purpose |
|---|---|---|---|
| Device cache | `localStorage["bizview.theme"]` | `system` \| `light` \| `dark` | pre-paint theme and pre-sign-in screens (FR-006, FR-007) |
| Resolved theme | `<html data-theme>` + `color-scheme` + `<meta name="theme-color">` | `light` \| `dark` | drives the CSS tokens |

## State transitions

```text
page load ──► theme-init.js: cache (default system) ─► resolve ─► data-theme
sign-in / GET /api/me ──► account theme overrides cache ─► resolve ─► data-theme
user picks option ──► apply now + write cache ─► PATCH /api/me/preferences
                                         └─ failure: keep applied theme, toast "no se guardó" (FR-013)
device appearance changes ──► only if preference = system ─► resolve ─► data-theme
sign-out ──► cache kept (last choice on this device)
```
