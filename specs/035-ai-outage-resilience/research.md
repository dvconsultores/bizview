# Research: surviving an AI outage

Decisions taken while designing 035. Each one is what the implementation follows.

## R1 — The stable code set

**Decision**: one closed list, used by the API, the i18n catalogues, the bubble and `/api/health`:

| Code | Cause | Action shown | Transient |
|---|---|---|---|
| `no_credit` | 402 | Ir a Administración → IA | no |
| `bad_key` | 401, 403 | Ir a Administración → IA | no |
| `model_not_found` | 400/404 whose body names the model | Ir a Administración → IA | no |
| `rate_limited` | 429 (with `retry_after` when sent) | Reintentar | yes |
| `context_too_long` | 400 naming length/tokens | Reintentar | no |
| `provider_down` | 5xx, timeout, connection error | Reintentar | yes |
| `invalid_tool_call` | malformed tool JSON after one repair round | — | no |
| `provider_error` | anything else | — | no |
| `not_configured` | AI off or incomplete | Ir a Administración → IA | no |
| `refused` | provider content filter | — | no |

`invalid_key` is renamed `bad_key`, `forbidden` is merged into it (the reader's fix is identical),
and `timeout`/`unreachable` become `provider_down` with the transport detail kept in the message —
the reader cannot act differently on them, and Auto treats all three as transient.
*Alternatives*: keeping the old names and adding the new ones (rejected: two vocabularies for one
thing, and the spec names the codes); keeping `timeout` separate (rejected: `_turn` only retried it,
which the transient path now covers).

## R2 — Mapping per provider, including DeepSeek's Anthropic endpoint

**Decision**: a single mapping module (`app/ai/errors.py`) with three entry points — an HTTP
status, an exception, and a body — used by both providers:

- Anthropic SDK exception classes map directly (`RateLimitError`, `AuthenticationError`,
  `PermissionDeniedError`, `NotFoundError`, `BadRequestError`, `APITimeoutError`,
  `APIConnectionError`), with `APIStatusError` falling back to the status table (402, 404, 429,
  ≥500).
- `BadRequestError`/400 bodies are scanned for context markers first (they win over model markers,
  the reader acts by shortening), then model markers.
- OpenAI-compatible: the same table over `r.status_code`, same body scans.
- Recorded bodies used in tests: DeepSeek `402 {"error":{"message":"Insufficient Balance"…}}`,
  `400 {"error":{"message":"Model Not Exist"}}`, Anthropic `429` with `retry-after: 7`, an OpenAI
  `500` HTML page, and a `400` naming `maximum context length`.

## R3 — Where the AI status lives

**Decision**: a table `ai_status` with exactly one row (`id = 1`), columns `last_ok_at`,
`last_error_code`, `last_error_at`, `last_error_detail` (redacted, ≤300 chars), `last_model`,
`updated_at`; written through `app/ai/state.py` in its own short session so a failed turn's
transaction never decides whether the status is recorded.
*Alternatives*: a column on `app_setting`/`Settings` (today the product keeps per-area tables —
`appearance`, `telegram`, `email` — so a table is the local convention); in-process memory
(rejected: the worker and the backend are different processes and a restart would forget the
outage).

## R4 — Refusing without a provider call

**Decision**: `state.blocked_reason(db)` returns the code when the last error is one of
`no_credit`, `bad_key`, `model_not_found` and is newer than `last_ok_at`; the three entry points
call it **before** any provider access:

- `ensure_auto_contract` (Auto contract confirmation, 028) → answers the refusal message instead of
  creating the contract;
- `_command_turn` before starting a `/speckit-*` run → same message, run not created;
- `_turn` when the user message is a bare «continua»/«continúa»/«corrige»/«sigue» → same message.

The refusal text carries the code, the reason and the action link, in both languages.
*Alternative*: a global "AI down" guard in the HTTP layer (rejected: it would also block the fix
endpoint, editing, validation and Probar — the very things that must keep working).

## R5 — Retry budget and stop rule

**Decision**: per turn, keep `failures: dict[code, int]`. Transient codes (`rate_limited`,
`provider_down`) get **one** retry, sleeping `min(retry_after or 2 s, 60 s)`; non-transient codes
get none. Two consecutive errors with the same code (transient after its retry, or non-transient at
the second attempt) stop the turn with `end("error", "blocked:ai_<code>")`, which closes the run
with `stop_reason = "blocked:ai_<code>"` and `status = "stopped"`, keeps `working_state` and the
draft, and posts the summary line (015 US5).
*Alternative*: exponential backoff (rejected: an outage is not a hiccup; the reader must be told).

## R6 — Shape of a deterministic fix

**Decision**: `Issue.fix_data: {"file": "<project-relative path>", "json_path": "/joins",
"op": "set|append|insert", "value": <json>}` — JSON Pointer into the YAML document, no SQL, no
expression evaluation, produced by the rule that knows the correction. Rendered as `Arreglo: …`
today and posted back verbatim by **Aplicar arreglo**. `append` appends to an array (creating it),
`insert` takes `{"index": n}` in `value`, `set` replaces the target (creating parents).
*Alternatives*: a unified-diff patch (rejected: fragile against whitespace and comments and it
can't be validated); free text for the model to interpret (rejected: the whole point is not needing
a model).

## R7 — Pre-schema and post-schema rules

**Decision**: the validator runs *fixable* rules twice in the pipeline:

- **before** the JSON-schema gate (in `_load_entries`, right after `_read_yaml`), so a file whose
  only problem is a missing `label`, an unknown view `type` or a missing `schedule` still gets a
  structured fix (today a schema failure removes the entry from further checks);
- **after** it, in `_check_report`/`layout` for the rules that need the parsed model (missing
  `joins`, missing `date`, undeclared layout filter, missing palette).

The schema error keeps being reported: applying the fix makes it disappear on the next validation.
*Alternative*: relaxing the schemas (rejected: it would weaken validation for every installation).

## R8 — How the bubble gets its data

**Decision**: the failure payload travels with the message:
`assistant_message.tool_payload["error"] = {code, detail, provider, model, at, request_id, action}`
and `message_json` forwards it (028 already forwards `contract`/`suggestions`/`scope` the same
way), so no extra request and no new column.
*Alternative*: a dedicated column (rejected: a migration for something `tool_payload` already
models); the frontend re-deriving the code from the text (rejected: never do that).

## R9 — Listing the provider's models

**Decision**: `Provider.list_models() -> list[str] | None` — OpenAI-compatible `GET /models`
(`data[].id`), Anthropic SDK `client.models.list()`; `None` when the endpoint is missing or fails
(a 404 from a compatible endpoint is normal, not an error). The Probar card lists them and marks the
configured one when absent.
*Alternative*: shipping a static list per provider (rejected: it goes stale and hides the problem).

## R10 — Identifying a failure

**Decision**: each turn mints a short id (`uuid4().hex[:8]`) reused in the error payload, the log
line (`assistant provider failure <id>: <code> …`) and the «Detalles técnicos» block, together with
the exact command `docker logs --tail 200 bizview-backend | grep -i "AI"`. No new middleware.
*Alternative*: a request-id middleware for the whole API (bigger, and the SSE/worker paths do not
share a request).
