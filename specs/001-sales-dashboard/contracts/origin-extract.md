# Contract: Origin Extract Queries (`custom_queries/`)

The integration worker reads the origin database **only** through the SQL files described here.
To connect a new origin, write one *profile* folder of queries that return exactly these shapes.
No Python changes are needed.

## Layout

```text
custom_queries/
├── README.md                 # this contract, kept in sync with the spec
├── sample_postgres/          # profile for the bundled synthetic origin (dev + tests)
│   ├── manifest.yaml
│   ├── sale_lines.sql
│   ├── products.sql
│   └── daily_totals.sql
└── <origin_profile>/         # the real origin, same three files + manifest
```

Selected with `ORIGIN_QUERY_PROFILE=<folder>`; connection with `ORIGIN_DATABASE_URL`, a
**read-only** user (mandatory). With `ORIGIN_ENGINE=connectorx` (default) the URL is a
ConnectorX URI (`postgresql://`, `mysql://`, `mssql://`, `oracle://`); with
`ORIGIN_ENGINE=sqlalchemy` it is a SQLAlchemy URL.

`manifest.yaml`:

```yaml
contract_version: 1          # must equal the worker's supported version
dialect: postgresql          # informational
origin_timezone: UTC         # timezone of naive timestamps returned by the queries
notes: "Who wrote it, which origin tables, known caveats"
```

## Parameters

All queries receive the same named parameters (`:name` style). The worker replaces them with
timestamp **string literals** (`'2026-09-21 00:00:00'`) before running the query, because the
fast extraction engine takes no bound parameters. Wrap each one in your engine's cast:

| Engine | Write |
|---|---|
| PostgreSQL | `CAST(:window_start AS timestamp)` |
| SQL Server | `CAST(:window_start AS datetime2)` |
| MySQL / MariaDB | `CAST(:window_start AS DATETIME)` |
| Oracle | `TO_TIMESTAMP(:window_start, 'YYYY-MM-DD HH24:MI:SS')` |

| Parameter | Type | Meaning |
|---|---|---|
| `:window_start` | timestamp | inclusive lower bound on document completion time |
| `:window_end` | timestamp | exclusive upper bound |

Timestamps are passed in `origin_timezone`. `products.sql` ignores them (full product list).

## 1. `sale_lines.sql`

One row per line of every **completed, non-cancelled** sale document and every processed return
line, with completion time in the window, for **all** origin customers (the worker keeps only
customers linked to an account).

| Column | Type | Rules |
|---|---|---|
| `origin_customer_id` | text | matches `customer_account.origin_customer_id` |
| `document_id` | text | stable id of the invoice/ticket (or return document) |
| `line_no` | integer | unique within the document |
| `line_kind` | text | `sale` or `return` |
| `completed_at` | timestamp | completion (invoice/ticket) time, **not** order creation time |
| `product_code` | text | not null |
| `quantity` | numeric | ≥ 0 (returns positive too; the worker subtracts) |
| `gross_amount` | numeric | ≥ 0, before discounts, excluding tax and shipping |
| `discount_amount` | numeric | ≥ 0, line + prorated order discount |
| `net_amount` | numeric | `gross_amount − discount_amount` |
| `currency` | text | ISO 4217 |

Required guarantees: (`document_id`, `line_no`, `line_kind`) unique per customer; cancelled
documents excluded; a document's lines all share one `completed_at`.

## 2. `products.sql`

| Column | Type | Rules |
|---|---|---|
| `origin_customer_id` | text | products are per customer; return the same product once per customer that sells it |
| `product_code` | text | not null |
| `product_name` | text | current name |
| `category_code` | text | nullable |
| `category_name` | text | nullable |

## 3. `daily_totals.sql` — reconciliation (SC-003)

Origin-side totals computed **independently** of `sale_lines.sql` (e.g. from invoice headers),
grouped by customer and **completion hour** in `origin_timezone`, for documents completed in the
window:

| Column | Type | Rules |
|---|---|---|
| `origin_customer_id` | text | |
| `completed_hour` | timestamp | completion time truncated to the hour, in `origin_timezone` |
| `net_sales` | numeric | same definition as FR-007 (returns subtracted in their own hour) |
| `orders` | integer | completed, non-cancelled sale documents |
| `units_sold` | numeric | units sold − units returned |

The worker converts each hour to the account's local date and sums, so reconciliation works for
any account timezone whose offset from `origin_timezone` is a whole number of hours (most of the
Americas and Europe). Accounts in half- or quarter-hour zones (e.g. Newfoundland, India) are
recorded as `not_run`.
If the origin has no independent source of totals, the file may reuse the `sale_lines` logic
(state this in `manifest.yaml` — reconciliation then checks the load, not the extract).

## Worker validation (fails the run, nothing published)

- Missing or extra columns, or wrong types → run `failed`, error names the column and query.
- `contract_version` mismatch → run `failed`.
- Duplicate keys in `sale_lines` → run `failed`.

## Worker validation (row rejected, run continues)

- `currency` ≠ account currency, negative quantities/amounts, or `net_amount` differing from
  `gross_amount − discount_amount` by more than 0.01 → row counted in `rejected_rows`, sample
  logged.

## Rules for query authors

- `SELECT` only; the worker's connection is read-only and the worker rejects files containing
  `INSERT`, `UPDATE`, `DELETE`, `MERGE`, `ALTER`, `DROP`, `CREATE`, `TRUNCATE`, `GRANT`.
- Filter on indexed completion-time columns so a 7-day window is cheap on the origin.
- Every change to a query is a new commit; breaking shape changes bump `contract_version`.
