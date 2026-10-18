# Data Model: Faster PostgreSQL extraction

**Feature**: [spec.md](./spec.md) · **Research**: [research.md](./research.md) R8

No schema migration. One JSON shape is extended.

## integration_run.rows (JSONB, existing)

Per dataset name:

| Key | Type | Notes |
|---|---|---|
| `extracted` | int | unchanged |
| `written` | int | unchanged |
| `full` | bool | unchanged |
| `path` | `"bulk"` \| `"rows"` | NEW — extraction path used; REST/SOAP datasets record `"rows"` |
| `fallback` | string, optional | NEW — SQLSTATE class name when a PostgreSQL source refused bulk export (e.g. `FeatureNotSupported`); never message text |

Readers that ignore unknown keys (API, admin screen) keep working; the admin run history shows
`path` when present.
