# Feature Specification: Sign in with Telegram

**Feature Branch**: `007-telegram-sign-in`

**Created**: 2026-09-30

**Status**: Implemented (closed 2026-10-08; quickstart 19 with a real bot is a manual check)

**Input**: User description: "Sign in with Telegram: users of a BizView installation can sign in
with their Telegram account instead of typing email and password. Users are still created by
administrators (no self-registration); a signed-in user links their Telegram account from their
profile, and from then on can sign in with Telegram on the sign-in screen. The super user enables
it per installation (off by default) and configures the installation's Telegram bot; the bot
credential is a secret (encrypted, write-only). Must respect the security profiles (internet
profile: two-step sign-in for administrators), audit, throttling, and account lock/deactivation."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The super user turns on Telegram sign-in (Priority: P1)

The super user opens the security administration, enters the installation's Telegram bot name
and its secret credential, checks that the bot answers, and turns "Ingresar con Telegram" on.
Until then nobody sees any Telegram option.

**Why this priority**: nothing else works until an installation has a working bot; it also
keeps the feature off by default, as the product requires for optional integrations.

**Independent Test**: on a fresh installation confirm no Telegram option appears anywhere; as
super user save a bot, run the check, enable it, and confirm the option appears on the sign-in
screen and in profiles.

**Acceptance Scenarios**:

1. **Given** a new installation, **When** anyone opens the sign-in screen or a profile, **Then**
   no Telegram option is shown.
2. **Given** the super user enters the bot name and credential and confirms their password,
   **When** they save, **Then** the credential is stored encrypted and is never shown again
   (only "configurado" and when it was changed).
3. **Given** a saved bot, **When** the super user runs the check, **Then** they see either
   success with the bot's public name, or a named reason (`invalid_credential`, `unreachable`,
   `timeout`).
4. **Given** a failing check, **When** the super user tries to enable Telegram sign-in, **Then**
   it is refused with the reason.
5. **Given** Telegram sign-in is enabled, **When** the super user disables it, **Then** the
   option disappears everywhere and Telegram sign-in attempts are refused, while existing links
   are kept for when it is turned back on.

---

### User Story 2 - A user links their Telegram account (Priority: P1)

A signed-in user opens their profile, taps "Vincular Telegram", confirms their password, and
approves the request in Telegram. The profile then shows the linked Telegram name. They can
unlink it at any time.

**Why this priority**: linking is how an existing, administrator-created account becomes
usable with Telegram; without it there is nothing to sign in to.

**Independent Test**: sign in with email and password, link a Telegram account, verify the
profile shows it and the audit log records it; unlink and verify both again.

**Acceptance Scenarios**:

1. **Given** Telegram sign-in is enabled and the user has no link, **When** they choose
   "Vincular Telegram", confirm their password and approve in Telegram, **Then** their profile
   shows the Telegram name and an audit event records the link.
2. **Given** the Telegram account is already linked to another user of the installation,
   **When** someone tries to link it, **Then** the link is refused with a message that does
   not reveal which user holds it.
3. **Given** a linked user, **When** they choose "Desvincular" and confirm their password,
   **Then** the link is removed and audited.
4. **Given** a user who lost their phone, **When** an administrator removes that user's
   Telegram link from the user's page, **Then** the link is removed and audited with the
   administrator as actor.
5. **Given** the user started linking but did not approve in Telegram within the allowed
   time, **When** the time passes, **Then** nothing is linked and they can start again.

---

### User Story 3 - A user signs in with Telegram (Priority: P1)

On the sign-in screen a user taps "Ingresar con Telegram", approves in Telegram, and lands on
their home screen without typing a password. The same rules as password sign-in apply: locked
or deactivated accounts are refused, repeated failures are limited, and administrators on an
internet-facing installation still enter their authenticator code.

**Why this priority**: this is the value the user asked for — a faster sign-in, especially
on phones where Telegram is already open.

**Independent Test**: with a linked account, sign in through Telegram on a phone-sized screen;
repeat with a deactivated account, a locked account, an unlinked Telegram account, and an
administrator on the `internet` profile.

**Acceptance Scenarios**:

1. **Given** a linked, active user, **When** they choose "Ingresar con Telegram" and approve,
   **Then** they are signed in and the audit log records a sign-in by Telegram.
2. **Given** a Telegram account that is not linked to any user, **When** it is used to sign
   in, **Then** sign-in is refused with "Esta cuenta de Telegram no está vinculada. Ingresa
   con tu correo y vincúlala desde tu perfil." and the attempt is recorded.
3. **Given** a linked user who is deactivated or locked, **When** they try Telegram sign-in,
   **Then** it is refused with the same messages as password sign-in.
4. **Given** the `internet` security profile and a linked administrator, **When** they approve
   in Telegram, **Then** they are asked for their two-step sign-in code before entering, and
   an administrator without two-step sign-in is sent to set it up first, exactly as with a
   password.
5. **Given** a user whose account has a temporary password, **When** they sign in with
   Telegram, **Then** they are still sent to change their password before anything else.
6. **Given** an approval that was already used, or one older than the allowed time, **When**
   it is presented again, **Then** it is refused.

