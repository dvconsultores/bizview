# Contract — the theme endpoints

All admin endpoints require the super user; `GET /api/themes/{id}` is readable by any signed-in
viewer because a report needs it to render.

| Method | Path | Body / params | Answers |
|---|---|---|---|
| `GET` | `/api/admin/themes` | — | `{themes: [{id, name, name_en, version, origin, project, tokens}], installation: <id>}` |
| `POST` | `/api/admin/themes` | `{yaml: "<file>"}`, `?replace=true` | `{theme}` (201) — 422 `theme_invalid` with `problems[]`, 409 `theme_exists` naming the confirmation, 403 for a built-in id |
| `DELETE` | `/api/admin/themes/{id}` | — | 204; 409 `theme_in_use` with `{reports: [...]}`; 403 `theme_builtin` |
| `GET` | `/api/admin/themes/{id}/download` | — | `text/yaml` — the file as authored |
| `GET` | `/api/themes/{id}` | — | `{id, name, name_en, tokens}` with `ETag` |
| `PUT` | `/api/admin/settings/theme` | `{theme_id}` | the setting; 422 when the theme is unknown |

Audit kinds: `theme_uploaded`, `theme_replaced`, `theme_deleted`, `theme_applied`.

Caching: `GET /api/themes/{id}` answers `ETag` = the row's `updated_at` and `304` when unchanged; the
frontend's settings store drops its cache when the installation theme changes.

## Mode precedence (rendering)

```
mode = report.layout.theme.mode ?? "auto"
"auto"   → the app's resolved theme (the viewer's preference)
"light"  → light, whatever the app says
"dark"   → dark, whatever the app says
the viewer's toggle writes sessionStorage per report and wins over all of the above for that session
the PDF always uses "light"
```
