# Research — mailing lists and unlimited recipients

Feature 058, 2026-11-06. Each decision names what it replaces and why the alternative was rejected.

## R1 — Where a list lives: table vs. JSON

**Decision**: a real table pair, `mail_list` + `mail_list_member`, owned by an `app_user` and
optionally visible to everybody (`visibility = personal | compartida`).

**Rationale**: a list is edited by one person and used by many; it needs an owner to enforce "only
the owner edits", a name unique per owner, and rows to pause a member individually. The CSV export and
the 1,000-member cap are queries, not document surgery.

**Alternatives**: JSON inside `email_subscription.recipients` (rejected: no owner, no sharing, no
per-member flag, no way to delete a list independently of a subscription); reusing `dashboard_access`
style grants (rejected: overkill, lists are installation-wide).

## R2 — Dynamic-by-role lists

**Decision**: keep `{"role": "admin"}` recipients exactly as feature 018 wrote them and expose them as
a **list of kind `role`** in the UI (a `mail_list` row with `kind = 'role'` and `role = 'admin'`, no
members). Resolution happens at send time, as today.

**Rationale**: authored `distributions/*.yaml` already says `recipients: {roles: [admin]}`; a
synthetic list row per role would either duplicate the role or require rewriting every existing
project. A `kind` column keeps one UI ("lists") over two implementations (members, role) without
touching authored YAML.

**Alternatives**: a `role` list per installation created by migration (rejected: it would have to be
created for each installation and kept in step with `app_user.role` changes); resolving roles into
members at edit time (rejected: a new administrator would be missing until somebody edits the list).

## R3 — Batches, pacing and per-recipient status

**Decision**: `EmailDelivery` keeps **one row per address**, in both modes. The send job groups the
pending deliveries of one send into chunks of `EMAIL_BATCH_SIZE`; per chunk it builds **one SMTP
message** with the addresses in BCC and the sender in To (`EMAIL_INDIVIDUAL_MESSAGES=false`, the
default), or one message per address (`true`). Between messages it sleeps to honour
`EMAIL_SEND_RATE` (a token bucket: `next_at = last_at + 1/rate`).

**Rationale**: status, retries and "re-send the failed ones" already key on `email_delivery`; changing
that shape would rewrite the history UI and the retry logic. A BCC batch keeps the provider calls
proportional to ⌈N/size⌉ while leaving one row per person to mark.

**Alternatives**: one `EmailDelivery` per batch (rejected: a bounce or a provider error would mark 50
people with one reason and no way to re-send individually); per-recipient always (rejected: 1,500 SMTP
conversations for one send).

## R4 — Where the domain filter applies

**Decision**: `EMAIL_ALLOWED_DOMAINS` empty ⇒ any domain. `resolve_recipients` applies the list only
to **free addresses and list members**; installation users are always allowed (they are inside).

**Rationale**: the filter exists to stop a sender from mailing the world; it cannot be a per-list
constraint because lists are shared. Keeping the check in `resolve_recipients` means every door
(dialog, subscription, distribution at apply) inherits it.

**Alternatives**: validate at list creation (rejected: an installation that later sets the filter
would keep lists it can no longer use, silently); validate only in the dialog (rejected: a
subscription could still fan out to a refused domain).

## R5 — From and Reply-To

**Decision**: `EMAIL_FROM_MODE=installation` (default) sends `From: SMTP_FROM` with
`Reply-To: <sender>`; `user` sends `From: <sender>` through the same relay. Both are configuration,
audited by the existing `email_sent` event (it already records who sent).

**Rationale**: a corporate Workspace/365 tenant can be authorised to send as its users; a plain SMTP
account cannot. The product cannot decide that, the operator can.

**Alternatives**: always the user's address (rejected: most relays reject a foreign From); per-user
SMTP credentials (rejected: secrets per user, out of scope).

## R6 — Pausing outgoing mail

**Decision**: `EMAIL_SENDING_PAUSED=true` makes `process_due` return without claiming deliveries (the
queue keeps growing, the worker holds). The dialog still accepts the send and the UI says delivery is
paused.

**Rationale**: a panic switch must not lose work. Refusing new sends would make the operator's
decision land on the user's screen; holding the queue keeps the promise of the audit event.

**Alternatives**: refuse new sends (rejected: the user loses the composed message); stop the worker
(rejected: also stops integrations).

## R7 — Lists inside `distributions/*.yaml`

**Decision**: `recipients: {lists: ["Gerencia comercial"]}` — **names**, resolved at apply. The CLI
schema refuses `roles`/`lists` entries that look like an address (any `@`), and apply refuses a name
with no list in the installation, naming it.

**Rationale**: constitution II — no personal data in project files — and the project must keep working
after the author leaves, so the YAML carries identities the installation owns, not addresses.

**Alternatives**: put addresses in the YAML (rejected: personal data in Git); reference lists by id
(rejected: ids differ per installation, so a project would not be portable).

## R8 — Deleting a list

**Decision**: `mail_list.deleted_at` (soft delete). Every `email_subscription` whose `recipients`
mentions the list is paused with `paused_reason = "list_deleted"`. Nothing is deleted.

**Rationale**: a scheduled delivery that silently stops is worse than one that says why; the authored
project may still name the list, and apply must keep failing loudly until somebody recreates it.

**Alternatives**: cascade delete (rejected: data loss of the delivery history); refuse deletion while
used (rejected: leaves the owner trapped).

## R9 — Address parsing

**Decision**: one parser in `app/mail/addresses.py` shared by the API (chips and bulk paste) and the
worker: splits on `, ; \n \t`, accepts `Nombre <correo>` and bare addresses, lowercases, collapses
duplicates, drops the sender's own address, and reports invalid entries with their raw text so the
dialog can show them in red.

**Rationale**: the browser and the server must agree about what "37 destinatarios" means; doing it
twice is how the counter and the deliveries drift.

**Alternatives**: parse only in the browser (rejected: the API is the security boundary); a
third-party parser (rejected: constitution V, and the format is trivial).
