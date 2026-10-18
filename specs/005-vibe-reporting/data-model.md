# Data Model: Vibe Reporting

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-29

Product tables (schema `public`, migration `0004_vibe_reporting`) plus engine-owned dataset
schemas `ds_<integration>` (research R4).

## workspace_version — *Workspace Version (applied)*

| Field | Type | Rules |
|---|---|---|
| id | bigint PK | |
| commit | text null | Git commit of the mounted checkout, when available |
| checksum | text | SHA-256 over the lock file |
| lock | jsonb | the validated `bizview.lock` |
| artifacts | jsonb | `{integrations: {id: integration.yaml as JSON + SQL/request texts}, reports: {id: report.yaml as JSON}}` |
| specs | jsonb | per entry: spec folder, status, title, sha256 (no spec text needed to run) |
| state | text | `active` \| `previous` \| `archived`; exactly one `active` (partial unique index) |
| applied_at | timestamptz | |
| applied_by | bigint FK → app_user | |

Rollback swaps `active` and `previous`. Older versions become `archived` (kept for audit).

## integration_run — *Integration Run*

| Field | Type | Rules |
|---|---|---|
| id | bigint PK | also the data version for reports using the integration |
| integration_id | text | |
| version_id | bigint FK → workspace_version | |
| kind | text | `incremental` \| `full` \| `manual_incremental` \| `manual_full` |
| status | text | `running` → `succeeded` \| `failed` \| `skipped` |
| window_start, window_end | timestamptz null | |
| started_at, finished_at | timestamptz | |
| rows | jsonb | `{dataset: {extracted, written, rejected}}` |
| checks | jsonb | `[{type, ok, detail}]` |
| message | text null | error message, credentials redacted |
| requested_by | bigint FK → app_user null | manual runs |

Index `(integration_id, started_at desc)`. A `running` row older than the time limit is marked
`failed` by the next run.

## integration_run_request

Queue for manual runs: `id`, `integration_id`, `kind`, `requested_by`, `requested_at`,
`taken_at null`, `run_id null`.

## report_cache

`report_id`, `selection_hash`, `data_version` (max run id of used integrations), `payload jsonb`,
`created_at`; PK `(report_id, selection_hash, data_version)`; purged daily. Narratives are cached
the same way (`kind = 'narrative'`).

## api_token — *Access Token*

| Field | Type | Rules |
|---|---|---|
| id | bigint PK | |
| user_id | bigint FK → app_user | super user in this version |
| name | text | 1–60 chars |
| token_hash | bytea | SHA-256 of the 32-byte token (shown once) |
| scopes | text[] | `{describe}` |
| created_at, expires_at | timestamptz | default 90 days |
| last_used_at | timestamptz null | |
| revoked_at | timestamptz null | |

## dashboard (extended, feature 002)

Adds `report_id text null unique` and `managed_by text` (`product` \| `workspace`). Applying a
version creates/updates rows for its reports (status `available`), and sets removed reports to
`hidden` (grants kept). The seeded `ventas` placeholder from feature 002 is replaced by the
workspace report with the same code when Customer B's workspace is applied.

## Dataset schemas `ds_<integration>`

One table per dataset from the contract (columns, types, primary key, `NOT NULL`), plus
`_run_id bigint` and `_loaded_at timestamptz`; index on `date_column`. Optional
`ds_<integration>._agg_<report>_daily` materialisations created by the report engine. Owned by the
engine role; readable by the backend.

## audit_event.kind (extended)

`workspace_validated`, `workspace_applied`, `workspace_rolled_back`, `integration_run_requested`,
`token_created`, `token_revoked`, `source_described`.
