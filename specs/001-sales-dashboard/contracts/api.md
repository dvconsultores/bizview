# Contract: Dashboard HTTP API

Base path `/api`, served same-origin with the frontend. JSON in and out (UTF-8), except the PDF
export, which returns `application/pdf`. The generated OpenAPI document (`/api/openapi.json`) is
the machine-readable form of this contract and must match it.

## Conventions

- **Auth**: session cookie `sid` (`HttpOnly; Secure; SameSite=Lax`). Unauthenticated → `401`.
  Wrong role → `403`. State-changing requests (`POST`, `PATCH`, `DELETE`) require header
  `X-Requested-With: fetch` and a same-site `Origin`, else `403`.
- **Account scope**: customer endpoints never take an account id; it comes from the session.
- **Money**: decimal strings with 2 decimals (`"12345.67"`); currency in `/api/me`.
- **Percentages**: decimal numbers, `0.125` = 12.5 %; `null` when the base is zero.
- **Errors**: `{"error": {"code": "string", "message": "string", "fields": {"name": "msg"}}}`.
  Codes: `unauthenticated`, `forbidden`, `locked`, `validation_error`, `not_found`,
  `rate_limited`, `internal`.
- **Caching**: dashboard `GET`s return `ETag` (data version + query) and
  `Cache-Control: private, no-cache`; `If-None-Match` → `304`.

### Selection parameters (all dashboard endpoints and the PDF export)

| Param | Values | Default |
|---|---|---|
| `preset` | `today`, `yesterday`, `last_7_days`, `mtd`, `last_month`, `qtd`, `ytd`, `last_12_months`, `custom` | `mtd` |
| `from`, `to` | `YYYY-MM-DD`, required iff `preset=custom`, `from ≤ to`, span ≤ 3 years | — |
| `compare` | `previous`, `yoy` | `previous` |
| `category` | category code, or `none` for uncategorised | all |

Resolved periods are echoed back in every response:

```json
"selection": {
  "preset": "mtd",
  "period": {"from": "2026-09-01", "to": "2026-09-28", "partial": true},
  "comparison": {"basis": "previous", "from": "2026-08-01", "to": "2026-08-28"},
  "category": null,
  "clipped": false
},
"freshness": {"last_updated_at": "2026-09-28T14:30:05Z", "stale": false, "data_version": 1842}
```

## Auth

| Method & path | Body | Success | Errors |
|---|---|---|---|
| `POST /api/auth/login` | `{email, password}` | `204` + `Set-Cookie` | `401 unauthenticated` (generic), `423 locked` with `retry_after_seconds` |
| `POST /api/auth/logout` | — | `204`, session deleted | — |
| `POST /api/auth/password/request` | `{email}` | `202` always (no account enumeration) | `429` |
| `POST /api/auth/password/confirm` | `{token, new_password}` | `204` | `400 validation_error` (expired/used token, weak password: min 10 chars) |
| `GET /api/me` | — | `{user: {id, email, full_name, role}, account: {name, currency, timezone} \| null}` | `401` |

## Dashboard (role `customer`)

### `GET /api/dashboard/summary`

```json
{
  "selection": {…}, "freshness": {…},
  "measures": {
    "net_sales":       {"value": "15230.50", "comparison": "14002.10", "delta": "1228.40", "delta_pct": 0.0877},
    "orders":          {"value": 412, "comparison": 398, "delta": 14, "delta_pct": 0.0352},
    "units_sold":      {"value": "1290", "comparison": "1301", "delta": "-11", "delta_pct": -0.0085},
    "avg_order_value": {"value": "36.97", "comparison": "35.18", "delta": "1.79", "delta_pct": 0.0509}
  }
}
```

`avg_order_value.value` is `null` when orders = 0. `delta_pct` is `null` when the comparison is
zero; the client shows "new" if value > 0, "—" otherwise.

### `GET /api/dashboard/trend`

Extra params: `measure` = `net_sales` | `orders` | `units_sold` (default `net_sales`);
`grain` = `auto` | `day` | `week` | `month` (default `auto`: day ≤ 31 days, week ≤ 91 days,
month otherwise).

```json
{
  "selection": {…}, "freshness": {…}, "measure": "net_sales", "grain": "day",
  "points": [
    {"bucket_start": "2026-09-01", "value": "512.00", "comparison_value": "480.10", "partial": false}
  ]
}
```

Comparison points are aligned by bucket position (1st day ↔ 1st day of comparison period).

### `GET /api/dashboard/products`

Extra params: `rank_by` = `net_sales` | `units` (default `net_sales`); `q` (name or code,
case- and accent-insensitive, ≤ 100 chars); `limit` 1–50 (default 10); `offset` ≥ 0.

```json
{
  "selection": {…}, "freshness": {…},
  "totals": {"net_sales": "15230.50", "units": "1290"},
  "total_count": 184,
  "items": [
    {"product_code": "SKU-001", "name": "Vitamin paste 100g", "category": {"code": "SUP", "name": "Supplements"},
     "net_sales": "2210.00", "units": "130", "share_pct": 0.1451, "comparison_net_sales": "1900.00", "delta_pct": 0.1632}
  ]
}
```

`totals` and `share_pct` respect `category` but not `q` (search filters the list, not the base).

### `GET /api/dashboard/products/{product_code}`

Same params as summary + trend (`measure`, `grain`). Returns
`{selection, freshness, product: {code, name, category}, measures: {net_sales, units_sold}, trend: {grain, points}}`.
`404 not_found` if the product does not belong to the account.

### `GET /api/dashboard/categories`

`{"items": [{"code": "SUP", "name": "Supplements"}, {"code": null, "name": null}]}` — the null
entry exists only if uncategorised products exist.

## Export (role `customer`)

### `POST /api/exports/pdf`

Body: the selection parameters as JSON. The PDF is always in Spanish.
Response `200 application/pdf`, `Content-Disposition: attachment; filename="ventas-2026-09-01_2026-09-28.pdf"`.
Figures are produced by the same services as the endpoints above (FR-021). Target p95 < 10 s.
Audited as `pdf_export`.

## Admin (role `admin`)

| Method & path | Body / params | Response |
|---|---|---|
| `GET /api/admin/accounts` | `?q=` | list of accounts with user counts |
| `POST /api/admin/accounts` | `{name, origin_customer_id, timezone, currency}` | `201` account; `409` if origin id already linked |
| `PATCH /api/admin/accounts/{id}` | any of `{name, timezone, currency, is_active}` | `200`; timezone change schedules a full rebuild |
| `GET /api/admin/accounts/{id}/users` | — | users of the account |
| `POST /api/admin/accounts/{id}/users` | `{email, full_name}` | `201`; sends a "set your password" email (7-day token) |
| `PATCH /api/admin/users/{id}` | `{is_active}` or `{unlock: true}` | `200`; deactivation deletes all sessions |
| `GET /api/admin/refresh-runs` | `?limit=20` | latest runs with status, counts, reconciliation |

Bootstrap: `python -m app.cli create-admin --email …` (prompts for password).

## Operations

### `GET /api/health` (no auth)

`200 {"status": "ok" | "degraded", "database": "ok", "last_refresh": {"finished_at": "…", "status": "succeeded", "stale": false}}`
— `degraded` when data is stale; `503` when the database is unreachable. No customer data.
