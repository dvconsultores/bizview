# Data Model: Platform Foundation

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-29

Database: `DATABASE_URL_BI` (PostgreSQL 15, database `bizview`). All tables live in the standard
schema **`public`**, created and versioned by Alembic from `backend/alembic/` (version table
`public.alembic_version`); no schema is hard-coded (research R5). No extensions are installed.
Table names below are unqualified.

Feature 001 later adds `customer_account`, a nullable `app_user.account_id`, and its sales
tables, in its own migrations.

## app_user — *User*

| Field | Type | Rules |
|---|---|---|
| id | bigint identity PK | |
| email | text not null unique | stored as `lower(btrim(email))`; CHECK `email = lower(btrim(email))`; CHECK length 3–254 and contains `@` |
| full_name | text not null | 1–120 chars after trim |
| role | text not null | CHECK in (`admin`, `user`) |
| is_superuser | boolean not null default false | CHECK `NOT is_superuser OR role = 'admin'`; partial unique index `uq_app_user_single_superuser ON ((true)) WHERE is_superuser` → at most one |
| is_active | boolean not null default true | CHECK `is_active OR NOT is_superuser` |
| password_hash | text not null | Argon2id PHC string |
| must_change_password | boolean not null default true | false only after the user sets their own password (or bootstrap) |
| failed_attempts | int not null default 0 | reset on successful sign-in |
| locked_until | timestamptz null | now + 15 min on the 5th consecutive failure |
| last_login_at | timestamptz null | |
| password_changed_at | timestamptz not null default now() | |
| created_at / updated_at | timestamptz not null default now() | `updated_at` set by the application |
| created_by | bigint null FK → app_user(id) | null for the bootstrap super user |

Indexes: unique `email`; `(role, is_active)`; trigram search is not needed at this scale (list
search uses `ILIKE` over ≤ a few thousand rows).

**States**

```text
created (must_change_password) ──own change──▶ active
active ──admin reset──▶ must_change_password (all sessions deleted)
active ──5 failures──▶ locked (until locked_until) ──time passes / admin reset──▶ active
active ──deactivate──▶ inactive (all sessions deleted) ──reactivate──▶ active
super user: never inactive, never role ≠ admin
```

## app.user_session — *Session*

| Field | Type | Rules |
|---|---|---|
| id_hash | bytea PK | SHA-256 of the 32-byte random cookie value; raw value never stored |
| user_id | bigint not null FK → app_user ON DELETE CASCADE | index |
| created_at | timestamptz not null default now() | absolute expiry = created_at + 30 days |
| last_seen_at | timestamptz not null default now() | idle expiry = last_seen_at + 7 days; updated at most every 5 min |
| user_agent | text null | truncated to 300 chars |
| ip | inet null | |

Expired rows are deleted lazily on lookup and in bulk by `bootstrap`.

## dashboard — *Dashboard* (catalogue)

| Field | Type | Rules |
|---|---|---|
| id | smallint identity PK | |
| code | text not null unique | `^[a-z][a-z0-9-]{1,39}$`; used in URLs `/d/{code}` |
| name | text not null | Spanish display name |
| description | text not null | ≤ 200 chars |
| icon | text not null | lucide icon name, e.g. `chart-line` |
| sort_order | int not null default 100 | |
| status | text not null | CHECK in (`available`, `coming_soon`, `hidden`) |
| created_at / updated_at | timestamptz | |

Seed (migration 0002): `('ventas', 'Ventas', 'Resumen, tendencias y productos de tus ventas.',
'chart-line', 10, 'coming_soon')`. Feature 001 sets `status = 'available'`.

## dashboard_access — *Dashboard Access*

| Field | Type | Rules |
|---|---|---|
| user_id | bigint FK → app_user ON DELETE CASCADE | PK part |
| dashboard_id | smallint FK → dashboard ON DELETE CASCADE | PK part |
| granted_by | bigint null FK → app_user | |
| granted_at | timestamptz not null default now() | |

Only meaningful for `role = 'user'`; admins see every non-hidden dashboard. Grants are kept if a
user becomes admin (harmless) so demotion restores them.

**Access rule**: `can_see(u, d) = d.status <> 'hidden' AND (u.role = 'admin' OR grant exists)`;
`can_open(u, d) = can_see(u, d) AND d.status = 'available'`.

## app.audit_event — *Audit Event*

| Field | Type | Rules |
|---|---|---|
| id | bigint identity PK | |
| occurred_at | timestamptz not null default now() | index (desc) |
| kind | text not null | CHECK in list below |
| actor_id | bigint null FK → app_user | null for failed sign-in with unknown email and for bootstrap |
| target_id | bigint null FK → app_user | index |
| ip | inet null | |
| detail | jsonb not null default '{}' | never passwords, hashes, or session ids; for unknown-email failures the attempted email is stored |

Kinds: `login_ok`, `login_failed`, `login_locked`, `logout`, `user_created`, `user_updated`,
`user_deactivated`, `user_reactivated`, `role_changed`, `password_changed`, `password_reset`,
`dashboard_granted`, `dashboard_revoked`, `superuser_created`, `superuser_promoted`,
`superuser_recovered`.

Retention: 12 months, purged by `app.cli bootstrap` (research R4).

## Relationships

```text
app_user 1 ─── * user_session
app_user 1 ─── * dashboard_access * ─── 1 dashboard
app_user 1 ─── * audit_event (actor_id / target_id)
app_user 1 ─── * app_user (created_by)
```

## Validation rules from requirements

- FR-001: email normalised before every lookup and insert.
- FR-003: `failed_attempts`, `locked_until`; a wrong current password in FR-017 increments too.
- FR-009: partial unique index + CHECKs make a second or inactive super user impossible in the
  database, not only in code.
- FR-015: password rules in `backend/app/auth/passwords.py` and mirrored for instant feedback in
  `frontend/src/lib/password.ts`; the server is authoritative.
- FR-016: no DELETE path for users in the API; the FK from audit events would block it anyway.

## Migrations

| Revision | Content |
|---|---|
| `0001_app_auth` | `app_user`, `user_session`, `audit_event` |
| `0002_dashboards` | `dashboard`, `dashboard_access`, seed `ventas` |

Both have `downgrade()` that drops only their own tables. Upgrade → downgrade → upgrade is part of the test suite.
