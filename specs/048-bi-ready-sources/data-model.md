# Data model — BI-ready sources

## The declaration (new: `data_source.bi_ready`, JSONB)

Kept on the source row, next to the settings it governs. Empty `{}` means "not BI-ready".

| Field | Type | Notes |
|---|---|---|
| `enabled` | bool | the source may be read directly |
| `schemas` | list of text | the only schemas reports may reach; empty means "none" — never "all" |
| `objects` | list of text, optional | `schema.object` inside the those schemas; absent means every object there |
| `timeout_s` | int | 1–300; default from `DIRECT_*` settings |
| `cache_ttl_s` | int | 0–86400; default 300 (today's `cache_seconds`) |
| `max_rows` | int | 1–1 000 000; default 50 000 |
| `max_parallel` | int | 1–20; default `DIRECT_REPORT_CONCURRENCY` |
| `timezone` | text | IANA name; how a `date` column is read |
| `verified_at` | timestamptz | when the read-only proof last passed |
| `verified_ok` | bool | the last proof's outcome |

Rules the database enforces (`CheckConstraint`s on the JSONB where cheap, the API elsewhere):
`schemas` may not contain `pg_catalog`, `information_schema`, `pg_toast*`, `app_test_*`,
`preview_*` — the deny-list is not overridable by declaration; `timeout_s`, `max_rows`,
`max_parallel` and `cache_ttl_s` bound as above.

**Transitions**: turning it on sets `enabled` and runs the proof; turning it off only sets
`enabled = false` (the scope is remembered, so turning it back on is one click). Every change is
audited (`source_bi_ready_changed`), with the previous and the new declaration.

## The report

```yaml
direct:
  source: Almacén ventas          # a source name, or `bi`
  tables:
    v: reporting.v_ventas_dia     # new form: the columns come from the source's structure
    p:
      table: reporting.dim_producto   # 019's form: a declared column contract
      columns: {id: {type: bigint}, nombre: {type: text}}
joins:
  - {left: v.producto_id, right: p.id}
date: v.fecha
allow_personal: [v.email]         # only with the decision recorded in the spec
materialize: none                 # none | daily
```

Invariants: `direct` and `uses` are mutually exclusive; every object is inside the declaration's
scope; every referenced column exists in the structure (new form) or the declared contract (old
form); a join is between existing columns; `allow_personal` may only name columns the structure
flags as personal.

## Direct read (exists: `direct_read_log`)

One row per executed query: `report_id`, `source`, `duration_ms`, `rows`, `outcome`,
`stale_served`, `occurred_at`. FR-010 reads it; nothing new is stored.

## Snapshot (new: `direct_snapshot`, Phase 4)

| Column | Type | Notes |
|---|---|---|
| `id` | bigint identity | |
| `report_id` | text | |
| `day` | date | the day the figures answer for |
| `payload` | jsonb | what the engine returned (figures, never rows) |
| `selection` | jsonb | the period/filters/compare the figures answer for |
| `source` | text | the source at snapshot time |
| `created_at` | timestamptz | |

Unique on `(report_id, day, selection fingerprint)`. The dashboard reads the newest row not older
than the report's TTL-ish window and labels it; no row is ever edited.

## Entities the frontend shows

- **Source page → "Lista para BI"**: the toggle, the schema picker (from `describe`), the object
  picker, the three numbers, the timezone, the proof badge with its date, and the 24-hour health.
- **Source page → health**: runs, p50/p95 duration, failures by outcome, "answered from cache" share.
