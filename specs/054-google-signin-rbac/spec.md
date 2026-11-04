# Feature Specification: Google button branding and role mapping for Google sign-in

**Feature Branch**: `054-google-signin-rbac`

**Created**: 2026-11-04

**Status**: Draft

**Input**: Owner, 2026-11-04, after using the sign-in page on `bi.getbizview.com` and reading feature
027's invite-only rule: (1) the "Continuar con Google" button is a plain outline button, not Google's
branding; (2) `GOOGLE_ALLOWED_DOMAINS` is env-only and a Google account must already exist, so a
customer's Workspace cannot be brought in without an admin creating every person by hand. Two parts,
one screen and one settings card.

**Builds on**: 002 (auth and roles), 004 (two-step sign-in, step-up, security page), 007 (Telegram
sign-in — the settings-card precedent and its icon button), 027 (Google sign-in: authorization code +
PKCE, invite-only, second factor kept), 005/020 (dashboards are the product's access unit), 033
(help topics). Changes the sign-in screen, the Google callback and Administración → Seguridad.

**Decisions taken here** (so the plan does not reopen them):

- **Branding is drawn, not fetched.** The multicolour **G** ships as an inline SVG in the repo, with
  Google's light and dark variants; nothing is fetched from Google's CDN, so the sign-in screen keeps
  working with no third-party request and no CSP exception. Google's brand terms forbid recolouring
  it, so the two variants use their published hex values and are the one documented exception to the
  `no-raw-colors` gate.
- **Provisioning stays opt-in and bounded.** `Alta automática` is off by default; when on, only
  accounts on an **allowed domain** are created, never superusers, always `user` or `admin` and only
  through the default role or a matching rule. 027's invite-only rule survives as the default.
- **The domain list moves into the product.** `GOOGLE_ALLOWED_DOMAINS` becomes the **initial value**
  only (read when the settings row was never written), so an installation keeps working after the
  upgrade and an admin can change it without a restart. It is audited on every change.
- **Rules are ordered and stateless.** `primera coincidencia gana`; a rule matches on `domain` or on
  an explicit `email` list; `group` is declared in the model and shown disabled as *próximamente*
  because a Workspace service account is not something this installation has.
- **Existing users are never rewritten by default.** `aplicar reglas también a usuarios existentes`
  is off; when on, every change of role or access it causes is audited per user, and superusers are
  out of reach of rules in every case.
- **Dashboard access is materialised, not dynamic.** "All public dashboards" writes the explicit
  grants of the dashboards that are `available` at that moment (the same rows the admin screen
  edits), so a later catalogue change never silently widens somebody's access.
- **The sign-in screen does not leak.** Every refusal — unknown identity, domain, inactive, provider
  — renders the same sentence; only a cancelled consent keeps its own ("cancelaste el inicio de
  sesión"), because the person did it. The reason lives in the audit log.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The Google button looks like Google (Priority: P1) 🎯

On the sign-in screen the reader sees an official **G** logo and the label **Continuar con Google**,
in the light variant on a light page and the dark variant on a dark one; the Telegram button below it
has the same height and the same icon-left layout. With Google disabled the button is not rendered.

**Why this priority**: it is the visible half of the request and the first thing a customer's staff
sees of the product.

**Independent Test**: render the sign-in screen in both themes with Google on: the button carries the
four-colour SVG, the label from the catalogue, a 44 px minimum height and the same height as the
Telegram button; with Google off it is absent; axe reports nothing serious.

**Acceptance Scenarios**:

1. **Given** Google enabled and a light page, **When** the sign-in screen renders, **Then** the
   Google button uses the light variant (white surface, official border and wordmark) with the
   multicolour G at the left.
2. **Given** the dark theme, **Then** the same button uses the dark variant.
3. **Given** Telegram enabled, **Then** its button keeps its paper-plane icon and both buttons have
   the same height and a ≥44 px touch target.
4. **Given** Google disabled, **Then** no Google control is in the DOM and the divider is still
   correct when only Telegram is enabled.
5. **Given** either language, **Then** the label reads **Continuar con Google** / **Continue with
   Google**.

---

### User Story 2 - An admin edits the allowed domains (Priority: P1)

In **Administración → Seguridad** a superuser finds **Ingreso con Google** with **Dominios
permitidos**, pre-filled from `GOOGLE_ALLOWED_DOMAINS` the first time, and saves. The next sign-in
uses the new list — no restart, no env edit — and the change appears in the audit log.

**Independent Test**: with env `example.com`, `GET` returns that list; saving `example.org` makes a
Google account on `example.com` refused and one on `example.org` accepted; the audit has one entry
with both values.

**Acceptance Scenarios**:

1. **Given** no settings row yet, **When** the card loads, **Then** it shows the env value.
2. **Given** a saved list, **When** the card loads, **Then** it shows the saved list, not the env.
3. **Given** a save, **Then** an audit entry records the previous and the new list.
4. **Given** an empty list, **Then** any verified Google domain is accepted (today's meaning of an
   empty filter), and the card says so.

---

### User Story 3 - Alta automática brings the domain in (Priority: P1)

A superuser turns on **Alta automática** and chooses **Rol por defecto** (`usuario`) and **Acceso por
defecto** (a list of dashboards). A colleague with a Google account on the allowed domain signs in for
the first time: Bizview creates the account, grants the dashboards and signs them in. The second
sign-in reuses the same account. Someone from another domain is refused with the generic message and
the attempt is audited.

**Independent Test**: with provisioning on and a fake identity, the callback creates exactly one user
(`auth_provider=google`, `must_change_password=false`, no usable password), the granted dashboards are
the default ones, a repeat callback creates nothing, and a foreign domain yields the generic message
plus a `domain_not_allowed` audit entry.

**Acceptance Scenarios**:

1. **Given** provisioning on and a new account on an allowed domain, **Then** a user is created with
   the default role and grants, is signed in, and `google_sign_in` records `provisioned`.
2. **Given** that user signs in again, **Then** no second user is created and the link is reused.
3. **Given** a domain outside the list, **Then** no user is created and the page shows the generic
   failure while the audit keeps `domain_not_allowed`.
4. **Given** provisioning off (the default), **Then** an unknown account is refused exactly as 027
   refuses it today.
5. **Given** a provisioned user, **When** they try the password form, **Then** it is refused (they
   have no password) until an admin sets one.

---

### User Story 4 - Reglas de rol decide who gets what (Priority: P2)

A superuser writes an ordered list of rules, each with a condition and an outcome: `dominio ==
acme.com → admin, todos los tableros públicos`, `email en [cfo@acme.com] → admin, tableros
[finanzas]`. The first match wins. Superusers are never touched, and a rule cannot produce a
superuser.

**Independent Test**: with `email` before `domain`, the listed address gets the email rule's outcome
and another address on the same domain gets the domain rule's; reordering swaps the outcomes; a rule
whose role is `superusuario` is refused by the API with a field error.

**Acceptance Scenarios**:

1. **Given** two matching rules, **Then** the first in the order decides.
2. **Given** rules and an existing user with `aplicar reglas también a usuarios existentes` off,
   **Then** their role and grants are unchanged and the audit says the rule was not applied.
3. **Given** the toggle on and a matching rule that changes the role, **Then** the change happens and
   is audited per user with the rule id.
4. **Given** a superuser whose email matches a rule, **Then** nothing changes.
5. **Given** a `group` condition, **Then** the UI shows it disabled with *próximamente* and the API
   refuses it with a field error.
6. **Given** a newly provisioned account, **Then** the first matching rule overrides the defaults.

---

### User Story 5 - The sign-in screen stays quiet (Priority: P1)

Whatever went wrong, the person sees **No se pudo iniciar sesión con Google**; the audit log has the
real reason (`domain_not_allowed`, `no_user`, `provisioned`, `rule:<id>`).

**Acceptance Scenarios**:

1. **Given** an unknown identity, **Then** the page shows the generic sentence and the audit keeps
   `no_user`.
2. **Given** a refused domain, **Then** the page shows the same sentence.
3. **Given** the person cancelled at Google, **Then** the page says the sign-in was cancelled.

---

### Edge Cases

- Google is disabled in the settings but the card is open: saving keeps the row, and the button
  stays hidden (the provider switch remains the env pair, unchanged by this feature).
- A rule matches an email that belongs to an *inactive* user: the account stays inactive; the rule
  never reactivates.
- Provisioning with `admin` as the default role: allowed for a superuser, and the new admin has no
  dashboards of their own (admins see every dashboard by role, as today).
- `email in [list]` with a mixed-case entry: matched case-insensitively.
- A provisioned user deleted later: the Google link is removed with them, so a new sign-in provisions
  again (if enabled) instead of resurrecting the old id.
- Two rules with the same condition: allowed; the first wins and the card warns about the shadowed
  one.

## Requirements *(mandatory)*

### Branding
- **FR-001**: The sign-in screen MUST render the Google control with the official multicolour **G**
  as an inline SVG shipped with the product, in the light variant on a light page and the dark
  variant on a dark one, the label from the catalogue, the logo at the left and a minimum height of
  44 px.
- **FR-002**: The Telegram control MUST keep its icon-left layout and share the Google control's
  height; the order remains email/password → divider → Google → Telegram and each is hidden when its
  provider is disabled.
- **FR-003**: The SVG MUST NOT recolour the brand mark; the component is the single documented
  exception to the colour-literal gate, with its reason written next to it.

### Settings
- **FR-004**: A singleton `google_settings` row MUST hold `allowed_domains`, `auto_provision`,
  `default_role`, `default_access` (`none` | `all_public` | a dashboard-code list),
  `apply_rules_to_existing`, `updated_at` and `updated_by`; with no row, `allowed_domains` reads
  `GOOGLE_ALLOWED_DOMAINS` and everything else is off/`usuario`/`none`.
- **FR-005**: `GET/PUT /api/admin/google` MUST be superuser-only and step-up protected on write, return
  the dashboard catalogue for the access picker and audit every change
  (`google_settings_updated`).
- **FR-006**: `default_role` MUST be `usuario`… in storage terms `user` or `admin`, and anything else
  MUST be a validation error; `superusuario` is not an option anywhere.

### Rules
- **FR-007**: `google_rule` MUST store an ordered list per installation: `position`, `condition`
  (`domain` | `email` | `group`), `value` (a domain, or a list of addresses for `email`), `role`,
  `access`, `enabled`, `created_at/updated_at`, `updated_by`.
- **FR-008**: `GET/POST/PUT/DELETE /api/admin/google/rules` MUST be superuser-only and step-up
  protected, keep `position` contiguous, refuse `group` with a field error, refuse a role other than
  `user`/`admin`, and audit create/update/delete/reorder.
- **FR-009**: Evaluation MUST be first match wins over enabled rules in `position` order, matching
  the domain case-insensitively and the email list case-insensitively.

### Sign-in
- **FR-010**: The callback MUST resolve an identity in this order: linked subject → existing user by
  email (linking it) → provisioned user when `auto_provision` is on and the domain is allowed → the
  generic refusal.
- **FR-011**: A provisioned user MUST be created with `auth_provider="google"`, no password hash,
  `must_change_password=false`, the rule outcome or the defaults, active, and the grants its access
  describes.
- **FR-012**: Password sign-in MUST refuse an account without a password hash exactly as it refuses a
  wrong password (same generic message, throttled and audited), and an admin MUST be able to set one
  from the existing reset password action.
- **FR-013**: Rules MUST be applied to existing users only when `apply_rules_to_existing` is on, and
  each resulting change MUST be audited with the rule id; superusers MUST never be modified.
- **FR-014**: The sign-in page MUST show one generic failure for every refusal except a cancelled
  consent, and the audit MUST record `domain_not_allowed`, `no_user`, `provisioned`, `rule:<id>` and
  the existing reasons.
- **FR-015**: Every new refusal and change MUST be audited with its own kind, and no secret, token or
  code is ever written to the audit or the page.

### Documentation
- **FR-016**: A help topic **Ingreso con Google** (033) MUST describe the button, the card, domains,
  provisioning and rules, in Spanish and English; `.env.example` MUST say that
  `GOOGLE_ALLOWED_DOMAINS` is the initial value only.

### Key Entities

- **GoogleSettings**: the installation's policy (domains, provisioning, defaults, existing users).
- **GoogleRule**: one ordered condition → role + access.
- **AppUser**: gains `auth_provider` (`password` | `google`) and a nullable password hash.
- **DashboardAccess**: the materialised grants provisioning writes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The sign-in screen renders one Google control with the official mark in both themes and
  none when the provider is off; axe clean in both themes.
- **SC-002**: Changing the domains in the card takes effect on the next callback with no restart.
- **SC-003**: A first sign-in on an allowed domain with provisioning on results in exactly one user
  and the default grants; a second sign-in creates nothing.
- **SC-004**: Rule order decides the outcome: swapping two rules swaps the results, proven by a test.
- **SC-005**: An existing user's role changes only with the toggle on, and every such change has its
  audit entry with the rule id.
- **SC-006**: No refusal reaches the page with a reason-specific message.

## Assumptions

- The provider switch (enabled + client id/secret) stays in the environment: this feature changes
  *who may sign in*, not *whether Google is configured*.
- The `internet` profile's second factor keeps applying to provisioned admins through the existing
  `finish_sign_in()`.
- Dashboards are the only access unit; no new permission model is introduced.
- The e2e fake Google is a test hook that answers the callback with a fixed identity, not a real OIDC
  server (the CI has no network to Google).

## Decisiones tomadas (modo autónomo)

- [specify] decision — the official brand colours live in the logo component and are listed in the
  colour gate's per-file exceptions, because Google's terms forbid recolouring the mark and the gate
  exists to keep *screens* on theme tokens, not to forbid a third party's trademark.
- [specify] decision — "all public dashboards" materialises grants for the dashboards that are
  `available` at that moment instead of being evaluated at read time, so access cannot widen later by
  someone publishing a dashboard.
- [specify] decision — a provisioned account has no password hash at all (column made nullable) and
  `must_change_password=false`: there is nothing to change, and the admin's reset action is the only
  way to give them one.
- [specify] decision — the settings card lives on **Seguridad**, as the brief names it, not on a page
  of its own; the security page already gathers the installation's auth posture.
- [clarify] decision — domain entries are normalised on write (lower case, leading `@` stripped,
  trimmed, deduplicated, empties dropped), the same normalisation `Settings.google_domains` already
  applies, so the card and the env value mean the same thing.
- [clarify] decision — the access value is one object, `{mode: "none"}` / `{mode: "all_public"}` /
  `{mode: "list", codes: [...]}`, for both the default and each rule: one shape, one validator, and
  an unknown dashboard code is a field error instead of a silently dropped grant.
- [clarify] decision — a provisioned `full_name` comes from the Google `name` claim and falls back to
  the email's local part, because `app_user.full_name` is mandatory and a blank name would break the
  user list; the claim is read from the ID token we already validate.
- [clarify] decision — with `auto_provision` on and an empty domain list, any verified Google domain
  is admitted: that is exactly what an empty `GOOGLE_ALLOWED_DOMAINS` means today, and making the
  empty list mean "nobody" would turn the feature off in a way the card does not show.
- [clarify] decision — the default role `admin` provisions admins who, like every admin, see the whole
  dashboard catalogue; the access value still applies to `user` accounts only, and the card says so.
- [clarify] decision — `apply_rules_to_existing` is evaluated on every Google sign-in, not once: a
  deterministic outcome is easier to reason about than a "already applied" flag, and each change is
  audited only when the role or the grants actually differ.
- [clarify] decision — limits on the card's inputs: 20 domains, 50 rules, 50 addresses per email rule,
  matching the moderation of every other list in the product and keeping the callback's work bounded.
- [analyze] decision — an admin gives a provisioned account a password through the existing
  `POST /api/admin/users/{id}/password`, unchanged: the reset writes the hash and the forced change
  still applies, so no second path is invented (and the flow is asserted in the backend tests).
- [analyze] decision — the card's dashboard picker reads the catalogue from the existing
  `GET /api/admin/dashboards` instead of embedding it in the settings response, so one endpoint owns
  the catalogue and the card cannot show a stale list after a report is applied.
- [implement] decision — the default role is chosen with the product's `RoleTiles` (two radio tiles,
  `usuario` / `admin`) instead of a `<select>`: it is the same control the user detail already uses
  for the role, it is keyboard- and touch-friendly by construction, and `superusuario` is not an
  option that has to be hidden. The rule editor keeps a `<select>` because it sits inside a compact
  row of conditions and needs no icons.
- [implement] decision — the dashboard catalogue travels with `GET /api/admin/google` instead of the
  card calling `GET /api/admin/dashboards` afterwards (supersedes the [analyze] decision above): the
  picker and the rule editor need the catalogue the moment the settings render, one request answers
  both, and the list cannot arrive after a rule the reader already opened. Both endpoints read the
  same table, so the catalogue is not duplicated as data, only as a response field.
- [implement] decision — the card is mounted unconditionally and shows a warning when the provider is
  off (`GOOGLE_CLIENT_ID` missing) instead of being hidden: a hidden configuration is a support trap,
  and the policy can be prepared before the installation is given a client. Telegram's card follows
  the same rule.
- [implement] decision — the three specific sign-in sentences (`notRegistered`, `inactive`, `domain`)
  were deleted from both catalogues when FR-016 landed, and feature 027's error-code test was updated
  to assert the generic sentence for every code but `denied`: keeping unused strings would let a
  later edit reintroduce the leak the feature removes.
