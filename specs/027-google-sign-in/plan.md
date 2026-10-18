# Implementation Plan: Sign in with Google

**Branch**: `027-google-sign-in` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

## Summary

An installation may enable Google as an **additional** identity for users who already exist. The
server-side authorization-code flow for a **confidential client** proves the identity, then hands it to
the same `finish_sign_in()` that the password and Telegram paths already use, so sessions, timeouts,
lockout, audit and the `internet` second-factor gate are inherited rather than reimplemented.

Off by default; invite-only; password sign-in untouched. Constitution principle V's Auth line was
amended to **2.1.0** (MINOR) with a Sync Impact Report, because auth is fixed in the stack.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript + React 19 (frontend)

**Primary Dependencies**: FastAPI, SQLAlchemy, Alembic, `httpx` (already a stack component) for the
token exchange. **No new dependency and no JWT library** — see R3.

**Storage**: PostgreSQL; one new table (`google_link`) via Alembic `0021`, following the
`telegram_link` precedent.

**Testing**: `pytest` (backend, own temporary `app_test_*` schema), `vitest` (frontend), Playwright
for the sign-in screen at 320/375 px.

**Constraints**: the client secret never leaves the backend, is never logged and never reaches the
browser; the redirect URI derives from `SITE_ADDRESS`, never from a request header.

## Decisions (research)

**R1 — Invite-only, matched on the immutable subject.** A link is looked up by `google_sub` first, so a
user renaming their Google address keeps their link; with no link, the verified email is matched to an
existing active user and the identity is linked on first use. An unknown email is refused with the
generic failure so the endpoint cannot enumerate accounts. Auto-provisioning was rejected: this is
self-hosted BI over business data, and an operator who wants someone in can invite them.

**R2 — Off by default, per installation, never the vendor's client.** `GOOGLE_AUTH_ENABLED=false`;
the client id/secret come from the installation's own Google Cloud project (constitution VII: no
customer data path through this project's credentials; VIII: a third party only when the operator
opts in).

**R3 — No JWT library.** Identity is read from Google's token endpoint over TLS, authenticated with
the client secret. Google documents that a confidential client receiving the ID token directly from
that endpoint need not verify the signature; `iss`, `aud`, `exp` and `email_verified` are still
validated, and nothing the browser supplies is trusted beyond the authorization code and the `state`
that matches its own cookie. Adding `authlib`/`PyJWT` was rejected: a new dependency to re-verify a
token the server just received over an authenticated TLS channel, when the stack is fixed.

**R4 — The second factor is inherited, not re-implemented.** The callback calls
`finish_sign_in(..., method="google")`, which already returns `mfa_required` for administrators on the
`internet` profile and the enrolment-only pending session for an unenrolled admin (026's R16/Finding
2 behaviour). A Google sign-in therefore cannot be weaker than a password sign-in.

**R5 — `state` in a cookie, constant-time compare, PKCE S256.** A third-party-initiated callback or a
cross-site replay is refused before any token exchange happens.

**R6 — Errors are codes, not Google's text.** The callback redirects to
`/ingresar?google_error=<code>` with a closed set (`disabled`, `state`, `denied`, `provider`,
`unknown_identity`, `inactive`, `domain`) and the client maps each to a localised message. Google's raw
error and the tokens never reach the browser or a log.

## Constitution Check

| Principle | How it is satisfied | Verdict |
|---|---|---|
| II/VI | No change to data access; authentication touches no report data. | PASS |
| V (amended) | Optional federated identity, bounded by off-by-default, per-installation client, invite-only and the preserved second factor; `httpx` is already the stack's HTTP client. | PASS (amendment 2.1.0) |
| VII | Configured per installation; no vendor-held client; no fork. | PASS |
| VIII | Third party only on operator opt-in; only OAuth parameters and the code are sent — no business data, no report data. | PASS |
| IX | Product feature with a spec (`027`) and a plan; customer reporting logic untouched. | PASS |
| Constraints | Credentials encrypted/write-only; the client secret is never returned or logged; every user-visible string in Spanish and English; the `internet` profile keeps TLS, two-step sign-in for administrators and step-up. | PASS |

## Structure

```text
backend/app/config.py             # GOOGLE_* settings + google_enabled_effective
backend/app/models.py             # GoogleLink (unique google_sub per user)
backend/alembic/versions/0021_google_sign_in.py
backend/app/auth/google.py        # authorize URL (state + PKCE), token exchange, claim checks
backend/app/api/oauth.py          # /api/auth/google/{start,callback}; /api/config gains google_auth
backend/app/i18n/{es,en}.py       # refusal messages (codes, never raw provider text)
backend/tests/test_google_sign_in.py

frontend/src/config/BrandingContext.tsx   # google_auth from /api/config
frontend/src/pages/SignIn.tsx             # the button + ?google_error mapping
frontend/src/i18n/{es,en}.ts
frontend/tests/unit/google-sign-in.test.tsx

.env.example, docs/INSTALL.md, README.md, CHANGELOG.md, SECURITY.md
.specify/memory/constitution.md           # 2.1.0 amendment
```

## Verification

- `pytest tests/test_google_sign_in.py tests/test_auth.py tests/test_mfa.py` — the flow, the refusals,
  and the guarantee that password sign-in still works in every failure state (SC-006).
- `vitest` — the button only with `google_auth: true`, the error codes, both languages.
- `alembic upgrade head` / `downgrade -1` / `upgrade head` — the migration is reversible.
- Manual (operator): with the feature disabled, `/api/auth/google/start` refuses and the sign-in
  screen is unchanged.
