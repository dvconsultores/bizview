# Contract — share link theme

The sharer may force the first-load theme of a public link (FR-006, US4). After that first load the
viewer decides; the choice is device-local, exactly like the language switcher.

## `POST /api/sharing/{code}/links` (extended)

*Actor*: admin (unchanged). New optional body field:

```json
{ "days": 7, "note": "Cliente norte", "theme": "dark" }
```

| Field | Type | Rules |
|---|---|---|
| `theme` | `"light" \| "dark" \| null` | optional, default `null` = follow the viewer |

Response gains `"theme"` next to the existing link fields; `token` and `url` are unchanged.

## `GET /api/shared/{token}` (extended)

Adds `"theme": "dark" | null` at the top level (next to `dashboard`, `expires_at`, `report`). No other
change: the token check, throttling, visit counting and `ai_narrative: false` stay as they are.

## Shared view behaviour (`/s/<token>`)

```text
on first successful GET /api/shared/{token}:
  stored = localStorage["bizview.theme"]            (try/catch → null when blocked)
  if stored is null and payload.theme is set:
      apply payload.theme  →  localStorage["bizview.theme"] = payload.theme
  else: keep the resolved value (viewer's choice / device appearance)
```

- The toggle in the header is `ThemeSwitcher compact` (Claro / Oscuro, roving radio, `aria-checked`),
  beside the existing `LanguageSwitcher compact`.
- Switching re-themes instantly: `applyTheme()` sets `<html data-theme>`; the palette variables follow
  the resolved theme with no reload.
- Storage failures are swallowed (private mode): the theme still applies for the page.
- `PDF` from the shared view is rendered by the backend with the preset's **light** variant,
  irrespective of the screen theme.

## Data

`share_link.theme` (nullable, `light`/`dark`, check constraint) — migration `0027_appearance_palette`.
Existing links created before the migration have `NULL` and behave exactly as today.
