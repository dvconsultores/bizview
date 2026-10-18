# Feature Specification: Sign in with Google

**Feature Branch**: `027-google-sign-in`

**Created**: 2026-10-18

**Status**: Draft

**Input**: Owner, 2026-10-18: "it is possible login with google?"

**Builds on**: 002 (auth and roles), 004 (data sources and security: the `internet` profile, two-step
sign-in, step-up), 007 (Telegram sign-in — the existing precedent for an alternate sign-in method).

**Constitution**: this feature changes the **Auth** line of principle V, which currently fixes
authentication as "email + password, Argon2id, server-side sessions in PostgreSQL, carried by an
HttpOnly cookie". Adding a federated identity provider is therefore an **amendment** (MINOR: the
principle is materially expanded, not redefined — password sign-in survives unchanged and stays the
only method for accounts without a linked identity). Principles VIII (a third party only when the
operator opts in) and VII (every difference is configuration, never a fork) decide the two defaults
below: **off by default** and **configured per installation**.

## The decision this spec takes

Google is an **additional** identity for users who already exist. It does not create accounts.

- **Invite-only linking.** A Google sign-in succeeds only when the verified Google email matches an
  existing, active user. An unknown email is refused with the same message as any other failed
  sign-in, so the endpoint cannot be used to enumerate accounts. This product is self-hosted BI over
  a customer's business data: auto-provisioning strangers into it is the wrong default, and an
  operator who wants the people in can invite them.
- **Off by default** (`GOOGLE_AUTH_ENABLED=false`). With it off, the endpoints refuse to act and the
  sign-in screen is exactly what it is today.
- **Password sign-in never disappears.** Even with Google enabled, `/api/auth/login` behaves as it
  does now, so an installation cannot lock itself out of its own superuser through a Google outage,
  a deleted OAuth client, or a mistyped client secret.
- **A Google-sign-in user still holds a password.** An invited user completes the existing forced
  password change on first sign-in (the product already routes a `must_change_password` session to
  `/cambiar-clave`), so Google is an alternative route into an account that also has a break-glass
  credential. Verified against the code while planning: `POST /api/me/password` is reachable for
  such a session through `self_service_auth`, so the user is never trapped.
- **The second factor is not bypassed.** Google proves *who* someone is; it does not satisfy the
  `internet` profile's two-step requirement for administrators. Both methods end in the same
  `finish_sign_in()`, so an admin still presents a TOTP code (or enrols one).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An invited user signs in with their Google account (Priority: P1)

A customer's analyst has a Bizview account created by the superuser and Google sign-in is enabled.
On the sign-in screen the analyst presses **Continuar con Google**, picks their work account, and
lands on the dashboard — no password to remember, no password to leak.

**Why this priority**: it is the whole point of the request. Without it the feature does nothing.

**Independent Test**: with Google enabled and a user whose identity is linked, a completed
authorization-code flow yields a session and the user reaches the dashboard; the session has the same
shape a password sign-in produces (same cookie, same timeouts).

**Acceptance Scenarios**:

1. **Given** Google is enabled and an active user has a linked identity, **When** the callback carries
   a valid code and the verified email matches, **Then** a session is created and the user is signed in.
2. **Given** an active user exists with no linked identity, **When** the verified email matches that
   user, **Then** the identity is linked and the user is signed in (first-use linking).
3. **Given** the verified email matches no user, **When** the callback completes, **Then** the
   sign-in is refused with the generic failure and no account is created.
4. **Given** the account is inactive or locked, **When** it signs in through Google, **Then** it is
   refused exactly as the password path refuses it.

---

### User Story 2 - An administrator keeps the second factor (Priority: P1)

On an `internet` installation an administrator signs in with Google. Because that profile requires a
second factor for administrators, the Google step does not produce a working session: the user is
sent to the code prompt (or to enrolment), and only then reaches the application.

**Why this priority**: without it, adding Google would *weaken* the product's strongest security
guarantee — a stolen Google session would become admin access to business data.

**Independent Test**: on the `internet` profile, an admin with a linked identity who completes the
Google flow gets the `mfa_required` outcome and cannot call a report endpoint until the second factor
is presented.

**Acceptance Scenarios**:

1. **Given** the `internet` profile and an enrolled admin, **When** they sign in with Google, **Then**
   the response asks for the second factor and no report endpoint answers until it is given.
2. **Given** the `internet` profile and an unenrolled admin, **When** they sign in with Google,
   **Then** the session may only enrol the second factor — the same rule 026's security review
   established for passwords.

---

### User Story 3 - The operator turns it on safely (Priority: P2)

A superuser sets `GOOGLE_AUTH_ENABLED=true` with the OAuth client id and secret (optionally
restricting the accepted Google Workspace domain), restarts, and the button appears. If the
credentials are wrong or Google is unreachable, password sign-in still works and the failure is a
plain localised error, not a broken sign-in screen.

**Why this priority**: it is what makes the feature usable across installations (constitution VII)
without a code fork, and it is where real incidents happen.

**Independent Test**: with the feature disabled the start endpoint is refused and the button is
absent; with it enabled and a wrong client secret, the callback reports a sign-in failure and
password sign-in continues to work.

**Acceptance Scenarios**:

