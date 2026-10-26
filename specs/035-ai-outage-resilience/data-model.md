# Data model: surviving an AI outage

## AIStatus (new table `ai_status`, one row)

The installation's last known AI outcome. No key material, no conversation content.

| Column | Type | Rules |
|---|---|---|
| `id` | int PK, always 1 | enforced by a check constraint |
| `last_ok_at` | timestamptz null | last successful provider call of any kind |
| `last_error_code` | text null | one of the codes in [contracts/provider-errors.md](../contracts/provider-errors.md); cleared by a success |
| `last_error_at` | timestamptz null | when that error happened |
| `last_error_detail` | text null | the redacted provider message, ≤300 chars (admin page only; never in `/api/health`) |
| `last_model` | text null | the model that answered or refused, as the provider named it |
| `updated_at` | timestamptz not null | `now()` default, bumped on every write |

**Invariants**

- One row per installation: `state.record_ok`/`state.record_error` upsert `id = 1`.
- A success sets `last_ok_at`, `last_model`, and clears `last_error_code`/`last_error_at`/
  `last_error_detail`.
- A failure sets the three error columns and never touches `last_ok_at`.
- `state.blocked_reason(db)` → the code when `last_error_code` is `no_credit`, `bad_key` or
  `model_not_found` **and** `last_error_at > coalesce(last_ok_at, -infinity)`; else `None`.
- Writes happen in their own short session (`get_sessionmaker()`), so a rolled-back turn still
  records its failure.

**State transitions**

```
(none) --first success--> healthy
(none) --first error----> <code>
healthy --error---------> <code>            (blocked when the code is non-transient)
<code> --success--------> healthy            (blocked cleared)
<code> --another error--> <code> (newer)
```

## Provider error payload (message, no new column)

Stored in `assistant_message.tool_payload["error"]` and forwarded by `message_json`:

| Field | Type | Notes |
|---|---|---|
| `code` | str | R1 code |
| `detail` | str \| null | redacted provider message, ≤300 chars |
| `provider` | str | `anthropic` \| `openai_compatible` \| `none` |
| `model` | str \| null | the configured/answered model |
| `at` | iso8601 | when the turn failed |
| `request_id` | str | 8 hex chars, same as the log line |
| `action` | str \| null | `admin_ai` \| `retry` \| null (the UI turns it into a link/button) |
| `retry_after` | float \| null | seconds the provider asked for, when given |

The message `content` keeps the human sentence so old clients and the PDF/history views still read
it.

## Structured fix (`Issue.fix_data`)

| Field | Type | Notes |
|---|---|---|
| `file` | str | project-relative path of the YAML to edit |
| `json_path` | str | JSON Pointer (`/joins`, `/metrics/ventas/label`, `/views/2/type`) |
| `op` | enum | `set` \| `append` \| `insert` |
| `value` | any | the JSON value; for `insert`, `{"index": n, "value": …}` |

**Rules that ship one** (FR-013)

| Rule code | File | Path | Op | Value |
|---|---|---|---|---|
| `unjoined_sets` | `reports/<id>/report.yaml` | `/joins` | `append` | `{left: a.col, right: b.col, type: left}` |
| `invalid_reference` (date) | `reports/<id>/report.yaml` | `/date` | `set` | `<alias>.<date column>` |
| `label_missing` | report | `/metrics/<id>/label` (+ `label_en`) | `set` | a humanised id |
| `view_type_unknown` | report | `/views/<i>/type` | `set` | the suggested type |
| `schedule_missing` | `integrations/<id>/integration.yaml` | `/schedule` | `set` | `"0 * * * *"` |
| `palette_missing` | report with a layout | `/layout/theme/palette` | `set` | the installation preset |
| `layout_filter_undeclared` | report with a layout | `/layout/…/filters/<i>` | `set`/`append` | removal (`set` to null) / the declared filter |

A fix is refused when the file's current hash differs from the hash validation saw
(`base_sha256`), or when the JSON Pointer's parent does not exist.

## Run stop reason

`assistant_auto_run.stop_reason` gains the value `blocked:ai_<code>` (`ai_no_credit`,
`ai_bad_key`, `ai_model_not_found`, `ai_rate_limited`, `ai_provider_down`). `status` keeps its
existing enum (`stopped`); the summary text and the audit line carry the same string so the bubble,
the summary and the log agree.