---

### Edge Cases

- The installation cannot reach Telegram (no outbound internet, Telegram down): the sign-in
  option shows a clear "Telegram no está disponible; ingresa con tu correo" message and email
  and password keep working.
- The bot credential is changed or revoked in Telegram: approvals fail with a named reason and
  the super user's check shows `invalid_credential`; links are kept.
- A user changes their Telegram display name or username: the link still works (it follows the
  Telegram account, not its name) and the profile shows the current name after the next sign-in.
- The same person has two BizView users: one Telegram account can be linked to only one of them.
- A session started by Telegram sign-in is ended by the same actions as any other session
  (sign-out, password change on another device, deactivation, lock).
- Password confirmation (step-up) for sensitive actions still asks for the password; Telegram
  does not replace it.
- The super user's own account may link Telegram like any other user; their recovery path
  (server command) is unchanged.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Telegram sign-in MUST be off by default on every installation; while off, no
  Telegram option is shown and every Telegram sign-in or link attempt is refused.
- **FR-002**: Only the super user MAY configure the bot (bot name and secret credential), run
  the bot check, and enable or disable Telegram sign-in; each change requires password
  confirmation (step-up) and is audited.
- **FR-003**: The bot credential MUST be encrypted at rest with the installation's existing
  secret key and MUST be write-only: never returned, shown, logged, or included in audit
  details.
- **FR-004**: Enabling MUST be refused unless the most recent bot check succeeded.
- **FR-005**: A signed-in user MUST be able to link exactly one Telegram account to their own
  user, after confirming their password and approving in Telegram; the link MUST identify the
  Telegram account by its permanent identifier, not by its name.
- **FR-006**: A Telegram account MUST be linked to at most one user per installation; a
  refused link MUST NOT reveal which user holds it.
- **FR-007**: Users MUST be able to unlink their own Telegram account (password confirmation);
  administrators MUST be able to remove the link of users they manage; both are audited.
- **FR-008**: The sign-in screen MUST offer "Ingresar con Telegram" when enabled; a successful
  approval for a linked, active, unlocked user MUST start a normal session.
- **FR-009**: Telegram sign-in MUST apply every rule of password sign-in: deactivated and locked
  accounts refused, per-address throttling (Telegram failures count with password failures),
  temporary-password redirect, and on the `internet` profile two-step sign-in (and its forced
  enrolment) for administrators.
- **FR-010**: Each approval MUST be single-use, bound to the sign-in or link request that
  started it, and valid for at most 5 minutes; forged, replayed, or expired approvals MUST be
  refused.
- **FR-011**: The audit log MUST record: Telegram settings changed, bot check, enabled/disabled,
  link created, link removed (with actor), sign-in by Telegram (success and failure, with the
  reason) — never the credential and never Telegram message content.
- **FR-012**: Telegram MUST NOT replace the password: password sign-in, step-up confirmation and
  password recovery keep working for every user, linked or not.
- **FR-013**: When Telegram cannot be reached, the product MUST show a clear message and keep
  email and password sign-in fully working.
- **FR-014**: The only Telegram data stored per user MUST be the permanent account identifier,
  the display name/username for showing in the profile, and the link date.
- **FR-015**: All new screens MUST work at 375 px, meet WCAG 2.1 AA in light and dark themes
  (feature 006), and use Spanish text.

### Key Entities

- **Telegram settings (per installation)**: enabled flag, bot name, encrypted bot credential,
  when the credential was last changed, result and time of the last bot check.
- **Telegram link**: one per user at most; the Telegram account's permanent identifier (unique
  in the installation), its display name/username, link date, who created it.
- **Telegram approval request**: a short-lived, single-use request (purpose: sign in or link;
  the user for links; creation time; used flag) that an approval must match.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A linked user signs in with Telegram from the sign-in screen in under 20 seconds
  on a phone, without typing anything.
- **SC-002**: 100% of Telegram sign-in attempts for deactivated, locked, unlinked, replayed, or
  expired approvals are refused and appear in the audit log.
- **SC-003**: On the `internet` profile, 0 administrators reach administration through
  Telegram without their two-step sign-in code.
- **SC-004**: The bot credential never appears in any screen, API response, log line, or audit
  entry (verified by searching all of them for a marker credential).
- **SC-005**: A super user can configure, check and enable Telegram sign-in in under 5 minutes
  with a bot they already created.
- **SC-006**: With Telegram unreachable, email and password sign-in success rate is unchanged.

## Assumptions

- Each installation uses its own Telegram bot, created by the customer or implementer with
  Telegram's own tools; creating the bot is outside the product.
- Using Telegram sign-in requires the installation (and the user's device) to reach Telegram on
  the internet; fully offline installations simply leave it off.
- Telegram sign-in is an alternative to the password, not a second factor; it never satisfies
  the two-step sign-in requirement for administrators.
- No self-registration: a Telegram account that is not linked cannot create a user.
- Administrators can remove a user's link but cannot create one for them (only the user can
  approve in their own Telegram).
- The feature follows the existing security profile, throttling, audit and encryption rules of
  features 002 and 004; no change to them is intended.
