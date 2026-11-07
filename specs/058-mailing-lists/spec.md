# Feature Specification: Mailing lists — send a dashboard to any address

**Feature Branch**: `058-mailing-lists`

**Created**: 2026-11-06

**Status**: Draft

**Input**: User description: "Today 'Enviar por correo' reaches installation users only, external addresses only inside `EMAIL_ALLOWED_DOMAINS`, at most 20 recipients, typed one by one, and scheduled subscriptions address roles only. Senders stay internal (signed-in Bizview users), but a send may go to any list of addresses — a reusable list kept in Bizview, or addresses pasted on the spot — for dashboards and scheduled deliveries alike."

## Context

Feature 018 built "Enviar por correo" for installation users, with two guards that made the feature
useless outside a small team: a domain allowlist that refused every external address when empty, and
a ceiling of 20 recipients per send. Real installations send a monthly board to a commercial list of
a hundred people, and the product's owner decided the volume is governed by the mail provider they
already pay for — not by Bizview.

This feature keeps the security shape that matters (**only signed-in users send**, the sender must
have access to the dashboard, addresses never reach project files or logs) and removes the volume
shape that does not (per-send and per-hour ceilings). It adds what was missing: **lists of
addresses**, reusable, shareable inside the installation, and usable both by an on-demand send and by
a scheduled delivery.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Send a dashboard to whoever needs it (Priority: P1)

An analyst opens a dashboard, presses **⋯ → Enviar por correo**, adds the shared list *Gerencia
comercial*, a colleague (installation user) and two addresses pasted from a mail thread, and sends.
The counter says 37 destinatarios; everybody gets the same email with the PDF and the branding.

**Why this priority**: it is the feature. Everything else (lists, subscriptions) is in service of
"reach these addresses".

**Independent Test**: with SMTP configured and no domain allowlist, send to one user + one list +
two free addresses; the send carries one delivery per address and appears in the history.

**Acceptance Scenarios**:

1. **Given** an installation with `EMAIL_ALLOWED_DOMAINS` unset, **When** a user sends a dashboard to
   `ana@cliente.com; Luis Pérez <luis@cliente.com>` pasted in one go, **Then** both are accepted,
   both receive the message, and the send shows 2 destinatarios.
2. **Given** `EMAIL_ALLOWED_DOMAINS=acme.com`, **When** a user adds `ana@otro.com`, **Then** the chip is
   marked invalid, the send is blocked with a message naming the allowed domains, and nothing is
   queued.
3. **Given** a send of 1,500 recipients, **When** it runs, **Then** it is one job delivered in
   messages of `EMAIL_BATCH_SIZE` recipients (BCC, sender in To), paced by `EMAIL_SEND_RATE`, and
   the history shows a per-recipient status.
4. **Given** the same address typed twice and the sender's own address, **When** the chips are built,
   **Then** duplicates and the sender collapse into one.

---

### User Story 2 - Keep a list once, use it many times (Priority: P1)

An administrator creates **Listas de correo → Nueva lista**, pastes 140 members, imports a CSV
`correo,nombre`, pauses two people who asked not to receive anything, exports the list to check it,
and marks it **compartida** so other senders can use it.

**Why this priority**: without a list, every send is typing; the list is what makes the volume
usable and auditable.

**Independent Test**: create a list with a CSV import, pause a member, export it, use it in a send and
confirm the paused member is skipped.

**Acceptance Scenarios**:

1. **Given** a user, **When** they create `Gerencia comercial` and paste ten lines, **Then** the list
   exists with 10 members, is personal by default, and appears under **Mis listas**.
2. **Given** a CSV `correo,nombre`, **When** it is imported, **Then** every valid row becomes a member
   and the invalid ones are reported by line, without aborting the import.
3. **Given** a paused member, **When** the list is used in a send, **Then** that address is skipped.
4. **Given** a shared list owned by an admin, **When** another sender opens the recipient box,
   **Then** they can pick it and cannot edit its members.
5. **Given** a list named by a scheduled delivery, **When** the list is deleted, **Then** the
   subscriptions that use it are paused with a reason, never deleted.

---

### User Story 3 - Schedule the monthly board to that list (Priority: P2)

