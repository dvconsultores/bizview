# Data Model: Sales Dashboard for Customers

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-28

Dashboard-owned PostgreSQL database, versioned with Alembic from `backend/` (constitution §3).
The origin database is **not** modelled here; its extract shape is in
[contracts/origin-extract.md](./contracts/origin-extract.md).

Schemas: `app` (accounts, users, sessions, audit), `mart` (sales models served to users),
`ops` (refresh runs). Money: `numeric(18,4)` in the database, decimal strings in the API.

## Database roles

| Role | Used by | Rights |
|---|---|---|
| `dash_owner` | Alembic migrations | owns all objects |
| `dash_api` | backend | read `mart`, read/write `app`, read `ops`, insert `ops.rebuild_request`; **RLS enforced** on `mart` |
| `dash_worker` | integration worker | read/write `mart` and `ops`, read `app.customer_account` |

RLS policy on every `mart` table except `stg_sale_line`:
`USING (account_id = current_setting('app.account_id')::bigint)` for `dash_api`;
`USING (true)` for `dash_worker`. Admin endpoints never read `mart` rows.

## app.customer_account — *Customer Account*

| Field | Type | Rules |
|---|---|---|
| id | bigint PK | identity |
| name | text | required, 1–120 chars |
| origin_customer_id | text | required, **unique**; the customer's id in the origin |
| timezone | text | required, valid IANA name (e.g. `America/Caracas`) |
| currency | char(3) | required, ISO 4217 |
| is_active | boolean | default true; inactive → its users cannot sign in |
| created_at, updated_at | timestamptz | |

## app.app_user — *User*

| Field | Type | Rules |
|---|---|---|
| id | bigint PK | |
| email | citext | required, **unique**, valid format |
| full_name | text | required |
| role | text | `customer` or `admin` |
| account_id | bigint FK → customer_account | required when role = `customer`, null for `admin` |
| password_hash | text | Argon2id; null until the user sets a password |
| is_active | boolean | default true |
| failed_attempts | int | reset on success |
| locked_until | timestamptz | set to now + 15 min on the 5th consecutive failure (FR-033) |
| created_at, updated_at, last_login_at | timestamptz | |

Check: `(role = 'customer') = (account_id IS NOT NULL)`.

State: `invited` (no password) → `active` (password set) ⇄ `locked` (temporary) ;
`active` → `deactivated` (is_active = false; all sessions deleted).

## app.user_session

| Field | Type | Rules |
|---|---|---|
| id_hash | bytea PK | SHA-256 of the cookie's random 32-byte id (raw id never stored) |
| user_id | bigint FK → app_user | on delete cascade |
| created_at | timestamptz | absolute expiry = created_at + 30 days |
| last_seen_at | timestamptz | idle expiry = last_seen_at + 7 days; updated at most once per 5 min |
| user_agent | text | informational |

## app.password_token

| Field | Type | Rules |
|---|---|---|
| id | bigint PK | |
| user_id | bigint FK → app_user | |
| token_hash | bytea | SHA-256 of the emailed token |
| purpose | text | `set` (new user invite) or `reset` |
| expires_at | timestamptz | reset: 30 min; set: 7 days |
| used_at | timestamptz | single use |

## app.audit_event — *Audit Event*

| Field | Type | Rules |
|---|---|---|
| id | bigint PK | |
| occurred_at | timestamptz | |
| user_id | bigint null | null if the email did not match a user |
| account_id | bigint null | |
| kind | text | `login_ok`, `login_failed`, `login_locked`, `logout`, `pdf_export`, `password_reset`, `admin_change` |
| detail | jsonb | no passwords, no tokens |
| ip | inet | |

Retention: 12 months (purged by the nightly worker job).

## mart.dim_product — *Product* / *Product Category*

| Field | Type | Rules |
|---|---|---|
| account_id | bigint | PK part |
| product_code | text | PK part; origin product code |
| name | text | current name (renames apply to all history) |
| category_code | text null | null → "Uncategorised" |
| category_name | text null | |
| updated_at | timestamptz | |

Categories are the distinct `(category_code, category_name)` of an account's products.

## mart.stg_sale_line

Unlogged staging table with the columns of the `sale_lines` extract plus `run_id`. Truncated per
account at the start of each load; no RLS; not readable by `dash_api`.

## mart.fact_sale_line

| Field | Type | Rules |
|---|---|---|
| account_id | bigint | |
| document_id | text | origin sale document id |
| line_no | int | |
| line_kind | text | `sale` or `return` |
| completed_at | timestamptz | when the document was completed |
| local_date | date | `completed_at` in the account timezone — the day the sale counts on |
| product_code | text | |
| quantity | numeric(18,4) | ≥ 0 |
| gross_amount | numeric(18,4) | ≥ 0, before discounts, excl. tax/shipping |
| discount_amount | numeric(18,4) | ≥ 0 |
| net_amount | numeric(18,4) | = gross − discount (validated on load, 0.01 tolerance) |
| run_id | bigint | refresh run that wrote it |