1. **Given** `GOOGLE_AUTH_ENABLED=false` (the default), **When** the client asks to start the flow,
   **Then** the request is refused and the sign-in screen is unchanged.
2. **Given** a flow was started, **When** the callback arrives without the `state` cookie that belongs
   to it, **Then** it is refused (CSRF on the callback).
3. **Given** a `GOOGLE_ALLOWED_DOMAINS` list, **When** an account from another domain completes the
   flow, **Then** it is refused even though the email exists.
4. **Given** Google or its token endpoint fails, **Then** the user returns to the sign-in screen with
   a localised error and the password form still works.

### Edge Cases

- A user's Google email changes but the account stays the same: an existing link is matched by the
  stable subject id, so the rename does not break it; with no link, the new email simply does not
  match and the sign-in is refused.
- Two Bizview users claim the same Google identity: the subject is unique, so the second link is
  refused rather than pointing one Google account at two users.
- The link is removed (or the user is deleted): a later sign-in for that subject is an unknown
  identity and is refused.
- `redirect_uri` mismatch, expired code, reused code: refused, same user-facing message.
- Behind a proxy: the redirect URI derives from `SITE_ADDRESS`, never from the request `Host`, so a
  forged header cannot redirect the code elsewhere.

## Requirements *(mandatory)*

### Configuration
- **FR-001**: Configured only through settings, never a fork: `GOOGLE_AUTH_ENABLED` (default `false`),
  `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, optional `GOOGLE_ALLOWED_DOMAINS` (comma- or
  space-separated email domains) and optional `GOOGLE_REDIRECT_URI` (an override for unusual proxy
  setups; when empty the URI derives from `SITE_ADDRESS`).
- **FR-002**: The client secret is a secret: read only by the backend, never returned by an API
  response, never logged, never sent to the browser; `.env.example` carries a placeholder only.

### Sign-in
- **FR-003**: Two endpoints: one starting the flow (sets a short-lived `state`/PKCE cookie and
  redirects to Google), one handling the callback. Both refuse to act while the feature is disabled.
- **FR-004**: The start endpoint builds the authorization URL from `SITE_ADDRESS` and the request
  locale; the callback is bound to the `state` in the cookie (constant-time compare), so a
  third-party-initiated callback is refused.
- **FR-005**: Identity comes from Google's token endpoint over TLS, authenticated with the client
  secret (authorization-code flow for a confidential client), and the ID token's `iss`, `aud`, `exp`
  and `email_verified` claims are validated. No unsigned claim is trusted and nothing the browser
  supplies is believed except the authorization code.
- **FR-006**: A successful sign-in ends in the same `finish_sign_in()` every other method uses, with
  `method="google"`, so session shape, timeouts, lockout, audit and the second-factor gate are not
  reimplemented.
- **FR-007**: Invite-only: an email matching no active user is refused with the generic failure; no
  user is ever created or promoted by this flow.
- **FR-008**: A Google identity is stored per user with its immutable subject id, unique across the
  installation, so one Google account cannot map to two users.
- **FR-009**: Attempts are audited (`google_sign_in`, `google_sign_in_refused`, `google_linked`) with
  the same mechanism as the other methods.

### Client
- **FR-010**: The sign-in screen shows the Google action only when the installation reports it
  enabled, and never hides or replaces the password form.
- **FR-011**: A refused or failed callback returns the user to the sign-in screen with a localised
  message (Spanish and English), at 320 px as well as on a desktop viewport.

### Deployment and governance
- **FR-012**: `docs/INSTALL.md` and `.env.example` document the Google Cloud console steps (OAuth
  client, authorised redirect URI), the settings, and that a customer may use their own client — no
  installation depends on a secret held by the vendor.
- **FR-013**: Constitution principle V's **Auth** line is amended to include an optional federated
  identity provider, with a Sync Impact Report; password authentication stays mandatory to keep.

## Success Criteria *(mandatory)*

- **SC-001**: With the feature disabled (default), the sign-in screen is unchanged and the new
  endpoints are refused.
- **SC-002**: An invited user with a linked identity signs in through Google in one flow, and the
  resulting session is indistinguishable from a password session for the rest of the product.
- **SC-003**: 0 accounts are created or promoted by the flow: unknown, inactive, locked and
  wrong-domain identities are each refused with the generic failure.
- **SC-004**: On the `internet` profile, no report endpoint answers for an admin who has completed
  only the Google step.
- **SC-005**: A callback with a missing, mismatched or replayed `state` is refused; a replayed
  authorization code is refused.
- **SC-006**: Password sign-in works in every failure state of the Google flow (disabled,
  misconfigured, provider unreachable), verified by test.

## Assumptions

- The flow is the server-side authorization-code flow for a **confidential client**. Identity is read
  from Google's token endpoint over TLS with the client secret, which is why no JWT library is added
  (constitution V): Google permits a confidential client that receives the ID token directly from its
  token endpoint to skip signature verification, and the claims that matter (`iss`, `aud`, `exp`,
  `email_verified`) are still validated. Recorded as a research decision.
- An installation may use its own Google OAuth client; the product ships no vendor-held client, so no
  customer data path depends on this project's credentials.
- Linking happens on first successful sign-in for a matching active email (the invite-only default);
  a superuser can remove a link later through the existing user administration surface.