An administrator creates a subscription: first Monday at 7, period *last month*, recipients the same
list, PDF attached. On the day, the worker delivers it once and the history shows it.

**Why this priority**: scheduling already exists; it has to accept lists, or a list is only useful
for manual work.

**Independent Test**: create a subscription with a list, run the tick, see one send with as many
deliveries as members.

**Acceptance Scenarios**:

1. **Given** a subscription with a list and two users, **When** the tick runs, **Then** one send is
   queued with every member resolved at that moment.
2. **Given** a subscription paused because its list was deleted, **When** the user opens it, **Then**
   the form shows the reason and offers another list.

---

### User Story 4 - Lists come from the project too, by name (Priority: P2)

A project declares `distributions/<id>.yaml` with `recipients: {lists: [Gerencia comercial]}`. The
CLI validates the shape, the import refuses an address in the file, and apply fails naming a list
that does not exist in the installation.

**Why this priority**: it is how an authored project keeps delivering after the author leaves.

**Independent Test**: validate a distribution with `lists:` in the CLI, apply it with and without the
list existing.

**Acceptance Scenarios**:

1. **Given** a `recipients:` block with an `@` in it, **When** the CLI validates, **Then** it fails
   with a message that names the block and says addresses are not allowed.
2. **Given** `lists: [Gerencia comercial]` and no such list, **When** the project is applied, **Then**
   apply is refused and the message names the list.
3. **Given** the same block and the list exists, **When** it is applied, **Then** the subscription is
   created with that list as a recipient.

---

### User Story 5 - See what was sent, and re-send what failed (Priority: P3)

The sender opens **⋯ → Envíos**, sees the date, who sent it, how many recipients, and the status of
each one; a failed address shows its reason and can be re-sent.

**Why this priority**: with no quotas, visibility is what replaces the ceiling.

**Independent Test**: send, force one delivery to fail, open the history, re-send the failed one.

**Acceptance Scenarios**:

1. **Given** a send with one failed address, **When** the history is opened, **Then** the row says
   *failed* with the reason and **Reenviar los fallidos** queues only those.
2. **Given** a user without access to the dashboard, **When** they query the history, **Then** they
   are refused.

---

### Edge Cases

- A list whose members are all paused: the send is refused with *no recipients* rather than sending
  to nobody.
- A send that mixes a user, a list and an address that is also a member: the address appears once.
- `EMAIL_SENDING_PAUSED=true`: the dialog still accepts the send (it is queued) and the worker
  holds it; the UI says delivery is paused.
- A 1,000-member list with `EMAIL_INDIVIDUAL_MESSAGES=true`: 1,000 messages, each with its own
  bounce handling, paced by `EMAIL_SEND_RATE`.
- A member address that stopped being valid: the delivery fails, the member stays in the list and is
  shown with the reason.
- The sender's own address in a list: skipped, never the reason for a refusal.
- A dynamic role list (`{role: admin}`) resolves at send time, so a new administrator is included
  without editing anything.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A send MUST accept recipients of three kinds, mixed: installation users, lists, and
  free addresses typed or pasted (comma, semicolon, space or newline; `Nombre <correo>` accepted).
- **FR-002**: Duplicated addresses MUST collapse to one, the sender's own address MUST be dropped,
  and invalid addresses MUST be shown as invalid and block the send.
- **FR-003**: `EMAIL_ALLOWED_DOMAINS` MUST be an optional restriction: unset or empty (the default)
  accepts any domain; when set it limits free addresses and list members as before.
- **FR-004**: The product MUST NOT impose volume limits: the per-send recipient ceiling and the
  per-user hourly send ceiling MUST be removed, and no new quota may replace them.
- **FR-005**: A send MUST be paced and batched for the provider: `EMAIL_BATCH_SIZE` recipients per
  message via BCC (sender in To) and `EMAIL_SEND_RATE` messages per second (`0` = unlimited).
- **FR-006**: The super user MUST be able to pause all outgoing mail with `EMAIL_SENDING_PAUSED`;
  the queue keeps accepting and the worker holds.
