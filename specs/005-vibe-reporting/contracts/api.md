# API and CLI Contract — feature 005

Conventions of features 002–004 apply. All workspace and run endpoints are super user only;
mutations need step-up (feature 004).

## Workspace

| Method & path | Result |
|---|---|
| `GET /api/workspace` | `{mounted: {path, commit, checksum, read_at} \| null, active: Version \| null, previous: Version \| null}` |
| `POST /api/workspace/validate` | `{ok, errors: [{entry, code, message}], warnings: [...], changes: {added:[], changed:[], removed:[], dataset_changes:[]}}` — reads the mounted folder |
| `POST /api/workspace/apply` | `{version: Version}`; `409 invalid_workspace` with errors; `409 lock_mismatch` when files changed after validation |
| `POST /api/workspace/rollback` | re-activates `previous`; `404` if none |

`Version`: `{id, commit, checksum, applied_at, applied_by, integrations: [id], reports: [id]}`.

Error codes in `errors[].code`: `missing_spec`, `spec_incomplete` (missing file), `spec_not_approved`,
`open_tasks`, `lock_missing`, `lock_mismatch`, `schema_error`, `unknown_source`, `unknown_dataset`,
`unsafe_sql`, `invalid_reference`, `duplicate_id`, `breaking_dataset_change`.

## Integrations and runs

| Method & path | Result |
|---|---|
| `GET /api/integrations` | list: id, source, schedule, datasets, last run, next run, paused (source disabled) |
| `GET /api/integrations/{id}/runs?limit=` | runs: started, finished, kind (`incremental`/`full`/`manual`), window, rows per dataset, checks, outcome, message |
| `POST /api/integrations/{id}/run` | `{"kind": "incremental"\|"full"}` → `202 {request_id}` (worker picks it up) |

## Reports (viewers; access per report)

| Method & path | Result |
|---|---|
| `GET /api/reports/{id}` | definition for rendering: title, metrics (label, format, better), dimensions, periods, compare, views, filters, pdf, ai_narrative.enabled |
| `GET /api/reports/{id}/data?period=mtd&from=&to=&compare=previous_period&filter.category=` | `{selection, freshness, views: [{type, …data}]}`; ETag = data version + selection |
| `GET /api/reports/{id}/narrative?…same selection…` | `{text, generated_at}`; `404` when disabled; `503 ai_unavailable` when AI off |
| `POST /api/reports/{id}/pdf` | `application/pdf` for the selection |

Reports appear in `GET /api/dashboards` (feature 002) with `path: /r/{id}`.

## Tokens and describe

| Method & path | Result |
|---|---|
| `GET /api/tokens` | own tokens (name, scopes, created, expires, last used) — never the token |
| `POST /api/tokens` | `{name, scopes: ["describe"], expires_days}` (step-up) → `{token}` shown once |
| `DELETE /api/tokens/{id}` | revoke |
| `GET /api/sources/{name}/describe` | `Authorization: Bearer <token>` or super-user session; structure only (see research R8) |

## CLI (`bizview-cli`, used inside the workspace)

```text
bizview init <folder> --name <customer>      # new workspace (git init, specify init, preset, extension)
bizview validate [--write-lock]              # static validation; writes bizview.lock when valid
bizview describe "<source name>"             # needs BIZVIEW_URL + BIZVIEW_TOKEN
bizview version
```

Exit codes: `0` ok · `1` validation errors · `2` usage/config error · `3` network/auth error.
