# Data model — 065 dashboard embed widget

Alembic revision `0059_dashboard_widgets` (after `0058_password_removal`). Nothing on `share_link`,
`dashboard` or `app_user` changes; `audit_event.kind` gains four values.

## `dashboard_widget`

One standing permission to show one dashboard inside a list of sites.

| Column | Type | Notes |
|---|---|---|
| `id` | `bigint identity` PK | |
| `dashboard_id` | `smallint` FK → `dashboard.id` `ON DELETE CASCADE`, indexed | the one dashboard it shows |
| `name` | `text` NOT NULL | `CHECK char_length(name) BETWEEN 1 AND 80` (FR-001) |
| `key_hash` | `bytea` NOT NULL UNIQUE | SHA-256 of the 256-bit key; the key itself is never stored (FR-011) |
| `theme` | `text` NULL | `light` \| `dark`; NULL follows the visitor (FR-024) |
| `language` | `text` NULL | `es` \| `en`; NULL follows the visitor |
| `show_title` | `boolean` NOT NULL default `true` | |
| `show_filters` | `boolean` NOT NULL default `true` | |
| `pdf_enabled` | `boolean` NOT NULL default `false` | off by default (FR-024) |
| `expires_at` | `timestamptz` NULL | NULL = never expires (FR-005) |
| `created_by` | `bigint` FK → `app_user.id` | |
| `created_at` | `timestamptz` NOT NULL default `now()` | |
| `revoked_at` | `timestamptz` NULL | revocation is permanent (FR-022) |
| `revoked_by` | `bigint` NULL FK → `app_user.id` | |
| `visits` | `integer` NOT NULL default 0 | documents shown |
| `last_visit_at` | `timestamptz` NULL | |
| `rate_window_start` | `timestamptz` NULL | start of the current ceiling minute (FR-015) |
| `rate_count` | `integer` NOT NULL default 0 | requests in that minute |

Checks: `expires_at IS NULL OR expires_at > created_at`; `visits >= 0`; `rate_count >= 0`;
`theme IN ('light','dark')`; `language IN ('es','en')`; name length.

Index: `ix_dashboard_widget_active (dashboard_id, expires_at) WHERE revoked_at IS NULL` — the 50-count
and the list.

## `dashboard_widget_site`

One allowed site of a widget.

| Column | Type | Notes |
|---|---|---|
| `id` | `bigint identity` PK | |
| `widget_id` | `bigint` FK → `dashboard_widget.id` `ON DELETE CASCADE`, indexed | |
| `origin` | `text` NOT NULL | canonical `scheme://host[:port]` (R6) |
| `development` | `boolean` NOT NULL default `false` | local address, marked wherever shown (FR-020) |
| `created_at` | `timestamptz` NOT NULL default `now()` | |

`UNIQUE (widget_id, origin)`.

## Derived states

- `active` = `revoked_at IS NULL AND (expires_at IS NULL OR expires_at > now())`
- `expired` = `revoked_at IS NULL AND expires_at <= now()`
- `revoked` = `revoked_at IS NOT NULL` (wins over expired)

`active_count` for the limit = active widgets of that dashboard. Expired/revoked never count.

## API shapes

### Admin (`/api/dashboards/{code}/widgets`)

```jsonc
// GET → state of the panel
{
  "items": [widget…],
  "enabled": true,              // widgets usable: installation switch + share links on
  "max_active": 50, "active_count": 2,
  "max_sites": 10, "name_max": 80,
  "share_links_enabled": true
}

// widget
{
  "id": 3, "name": "Ventas · cliente.com",
  "sites": [{"origin": "https://www.cliente.com", "development": false},
            {"origin": "http://localhost:5173", "development": true}],
  "created_by": {"id": 1, "name": "Ana Admin"},
  "created_at": "…", "expires_at": null, "revoked_at": null,
  "state": "active", "active": true,
  "theme": "dark", "language": "es",
  "show_title": true, "show_filters": true, "pdf": false,
  "visits": 12, "last_visit_at": "…",
  "test_path": "/d/ventas/widgets/3/probar"
}

// POST 201 and POST …/replace 200 add the one-time material
{
  …widget,
  "key": "…",                   // only here, only now
  "url": "https://bi.example.com/w/…",
  "snippet": "<script>…</script>\n<iframe …></iframe>"
}

// POST …/frame 200 (admins, used by the test page)
{"url": "https://bi.example.com/w/pv.3.1790000000.…", "expires_at": "…"}
```

### Public (`/api/widgets/{token}`)

```jsonc
// GET /api/widgets/{token}
{
  "widget": {
    "id": 3, "theme": "dark", "language": "es",
    "show_title": true, "show_filters": true, "pdf": false,
    "preview": false, "expires_at": null,
    // The one origin the backend confirmed for the page that framed this document (from
    // `?parent=<origin>`), or null. No name, no site list: the response never publishes them.
    "parent_origin": "https://www.cliente.com"
  },
  "dashboard": {"code": "ventas", "name": "Ventas"},
  "report": {…definition_json, "pdf": false…}   // pdf additionally ANDed with the widget
}
// then, exactly like a share link:
// GET …/data?period=&compare=&filter.x=  GET …/filters/{dimension}  POST …/pdf
// GET …/assets/{set}/{key}  GET …/images/{name}   ← these two are not charged to the ceiling
```

`GET /api/widgets/{token}?parent=<origin>` is how the page learns where it may post its height
(FR-017): the answer is `parent_origin`, that origin or null — never the widget's list, and never the
administrator's internal name. `{token}` is either a key (`[A-Za-z0-9_-]{20,128}`) or a preview ticket
(`pv.<widget id>.<unix expiry>.<hmac>`). Every widget response carries
`X-Robots-Tag: noindex, nofollow`, `Cache-Control: no-store`, `Referrer-Policy: no-referrer`
(FR-014).

### The document decision (`/api/widgets/frame/{token}`)

`200` always, for Caddy's `forward_auth`, with:

| Header | Value |
|---|---|
| `Content-Security-Policy` | the site policy (same directives as the edge default) with `frame-ancestors <the widget's sites>`; `'none'` for an unknown token; `'self'` + the sites for a preview |
| `X-Robots-Tag` | `noindex, nofollow` |
| `Cache-Control` | `no-store` |

It reads no cookie, writes nothing, and is not counted against the ceiling.

## i18n keys (backend)

`widget.unavailable` (one neutral message for revoked/expired/unknown/withdrawn), `widget.disabled`
(embedding off), `widget.share_links_off`, `widget.not_shareable`, `widget.too_many` (`{n}`),
`widget.name_required`, `widget.site_required`, `widget.site_invalid`, `widget.site_scheme`,
`widget.site_path`, `widget.site_wildcard`, `widget.site_duplicate`, `widget.too_many_sites`
(`{n}`), `widget.expiry_past`, `widget.not_found`, `widget.rate_limited`, `widget.preview_unavailable`,
`widget.key_rotated` (audit-free toast only). Spanish and English, always.

## Audit events (`app.services.audit`)

| kind | detail |
|---|---|
| `widget_created` | `widget`, `dashboard`, `name`, `sites` (origins), `expires_at` |
| `widget_updated` | `widget`, `dashboard`, `name`, `sites`, `changed` (field names) |
| `widget_key_replaced` | `widget`, `dashboard` (the key never appears) |
| `widget_revoked` | `widget`, `dashboard` |

`target_id` stays empty: it is a foreign key to `app_user` and means "the account affected",
so the widget id travels in `detail.widget` (a widget id in `target_id` is a foreign-key violation).
The actor and the address are the request's.
