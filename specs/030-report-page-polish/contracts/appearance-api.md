# Contract — installation appearance API

The installation's palette preset, chosen and saved by the super user in Administración → Apariencia
(FR-008). Follows the `telegram_settings` precedent: a singleton row, a super-user `GET`/`PUT` pair,
an audit event, and the value exposed on the public config endpoint because the shared view needs it.

## `GET /api/admin/appearance`

*Actor*: super user (`require_superuser`). *Response* `200`:

```json
{ "palette_preset": "impacto", "presets": ["impacto", "clasico", "monocromo", "contraste", "daltonico"] }
```

`presets` lets the picker render without a second round trip and keeps the list in one place
(`backend/app/reports/palette.py`).

## `PUT /api/admin/appearance`

*Actor*: super user, CSRF header as the other admin writes. *Body*:

```json
{ "palette_preset": "contraste" }
```

| Case | Result |
|---|---|
| known id | `200 { "palette_preset": "contraste" }`, row upserted, audit `appearance_updated` |
| unknown id / wrong type | `422` with `error.message` in the installation language; nothing written |
| not super user | `403` |
| missing CSRF | `403` (existing middleware) |

Audit payload: `{"palette_preset": {"from": "impacto", "to": "contraste"}}` — no free text, no secrets.

## `GET /api/config`

Adds two fields to the existing public payload
([health.py:30-41](../../../backend/app/api/health.py:30)):

| Field | Type | Notes |
|---|---|---|
| `palette_preset` | string | the installation default; `"impacto"` when the row is missing or unreadable (same best-effort shape as `telegram_sign_in`) |
| `palette_presets` | string[] | the ids, so a shared view or the picker can render every card |

Unchanged: product name, organization name, logo, version, AI and Telegram availability.

## Frontend client

- Boot: the config values are read once with the rest of `PublicConfig` and handed to
  `ThemeProvider`; they feed `frontend/src/theme/palette.ts`.
- Admin screen: `GET /api/admin/appearance` on mount, `PUT` on "Guardar", success toast + optimistic
  preview of the selected card (the cards render with the preset, not with the saved value).