PK: `(account_id, document_id, line_no, line_kind)`. Index: `(account_id, local_date)`.
Only completed, non-cancelled documents are loaded (the extract contract guarantees it).

## mart.agg_sales_daily — *Daily Sales Summary*

| Field | Type | Definition (FR-007) |
|---|---|---|
| account_id | bigint | PK part |
| local_date | date | PK part |
| gross_sales | numeric | Σ gross_amount of `sale` lines |
| discounts | numeric | Σ discount_amount of `sale` lines |
| returns_value | numeric | Σ net_amount of `return` lines |
| net_sales | numeric | Σ net_amount(`sale`) − returns_value |
| orders | int | count distinct document_id of `sale` lines |
| units_sold | numeric | Σ quantity(`sale`) − Σ quantity(`return`) |
| units_returned | numeric | Σ quantity(`return`) |

Weekly/monthly values are sums of daily rows. Average order value = Σ net_sales ÷ Σ orders
(null when orders = 0).

## mart.agg_category_daily — *Daily Sales Summary* by category

Same measures as `agg_sales_daily`, per account × category × day, so a category filter gives
correct **orders** and **average order value** (orders here = distinct sale documents with at
least one line in the category; summing products would count a multi-item order twice).

| Field | Type | Rules |
|---|---|---|
| account_id | bigint | PK part |
| category_key | text | PK part; `category_code`, or `''` for uncategorised |
| local_date | date | PK part |
| net_sales, gross_sales, discounts, returns_value | numeric | as `agg_sales_daily`, restricted to the category's lines |
| orders | int | distinct `document_id` of `sale` lines in the category |
| units_sold, units_returned | numeric | as `agg_sales_daily`, restricted to the category |

Category orders summed over categories can exceed total orders (one order spans categories);
total figures always come from `agg_sales_daily`.

## mart.agg_product_daily / mart.agg_product_monthly — *Product Sales Summary*

| Field | Type | Rules |
|---|---|---|
| account_id | bigint | PK part |
| product_code | text | PK part |
| local_date / month | date | PK part (month = first day of month) |
| net_sales | numeric | as above, per product |
| units | numeric | units sold − units returned |

PKs lead with `(account_id, local_date|month)` for range scans.

## ops.refresh_run — *Refresh Run*

| Field | Type | Rules |
|---|---|---|
| id | bigint PK | also the **data version** exposed to the API |
| kind | text | `incremental` or `full` |
| status | text | `running` → `succeeded` \| `failed` \| `skipped` |
| started_at, finished_at | timestamptz | |
| window_start, window_end | timestamptz | extract window |
| accounts_processed | int | |
| rows_extracted, rows_written | bigint | |
| rejected_rows | bigint | rows failing contract validation (e.g. currency mismatch) |
| reconciliation_status | text | `ok`, `mismatch`, `not_run` |
| reconciliation_diffs | jsonb | per account/day differences, capped at 100 entries |
| error | text | message on failure (no credentials) |

A run left `running` by a crash is marked `failed` by the next run that acquires the lock.
"Last updated" shown to users = `finished_at` of the latest `succeeded` run; stale when older than
60 minutes (2 × 30-minute interval).

## ops.rebuild_request

Queued full rebuild for one account (e.g. after a timezone change, FR-011).

| Field | Type | Rules |
|---|---|---|
| id | bigint PK | |
| account_id | bigint FK → customer_account | |
| reason | text | e.g. `timezone_change` |
| requested_at | timestamptz | |
| requested_by | bigint FK → app_user | admin |
| done_run_id | bigint null FK → refresh_run | set when the rebuild succeeds |

The worker checks pending requests at the start of every incremental run.

## Relationships

```text
customer_account 1 ─── * app_user 1 ─── * user_session
customer_account 1 ─── * dim_product
customer_account 1 ─── * fact_sale_line * ─── 1 dim_product (account_id, product_code)
customer_account 1 ─── * agg_sales_daily / agg_category_daily / agg_product_daily / agg_product_monthly
refresh_run 1 ─── * fact_sale_line (run_id)
```

## Validation rules from requirements

- FR-002: every `mart` read is scoped by `account_id` (RLS + repository signature).
- FR-011: `local_date` computed with the account timezone at load time; changing an account's
  timezone triggers a full rebuild of that account.
- FR-012: history ≥ 24 full months + current year retained; nothing is purged from `mart`.
- FR-025: incremental window = 7 local days back from now.
- Currency: extract rows whose currency ≠ account currency are rejected and counted.
