# Data Model: Distribution & AI

**Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md) | **Date**: 2026-09-29

No database changes. The entities of this feature are configuration, held in each installation's
`.env` and read by `backend/app/config.py`.

## Installation settings (additions to feature 002)

| Setting | Type | Default | Rules |
|---|---|---|---|
| `BIZVIEW_VERSION` | SemVer string | `VERSION` file, else `dev` | baked into the backend image; selects image tags in an installation |
| `BIZVIEW_IMAGE_PREFIX` | image reference | stamped by release | installation only (compose file) |
| `SOURCE_URL` | https URL | project repository | shown on every page (AGPL §13) |
| `AI_PROVIDER` | enum | `none` | `none` \| `anthropic` \| `openai_compatible` |
| `AI_API_KEY` | secret | empty | never serialised, logged, or returned |
| `AI_MODEL` | string | `claude-opus-5-5` for `anthropic`; required for `openai_compatible` | 1–100 chars |
| `AI_BASE_URL` | http(s) URL | empty | required for `openai_compatible`; optional override for `anthropic` |
| `AI_TIMEOUT_SECONDS` | number | 30 | 1–300 |

## AI provider configuration (derived)

- **enabled** = provider ≠ `none` and nothing missing.
- **missing** = `AI_API_KEY` for `anthropic` without key; `AI_MODEL` / `AI_BASE_URL` for
  `openai_compatible` without them.
- State: `off` (provider none) → `incomplete` (missing ≠ ∅) → `enabled`. Changing settings requires
  a restart (settings are read at start).

## Connection test result (not stored)

`ok`, `provider`, `model`, `latency_ms`, `reply` (≤ 200 chars), `error {code, message}` — see
[contracts/api.md](./contracts/api.md). Not audited (it changes nothing).
