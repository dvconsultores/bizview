# Contract — the source structure API

Every route requires a super user (the whole Fuentes de datos area does); the ones that change
something require a recent re-authentication (`recent_reauth`). Responses are JSON; errors use the
product's envelope `{"error": {"code", "message", "key", "params", …}}`.

The routes that only read structure accept the same `token_or_session("describe")` dependency the
existing `/describe` does, so a `describe` token can download a pack for an authoring pipeline.

---

## Structure

### `GET /api/sources/{name}/structure?format=json|md`

The pack, built by the single generator (`cli/bizview_cli/structure.py`).

| | |
|---|---|
| Auth | super user session, or an API token with the `describe` scope |
| Query | `format` = `json` (default) or `md`; `path` (REST/Supabase only) — the endpoint to shape |
| 200 `json` | `application/json` — the wrapper of [data-model.md](../data-model.md#structurejson) |
| 200 `md` | `text/markdown; charset=utf-8`, `Content-Disposition: attachment; filename="structure.md"` |
| Audit | `source_described`, detail `{"source", "format", "key_id"}` |
| Errors | 404 `not_found`; 502 `source_error` with the product's own line (never the host or the credential) |

### `PUT /api/sources/{name}/structure/notes`

`{"notes": "…"}` (≤ 4 000 chars) → `{"notes": "…"}`. Audit `source_structure_notes_updated`
(counts only: `{"source", "chars"}`).

### `PUT /api/sources/{name}/structure/columns`

`{"schema": "public", "table": "orders", "column": "customer_email", "personal": true}` → the
stored override. Audit `source_structure_flag_changed` with the four fields (they are names, never
values). 422 when the column is not in the current describe output.

## Sample requests (REST and Supabase)

### `GET /api/sources/{name}/samples` → `{"items": [SampleRequest]}`

`SampleRequest` = `{id, name, method, path, params, notes, last_shape, last_suggestions,
last_status, last_error, last_run_at}`. `last_shape` is keys and types only.

### `POST /api/sources/{name}/samples`

`{"name", "path", "params", "notes"}` → 201 `SampleRequest`. 409 on a duplicate name; 422 when the
path is absolute or contains `://`; audit `source_sample_created` `{"source", "name"}`.

### `PATCH /api/sources/{name}/samples/{id}` · `DELETE …/{id}`

Same body minus the name uniqueness rules. Audits `source_sample_updated`, `source_sample_deleted`.

### `POST /api/sources/{name}/samples/{id}/run`

Runs the sample through the source's stored credential and returns

```json
{"status": 200, "shape": {"data": [{"id": "integer"}]},
 "records": "$.data", "fields": {"$.id": "integer"},
 "timestamp_units": "iso8601", "pagination": null, "duration_ms": 412}
```

and persists `last_*`. Audit `source_sample_run` `{"source", "name", "status"}`.
Errors: 502 `source_error` (the product's line, secrets stripped), 504 `timeout`, 422 when the
source is not REST/Supabase or the method is not `GET`.

## Chat

### `GET /api/sources/{name}/chat` → `{"turns": [...], "cap": 100000, "spent_today": 1052}`

### `POST /api/sources/{name}/chat`

`{"question": "…"}` (1–2 000 chars) → the object of
[data-model.md](../data-model.md#chat-request-and-answer).

| Situation | Answer |
|---|---|
| `AI_PROVIDER=none` | 409 `ai_not_configured`, `extra.ai.action = "admin_ai"` |
| guard refuses (data / write / action) | 200, `refused: true`, no provider call, no tokens |
| provider failure | 502 `ai_<code>` (`ai_no_credit`, `ai_bad_key`, …) with `extra.ai = {code, action, detail}` — the 035 vocabulary |
| daily cap reached | 429 `ai_chat_cap` with `extra.ai = {cap, spent_today}` |
| unknown objects in the answer | 200, `unknown: [{name, kind}]` |

Audit on every answered question: `source_chat_asked` `{"source", "tokens_in", "tokens_out",
"model"}` — counts only, never the question text.

### `DELETE /api/sources/{name}/chat` → 204, the user's own turns for this source. Audit
`source_chat_cleared` `{"source", "turns"}`.
