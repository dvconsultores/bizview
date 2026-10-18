# API Contract: Platform Foundation

Base path `/api`, same origin as the SPA (served by Caddy). JSON only. Session cookie `sid`
(research R3). Every `POST/PUT/PATCH/DELETE` requires header `X-Requested-With: fetch`
(else `403 csrf_failed`).

Error envelope (all non-2xx):

```json
{ "error": { "code": "validation_error", "message": "Texto en español", "fields": { "email": "…" } } }
```

`fields` is present only for `validation_error`. `locked` adds `"retry_after_seconds": 840`.

Guards used below:

- **session** — valid session, else `401 unauthenticated`. When the user has
  `must_change_password`, every route **not** marked *(allowed while temporary)* answers
  `403 password_change_required`.
- **admin** — session + `role = admin`, else `403 forbidden`.
- **super** — session + `is_superuser`, else `403 forbidden`.

## User object

```json
{
  "id": 7,
  "email": "ana@example.com",
  "full_name": "Ana Pérez",
  "role": "user",
  "is_superuser": false,
  "is_active": true,
  "must_change_password": false,
  "locked_until": null,
  "last_login_at": "2026-09-29T14:03:11Z",
  "created_at": "2026-09-20T10:00:00Z"
}
```

## Public

### `GET /api/health`
`200 {"status":"ok"}`; `503 {"status":"unavailable"}` when the database is unreachable.

### `GET /api/config` *(allowed while temporary; no session needed)*
`200 {"product_name": "…", "organization_name": "…", "logo_url": "/branding/logo.svg" | null}`

## Auth

### `POST /api/auth/login`
Body `{"email": "…", "password": "…"}` (email ≤ 254, password ≤ 128).
- `200` → `{"user": User}` + `Set-Cookie: sid=…; HttpOnly; SameSite=Lax; Path=/[; Secure]`.
- `401 invalid_credentials` — wrong email, wrong password, or inactive user (same message).
- `423 locked` — with `retry_after_seconds`.

### `POST /api/auth/logout` *(allowed while temporary)*
`204`; deletes the session and clears the cookie. Idempotent without a session.

## Me

### `GET /api/me` *(allowed while temporary)*
`200 User`.

### `POST /api/me/password` *(allowed while temporary)*
Body `{"current_password": "…", "new_password": "…"}`.
- `204` → password changed; `must_change_password = false`; **other** sessions deleted.
- `401 invalid_credentials` (wrong current; counts toward lockout) / `423 locked`.
- `422 validation_error` with `fields.new_password` ∈ `too_short`, `too_long`,
  `contains_email`, `same_as_current`.

## Dashboards

### `GET /api/dashboards`  — session
`200 {"items": [Dashboard]}` visible to the user in `sort_order`:

```json
{ "code": "ventas", "name": "Ventas", "description": "…", "icon": "chart-line",
  "status": "coming_soon", "path": "/d/ventas" }
```

### `GET /api/dashboards/{code}` — session
`200 Dashboard` when the user can open it; `403 forbidden` when not visible to the user or not
`available` (message distinguishes "no autorizado" / "próximamente" via `error.code` =
`forbidden` | `coming_soon`); `404 not_found` for unknown codes.

## Administration

### `GET /api/admin/users` — admin
Query: `q` (matches name or email, case-insensitive), `role` (`admin|user`),
`status` (`active|inactive|locked`), `limit` (1–100, default 50), `offset`.
`200 {"items": [User], "total": 123}` ordered by `full_name`.

### `POST /api/admin/users` — admin (creating `role=admin` requires super)
Body `{"email", "full_name", "role": "user"|"admin", "temporary_password"}`.
`201 User` (with `must_change_password: true`); `409 conflict` (email exists, any case);
`422 validation_error`; `403 forbidden`.

### `GET /api/admin/users/{id}` — admin
`200 {"user": User, "dashboards": [{"code", "name", "status", "granted": true|false}]}`
(`granted` omitted for admin users, who see all).

### `PATCH /api/admin/users/{id}` — admin, subject to research R6
Body: any of `{"full_name", "role", "is_active"}`.
`200 User`; `403 forbidden` (target is admin and actor is not super; target is super user;
target is self for `role`/`is_active`; role change by non-super). Deactivation deletes all the
target's sessions.

### `POST /api/admin/users/{id}/password` — admin, subject to research R6
Body `{"temporary_password"}` → `204`; sets `must_change_password`, clears lockout, deletes all
sessions of the target. Not allowed on self (use `/api/me/password`) or on the super user.

### `PUT /api/admin/users/{id}/dashboards` — admin
Body `{"codes": ["ventas", …]}` — the full set of grants (unknown codes → `422`).
`200 {"dashboards": [...]}` as in `GET /api/admin/users/{id}`; audit one event per grant added
or removed. Target must be `role = user`.

### `GET /api/admin/dashboards` — admin
`200 {"items": [Dashboard]}` — full catalogue including `hidden`.

### `GET /api/admin/audit` — super
Query: `target_id`, `actor_id`, `kind`, `before` (event id, for paging), `limit` (≤ 100, default
50). `200 {"items": [{"id","occurred_at","kind","actor":{"id","email"}|null,"target":{…}|null,"ip","detail"}], "next_before": 123|null}`.
