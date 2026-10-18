# API contract: Dark mode

Conventions as in features 002–005: JSON, same-origin session cookie, mutating requests carry
`X-Requested-With: fetch` (CSRF), errors use the common error body.

## `user_json` gains `theme`

Every response that embeds the user (`GET /api/me`, sign-in response, admin user reads) adds:

```json
{ "theme": "system" }
```

`theme` ∈ `"system" | "light" | "dark"`. The frontend `User` type adds `theme: ThemePreference`.

## `PATCH /api/me/preferences`

Change the signed-in user's own preferences. Allowed with a temporary-password session
(`auth_allow_temporary`); no step-up; not audited.

Request:

```json
{ "theme": "dark" }
```

| Field | Rule |
|---|---|
| `theme` | required; one of `system`, `light`, `dark`; unknown fields rejected |

Responses:

| Status | When | Body |
|---|---|---|
| 200 | saved | `{ "theme": "dark" }` |
| 401 | no session | common error body |
| 403 | CSRF header/origin missing | `csrf_failed` |
| 422 | invalid value, missing `theme`, or unknown field | `validation_error`, `fields.<name>` = pydantic error type (e.g. `literal_error`) |

Idempotent: sending the current value returns 200 and changes nothing.
