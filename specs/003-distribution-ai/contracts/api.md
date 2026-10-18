# API Contract additions — feature 003

Same conventions as feature 002 ([002 contracts/api.md](../../002-auth-admin-home/contracts/api.md)):
JSON, cookie session, `X-Requested-With: fetch` on mutations, error envelope
`{"error": {"code", "message", "fields"?}}`.

## `GET /api/health` (public)

`200 {"status": "ok", "version": "0.1.0"}` · `503 {"status": "unavailable", "version": "0.1.0"}`

## `GET /api/config` (public)

```json
{
  "product_name": "Bizview AI Powered",
  "organization_name": "",
  "logo_url": null,
  "version": "0.1.0",
  "source_url": "https://github.com/<owner>/bizview",
  "license": "AGPL-3.0-or-later",
  "ai_enabled": false
}
```

`ai_enabled` is true only when a provider is set and complete (key for `anthropic`; model and base
URL for `openai_compatible`).

## `GET /api/admin/ai` (super user)

```json
{
  "enabled": true,
  "provider": "anthropic",          // "none" | "anthropic" | "openai_compatible"
  "model": "claude-opus-5-5",
  "base_url": null,                  // scheme://host[:port]/path only, never credentials/query
  "key_configured": true,
  "timeout_seconds": 30,
  "missing": []                      // settings still needed, e.g. ["AI_API_KEY"]
}
```

Errors: `401 unauthenticated`, `403 forbidden` (not super user), `403 password_change_required`.

## `POST /api/admin/ai/test` (super user)

Body: none (`{}`). Always `200` with the outcome (the test result is data, not a server error):

```json
{"ok": true, "provider": "anthropic", "model": "claude-opus-5-5", "latency_ms": 812,
 "reply": "OK", "error": null}
```

```json
{"ok": false, "provider": "anthropic", "model": "claude-opus-5-5", "latency_ms": 301,
 "reply": null, "error": {"code": "invalid_key", "message": "La clave de API no es válida."}}
```

`error.code` ∈ `not_configured`, `invalid_key`, `forbidden`, `model_not_found`, `rate_limited`,
`unreachable`, `timeout`, `refused`, `provider_error`. `reply` is truncated to 200 characters. The
key never appears in any field.
