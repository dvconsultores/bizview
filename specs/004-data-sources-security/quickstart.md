# Quickstart & Validation: Data Sources and Internet-Grade Security

**Feature**: [spec.md](./spec.md) | **Contracts**: [api](./contracts/api.md), [connectors](./contracts/connectors.md)

## Setup

- `.env`: `BIZVIEW_SECRET_KEY` (new installations get it from the installer; existing ones:
  `python -c "import secrets,base64;print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"`),
  `SECURITY_PROFILE=private` for this development installation (HTTP on localhost). Remove `DATABASE_URL_ORIGIN` after the first start imports it.
- Test targets: the development origin (PostgreSQL, from the legacy import), in-process stub SOAP
  and REST servers (HTTP and HTTPS with a test CA), and optionally a public SOAP WSDL and a REST API
  with a bearer token. SQL Server is out of scope for this version.

## Tests

```bash
cd backend && uv run pytest tests/test_crypto.py tests/test_sources*.py tests/test_mfa.py \
  tests/test_throttle.py tests/test_security_profile.py
cd frontend && npx playwright test          # includes sources and two-step sign-in flows
```

## Validation scenarios

| # | Scenario | Expected | Covers |
|---|---|---|---|
| 1 | Start with `DATABASE_URL_ORIGIN` and no sources | one encrypted PostgreSQL source "Origen (importado)", notice for super user; restart → no duplicate | US5, FR-012 |
| 2 | Create PostgreSQL source, test | ok + server version; warning if account can write | US1, FR-006 |
| 3 | Search DB dump, API responses, logs, audit for the test passwords/tokens | not found | SC-001, FR-004 |
| 4 | Copy `secrets_ct` from source A to source B | B fails to decrypt ("credencial dañada") | FR-013 |
| 5 | Start without / with wrong `BIZVIEW_SECRET_KEY` while sources exist | refuses to start with the setting name | US4, FR-014 |
| 6 | Rotate key; test all sources; remove previous key; restart | all ok | FR-015, SC-006 |
| 7 | Source host `127.0.0.1`, `169.254.169.254`, `backend`, or a name resolving to them | `blocked_address` on save and on test | FR-008, SC-007 |
| 8 | SOAP WSDL with an external entity | rejected, no file read | FR-009 |
| 9 | REST endpoint answering 302 to another host | `invalid_response`, credentials not sent there | FR-010 |
| 10 | Admin (not super user) calls `/api/sources` | 403 | FR-002 |
| 11 | `internet` profile, admin without two-step sign-in | 403 `mfa_enrollment_required` → enrollment flow → recovery codes | US3, FR-017, FR-018 |
| 12 | Sign in with two-step: code, reused code, recovery code, wrong code ×5 | ok, refused, ok (code consumed), locked | FR-018 |
| 13 | 20 failed sign-ins from one address across accounts | 21st → 429 for the window | FR-020, SC-005 |
| 14 | Save a source 6 minutes after the last password confirmation | 403 `reauth_required` → dialog → retry ok | FR-021 |
| 15 | `ADMIN_ALLOWED_NETWORKS=10.0.0.0/8`, admin from another address | admin API 403, home works | FR-022 |
| 16 | Forged `X-Forwarded-For` through Caddy | audit shows the real address | FR-023 |
| 17 | `internet` profile with `COOKIE_SECURE=false` | backend refuses to start | FR-017 |
| 17b | `private`: save REST `http://` source and PostgreSQL `sslmode=disable`; switch to `internet`, restart, test both | saved and tested ok under `private`; `not_allowed_in_profile` under `internet` | FR-017, SC-008 |
| 17c | Installer `--security-profile private` / `internet` / omitted with a domain | `.env` has the chosen value; omitted → asked (or `auto` with `--yes`) | FR-016 |
| 18 | *Seguridad* page | profile + checklist | FR-025 |
| 19 | All screens at 320/375 px, three engines | no horizontal scroll, axe clean | constitution I |