- **FR-007**: A signed-in user MUST be able to create, edit and delete their own lists, with name
  (unique per owner), description, members (address + optional name), and members entered one per
  line, pasted or imported from a CSV `correo,nombre`; lists MUST be exportable as CSV.
- **FR-008**: A list MUST have visibility `personal` or `compartida`; only administrators and the
  super user may create shared lists, and every user with send rights may use them.
- **FR-009**: A member MUST be pausable (kept, never sent to). A list MUST hold up to 1,000 members.
- **FR-010**: A list MUST be able to be dynamic by role (`{role: admin}`), resolving to the
  installation's users with that role at send time.
- **FR-011**: Deleting a list MUST pause every scheduled delivery that uses it, with a reason, and
  MUST NOT delete them.
- **FR-012**: The send dialog MUST offer one recipient box with chips for the three kinds, a bulk
  paste, a live counter, and the options *Adjuntar PDF*, *Incluir enlace* (when enabled) and
  *Guardar estos destinatarios como lista*.
- **FR-013**: Scheduled deliveries MUST accept the same recipient kinds as a send.
- **FR-014**: A project's `distributions/<id>.yaml` MUST accept `recipients: {lists: [...]}` by
  **name only**; an address in that file MUST be refused by the CLI validator and by import.
- **FR-015**: Applying a project MUST refuse a distribution that names a list that does not exist,
  naming it.
- **FR-016**: The dashboard MUST show a send history per dashboard: date, sender, recipient kinds
  and count, per-recipient status with reason, and *Reenviar los fallidos*.
- **FR-017**: Only signed-in users with access to the dashboard may send, list history, or read
  addresses; there MUST be no public endpoint for any of it.
- **FR-018**: Addresses MUST never appear in project files, in the log in clear (masked as
  `a***@dominio`) or in an audit event.
- **FR-019**: Audit events MUST record list created/changed/deleted and send queued with count and
  kinds.
- **FR-020**: The super user MUST be able to restrict free addresses to administrators with
  `EMAIL_FREE_ADDRESSES_ROLE=admin` (default `user`).
- **FR-021**: `EMAIL_FROM_MODE=installation | user` MUST choose whether mail is sent from
  `SMTP_FROM` with the sender as `Reply-To`, or from the sender's own address through the same relay.
- **FR-022**: In-app help MUST have the topics **Enviar por correo** (updated) and **Listas de correo**
  (new) in Spanish and English, with `Relacionados` and app links.

### Key Entities

- **Mailing list**: name, description, owner, visibility, kind (`members` | `role`), role when
  dynamic, timestamps.
- **List member**: address, display name, paused flag, belongs to a list.
- **Send**: as today (dashboard, sender, subject, message, selection, attachments), plus the kinds of
  recipients it used.
- **Delivery**: one address of one send, its status, attempts and reason (unchanged).
- **Subscription**: as today, whose `recipients` may now include `{"list": <id>}` entries.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A sender goes from a dashboard to a 1,500-address delivery in under two minutes and two
  screens (dialog + list picker).
- **SC-002**: A 1,500-address send reaches the provider as ⌈1500 / `EMAIL_BATCH_SIZE`⌉ messages, none
  of them faster than `EMAIL_SEND_RATE` allows.
- **SC-003**: No send is refused for its size or frequency anywhere in the product (grep gate for the
  removed limits).
- **SC-004**: Every address of a send has its own status and, on failure, a reason a sender can act
  on, visible without leaving the dashboard.
- **SC-005**: An installation that never sets `EMAIL_ALLOWED_DOMAINS` can send to any domain, and one
  that sets it keeps refusing others.
- **SC-006**: A project that names an address in `distributions/` is refused before anything is
  written; one that names a list that does not exist is refused at apply with the name.

## Assumptions

- The mail provider is the installation's (SES, Workspace, 365, a corporate relay): bounce handling
  stays out of scope, a failed address is marked and shown.
- Senders stay internal: no public send endpoint and no anonymous access are introduced.
- Lists hold personal data (name and address) in the product database, never in project files — the
  constitution's principle II is respected.
- Existing subscriptions keep working: `recipients: {roles: [...]}` stays valid and keeps resolving
  at send time, so no authored YAML has to change.
