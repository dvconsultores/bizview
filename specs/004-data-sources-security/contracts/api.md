# API Contract — feature 004

Conventions of feature 002 apply (JSON, cookie session, `X-Requested-With: fetch` on mutations,
error envelope `{"error": {"code", "message", "fields"?}}`). New error codes:

| HTTP | code | Meaning |
|---|---|---|
| 403 | `mfa_enrollment_required` | `internet` profile: this administrator must enroll two-step sign-in first |
| 403 | `reauth_required` | confirm the password (`POST /api/auth/reauth`) and retry |
| 403 | `address_not_allowed` | administration refused from this network address |
| 429 | `rate_limited` | too many failed sign-ins from this address; `retry_after_seconds` included |

## Sign-in and second factor

### `POST /api/auth/login`

Unchanged body. Responses:

- no two-step sign-in: `200 {"user": User}` (as feature 002);
- two-step enabled: `200 {"mfa_required": true}` + pending session cookie (5 minutes);
- `429 rate_limited` before the password is checked when the address is over the limit.

### `POST /api/auth/mfa`

`{"code": "123456"}` or `{"recovery_code": "ABCDE-FGHIJ"}` with a pending session →
`200 {"user": User}`. Wrong code → `401 invalid_code` (counts toward lockout and throttle); no
pending session → `401 unauthenticated`; expired pending session → `401 unauthenticated`.

### `POST /api/auth/reauth`

`{"password": "…"}` → `204` (sets `reauth_at`); wrong → `401 invalid_credentials` (counts toward
lockout).

### `GET /api/me` (added fields)

```json
{"mfa_enabled": true, "mfa_required": true, "reauth_valid_until": "2026-09-29T21:05:00Z",
 "recovery_codes_left": 9}
```

`mfa_required` = the profile requires it for this user's role.

## Own two-step sign-in (`/api/me/mfa`) — step-up required for all mutations

| Method & path | Body | Response |
|---|---|---|
| `POST /api/me/mfa/setup` | `{}` | `{"otpauth_uri", "secret", "qr_svg"}` (`qr_svg` is a `data:image/svg+xml;base64,…` URI); replaces any pending, not-yet-enabled secret |
| `POST /api/me/mfa/enable` | `{"code"}` | `{"recovery_codes": ["ABCDE-FGHIJ", … 10]}` shown once; `422 invalid_code` |
| `POST /api/me/mfa/recovery-codes` | `{}` | new 10 codes (old ones invalid) |
| `POST /api/me/mfa/disable` | `{"code"}` | `204`; `403 forbidden` when the profile requires it for this user |

## Administration

- `POST /api/admin/users/{id}/mfa/reset` (super user, step-up) → `204`; audited `mfa_reset`.
- `GET /api/admin/users…` user objects gain `mfa_enabled`.

## Data sources (super user; step-up for every mutation and test)

### `GET /api/sources/types`

Field definitions per kind, used to build the forms (single source of truth):

```json
{"postgresql": {"label": "PostgreSQL", "fields": [
   {"name": "host", "type": "string", "required": true, "secret": false},
   {"name": "port", "type": "integer", "default": 5432},
   {"name": "password", "type": "string", "secret": true, "required": true},
   {"name": "sslmode", "type": "enum", "options": ["require", "verify-full"], "default": "require"}
 ]}, "soap": {…}, "rest": {…}}
```

Options not allowed by the active profile are omitted (e.g. `sslmode=disable` in `internet`).

### `GET /api/sources` · `GET /api/sources/{id}`

```json
{"id": 3, "name": "ERP ventas", "kind": "postgresql", "description": "", "enabled": true,
 "settings": {"host": "erp.internal", "port": 5432, "database": "ventas", "username": "bi_ro",
              "sslmode": "require", "timeout_seconds": 15},
 "secret_fields": ["password"], "imported": false,
 "last_test": {"at": "…", "ok": true, "code": null, "message": "Conexión correcta",
               "latency_ms": 184, "details": {"server_version": "PostgreSQL 16.4 …"}},
 "created_at": "…", "updated_at": "…"}
```

Never contains secret values.

### `POST /api/sources`

```json
{"name": "ERP ventas", "kind": "postgresql", "description": "", "enabled": true,
 "settings": {…non-secret…}, "secrets": {"password": "…"}}
```

→ `201` source object. `409 conflict` duplicate name; `422 validation_error` with `fields`
(`settings.host`, `secrets.password`, …) including profile violations (`not_allowed_in_profile`)
and blocked destinations (`blocked_address`).

### `PATCH /api/sources/{id}`

Any of `name`, `description`, `enabled`, `settings` (full replacement of non-secret settings),
`secrets` (partial: `{"field": "new"}` replaces, `{"field": null}` clears, omitted keeps) → source
object. Changing `kind` is not allowed (create a new source).

### `DELETE /api/sources/{id}` → `204`; `409 in_use` when referenced by a dataset.

### `POST /api/sources/{id}/test` and `POST /api/sources/test`

The first tests a saved source; the second tests an unsaved draft (same body as create; nothing is
stored). Always `200`:

```json
{"ok": false, "code": "auth_failed", "message": "Las credenciales fueron rechazadas.",
 "latency_ms": 212, "warnings": [], "details": {}}
```

`code` ∈ `unreachable`, `timeout`, `tls_error`, `auth_failed`, `not_found`, `blocked_address`,
`not_allowed_in_profile`, `invalid_response`, `error`; `warnings` ∈ `not_read_only`, `superuser_account`. `details`: database
→ `server_version`; SOAP → `services` (name, ports, operations); REST → `status`, `content_type`,
`bytes`.

## Security overview

### `GET /api/security` (super user)

```json
{"profile": "internet", "profile_source": "auto", "http_allowed": false,
 "checks": [
   {"id": "https", "ok": true}, {"id": "secure_cookies", "ok": true},
   {"id": "secret_key", "ok": true}, {"id": "admin_mfa", "ok": false, "detail": "1 de 3 administradores sin doble factor"},
   {"id": "admin_networks", "ok": null, "detail": "sin restricción"},
   {"id": "private_networks", "ok": null, "detail": "permitidas"},
   {"id": "key_rotation", "ok": null, "detail": "nunca rotada"}],
 "legacy_origin_notice": false}
```

`ok: null` = informational.
