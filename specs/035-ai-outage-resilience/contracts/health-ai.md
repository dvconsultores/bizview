# Contract: `/api/health` AI block

Public, unauthenticated, no secrets.

```http
GET /api/health
200 {"status":"ok","version":"0.1.0","commit":"abc1234",
     "ai":{"configured":true,"provider":"anthropic","model":"deepseek-flash",
           "last_ok_at":"2026-10-25T15:35:12+00:00",
           "last_error_code":"no_credit",
           "last_error_at":"2026-10-25T19:12:03+00:00"}}
503 {"status":"unavailable","version":"0.1.0","commit":"abc1234","ai":{…}}
```

**Rules**

- `configured` is `settings.ai_enabled` (provider set, key present, model resolvable).
- `provider` is the configured provider id (`none` when off); `model` the effective model or null.
- `last_ok_at` / `last_error_*` come from `ai_status`; all null on a fresh installation.
- **Never** the key, a token count, the provider's message or a conversation id.
- When `ai_status` cannot be read (migration not run, DB error) the block still answers with
  `configured` and nulls — health must not fail because of it.

**Consumers**: the Administración home pill and the composer pill (same payload, one request).

Pill states (both languages):

| State | Condition | Text |
|---|---|---|
| off | `configured == false` | «IA sin configurar» |
| ok | `last_error_code == null` or `last_ok_at > last_error_at` | «IA funcionando» |
| error | otherwise | «IA: <translated code>» |
