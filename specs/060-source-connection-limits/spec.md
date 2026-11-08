# Feature Specification: Survive "too many clients" on an origin database

**Feature Branch**: `060-source-connection-limits`

**Created**: 2026-11-07

**Status**: Draft

**Input**: User description: "An hourly run of `ventas-medicalvet` failed with `FATAL: lo siento, ya
tenemos demasiados clientes` (SQLSTATE 53300). The origin is the customer's ERP database, whose
`max_connections` the ERP's own clients exhausted. Bizview opens one short-lived connection per
extraction and closes it, but it treats 53300 like any other failure: the run is marked failed, the
next attempt is the next cron tick, and nothing tells the operator that the origin — not Bizview — is
out of slots or how to fix it."

## Context

Bizview reads an origin database it does not own (constitution II and III: read-only, never harmed).
The origin's connection slots are a shared, finite resource, and the ERP that owns the database takes
them first. When the last slot is gone, PostgreSQL refuses the connection itself — no query runs, no
row is read — and Bizview's run ends up in the same red "Falló" state it uses for a broken query, a
failed check or a timeout.

Two costs follow. The dataset keeps its previous data either way, so the *data* is fine, but the
operator cannot tell a self-healing congestion problem from a real defect, and the product neither
waits for a slot to free up nor explains what to do. The fix has three parts: retry politely, be a
smaller neighbour, and say plainly whose limit it is.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A busy origin is a pause, not a failure (Priority: P1)

The super user opens an integration whose hourly run failed. The run is not red: it is amber,
**«La fuente no admite más conexiones ahora»**, with the number of attempts it made and how long it
waited. The dashboard it feeds still shows its numbers with the time of the last good load, and the
next tick is scheduled normally.

**Why this priority**: the reported production incident. Telling congestion apart from a defect is
what stops an operator from "fixing" a healthy integration, and keeping the previous data marked as
such is what stops a reader from distrusting every number after one busy hour.

**Independent Test**: point an integration at a source that refuses connections, run it, and confirm
the run ends amber with no data loss, no change to the dashboard's freshness beyond the last good
load, and a message naming the origin's own limit.

**Acceptance Scenarios**:

1. **Given** an origin that refuses the first two connection attempts and accepts the third, **When**
   the integration runs, **Then** the run succeeds, and its history records that two retries were
   needed and how long they took.
2. **Given** an origin that refuses every attempt, **When** the run finishes, **Then** its state is
   `skipped_busy` (amber, «La fuente no admite más conexiones ahora»), the datasets keep the data and
   the freshness of the previous successful run, and the message carries the SQLSTATE and the
   origin's own words with no host and no credential.
3. **Given** a run that ended `skipped_busy`, **When** the next scheduled time arrives, **Then** the
   run is attempted again as normal — nothing is paused, nothing is disabled.
4. **Given** three consecutive `skipped_busy` runs of the same integration, **When** the third one
   finishes, **Then** exactly one notification reaches the operators through the installation's own
   channel, and the fourth consecutive one does not send another.
5. **Given** a run that is stopped by hand while it waits for a retry, **When** the stop is
   requested, **Then** the run ends `stopped` within a few seconds — the wait never outlives the
   operator's decision.

---

### User Story 2 - Be a small, well-behaved neighbour (Priority: P1)

The customer's DBA looks at the origin's session list and can see which sessions are Bizview's, how
many there are at most, and that they do not linger.

**Why this priority**: the retry above only helps because the slot is eventually free. If Bizview
opens one connection per dataset, per report and per structure scan without a per-source ceiling, it
becomes part of the congestion it is apologising for — and a session left idle inside a transaction
holds a slot all night.

**Independent Test**: with two integrations on one source allowed one connection each, run both at
once and confirm their sessions never overlap; open a direct report and a structure scan and confirm
they queue behind the same ceiling; look at the origin's session list and confirm every Bizview
session is named after the integration it belongs to.

**Acceptance Scenarios**:

1. **Given** a source whose ceiling is one connection, **When** two of its integrations run at the
   same time, **Then** the second waits for the first to release the slot; it does not open a second
   session.
2. **Given** the same source, **When** a direct report or a structure scan needs a session while a run
   holds the slot, **Then** it waits for the same slot rather than opening one of its own.
3. **Given** a task waiting for a slot, **When** it is cancelled or its deadline passes, **Then** it
   releases what it holds and leaves nothing behind.
4. **Given** any Bizview session on the origin, **When** the DBA lists sessions, **Then** its name
   says Bizview and which integration it serves.
5. **Given** an origin whose server supports the idle timeouts, **When** Bizview connects, **Then**
   its session cannot sit idle in a transaction beyond half a minute or idle beyond a minute; on an
   older server that does not know those settings, the connection still succeeds.
6. **Given** an integration with two datasets that read the same origin, **When** the run extracts
   them, **Then** the origin sees one Bizview session for the run, not one per dataset.

---

### User Story 3 - The product says what to do about it (Priority: P2)

The operator who reads the amber run finds a single page that explains that the limit belongs to the
origin, how to see who is holding the slots, and the four real options: put a pooler in front,
raise the limit with the ERP vendor, read a replica, or move the schedule off-peak.

**Why this priority**: without it, the amber state is a nicer word for the same dead end. It is P2
because the product keeps working without the page; the operator does not.

**Independent Test**: open the help topic from the run in both languages and follow its first
instruction on a real origin.

**Acceptance Scenarios**:

1. **Given** an amber run, **When** the operator follows its «Qué hacer» link, **Then** a help topic
   opens in the interface language that names the origin's limit, the two queries that show who holds
   the slots, and the four remedies.
2. **Given** the same situation, **When** the operator reads the installation guide, **Then** the same
   four remedies and the difference between "the origin is out of slots" and "Bizview's own database
   is out of slots" are documented there too.

---

### User Story 4 - Watch the ceiling in the product (Priority: P2)

The super user edits how many simultaneous connections a source allows and sees, when the test
connection runs, the origin's own ceiling and how many clients it already has.

**Why this priority**: the default of one is right for an ERP origin and wrong for a warehouse; a
value nobody can see or change would be a guess baked into the product. The counts turn the next
incident into a number instead of an anecdote.

**Independent Test**: set a source's ceiling to two, run three overlapping extractions and confirm
two proceed and one waits; press "Probar conexión" and see the origin's maximum and its current
clients, or a clear "no permission to see it" when the role cannot read the activity list.

**Acceptance Scenarios**:

1. **Given** a source, **When** the super user sets «Conexiones simultáneas», **Then** the value is
   stored with the source and used by every reader of that source; values outside a sane range are
   refused with a message naming the range.
2. **Given** a PostgreSQL source whose role may read the origin's session list, **When** the test
   connection runs, **Then** the result reports the origin's maximum connections and its current
   client count.
3. **Given** a role that may not read the session list, **When** the test connection runs, **Then**
   the connection is still reported healthy and the counts say "sin permiso para verlo" / "no
   permission to see it".

---

### Edge Cases

- The origin refuses with a pooler's own wording (`no more connections allowed`, PgBouncer's
  `server_login_retry`) instead of SQLSTATE `53300`: it is the same condition and must be classified
  the same way.
- The origin answers "out of memory" (`53200`) or "cannot connect now" (`57P03`, e.g. during
  recovery): also a *pending* condition, not a defect — treated as busy.
- The origin's network is unreachable: that is **not** busy. It stays a failure after the retries that
  the product already performs, and the message keeps saying the source did not answer.
- The failure happens after the connection was made (a query cancelled, a permission error): not
  busy. Only connection-slot refusals are amber.
- The whole installation has no work to do because every source is busy: the queue keeps accepting
  runs and they end amber one after another; nothing is disabled and no operator action is required.
- The wait for a retry is longer than the integration's own time limit: the run ends `skipped_busy`
  rather than being killed mid-wait, because nothing was read.
- A retry succeeds and the run then fails for a different reason: the run is `failed`, with the
  retries listed in its details.
- The same source is used by integrations with different time zones and windows: the ceiling is per
  source, not per integration, and does not depend on either.
- A source is deleted or disabled while a task waits for its slot: the waiting task ends as it does
  today (source missing / disabled) without leaking the slot.
- Two operators press "Ejecutar ahora" while the ceiling is taken: both queue, and each release
  returns the slot to the next one.

## Requirements *(mandatory)*

### Functional Requirements

**Classification and retry**

- **FR-001**: The product MUST recognise connection-slot refusals from an origin as a distinct
  condition: the SQLSTATEs for too many connections, out of memory, cannot-connect-now and the
  connection-failure class, the pooler wordings that stand for them, and the equivalent refusals of
  the other source kinds where they exist.
- **FR-002**: On that condition a run MUST retry inside the run, with exponential backoff and
  jitter, up to a configurable number of attempts and a configurable base delay (defaults: 4
  attempts, 15 s base → about 15 s, 45 s, 2 min, 5 min).
- **FR-003**: A retry MUST be interruptible: a stop requested by an operator, or the run's deadline,
  ends the wait promptly and the run reports what happened.
- **FR-004**: A run whose retries are exhausted MUST end in the new state `skipped_busy`, shown amber
  and never red.
- **FR-005**: A `skipped_busy` run MUST NOT touch the datasets: no rows replaced, no deletions, no
  schema change, and no change to the freshness of anything.
- **FR-006**: The stored message of a `skipped_busy` run MUST say «La fuente no admite más conexiones
  ahora» / "The source has no free connection slots", carry the SQLSTATE, the number of attempts and
  the total wait, and include the origin's own words with host and credential removed.
- **FR-007**: Three consecutive `skipped_busy` runs of one integration MUST produce exactly one
  notification, and the streak MUST NOT produce another until a run of that integration succeeds.
- **FR-008**: Any failure that is not a slot refusal MUST keep today's behaviour and wording; a run
  that retried and then failed another way MUST list the retries it made.

**Politeness**

- **FR-009**: Each source MUST have a ceiling of simultaneous origin connections (default 1, 2 for
  the hosted API sources), editable by the super user, and every reader of that source — scheduled
  runs, manual runs, direct reports, structure generation and describe — MUST respect the same
  ceiling.
- **FR-010**: A task waiting for its source's ceiling MUST wait rather than fail, and MUST say it is
  waiting («Esperando turno en la fuente») while it does.
- **FR-011**: Waiting MUST release and reclaim nothing it does not own: a cancelled or expired
  waiter leaves no permit held and no connection open.
- **FR-012**: A run MUST hold at most one origin connection at a time and MUST reuse it across the
  datasets of its integration instead of opening one per dataset.
- **FR-013**: Every origin session MUST name Bizview and the integration it serves, so an
  administrator at the origin can attribute it.
- **FR-014**: A session MUST give up its origin slot quickly when it is not working: the connection
  attempt MUST be bounded (10 s), and where the server understands them, the session MUST be limited
  to 30 s idle inside a transaction and 60 s idle.
- **FR-015**: The installation-wide ceiling on parallel work MUST stay the worker's global limit; the
  per-source ceiling is a second, smaller bound and never replaces it.
- **FR-016**: When an integration accumulates three or more `skipped_busy` runs in a day, its page
  MUST suggest the quietest hour for its schedule, derived from the run history already stored.

**Telling the operator**

- **FR-017**: A help topic «La fuente no admite más conexiones» / "The source has no free connection
  slots" MUST exist in both languages, reachable from the amber run, and MUST cover: whose limit it
  is, how to see the ceiling and who holds the slots, that Bizview's own ceiling and short-lived
  sessions are not the cause, the four remedies (pooler, raise the limit with the vendor, read a
  replica, off-peak or a wider window / `materialize: daily`), and how to tell this apart from
  Bizview's own database running out of connections.
- **FR-018**: The installation guide MUST document the same four remedies and the two
  configurations this feature adds.

**Interface**

- **FR-019**: The integration's run list MUST show a `skipped_busy` run with an amber badge, the
  attempts and total wait, and a «Qué hacer» / "What to do" link to the help topic.
- **FR-020**: The source page MUST show the connection ceiling as an editable value for the super
  user, and the last test connection MUST report the origin's maximum connections and current
  clients when the credential may read them, and say it may not otherwise.
- **FR-021**: Every new text MUST exist in Spanish and English, and no message may include a host,
  a port or a credential.

### Key Entities

- **Source connection ceiling**: the number of simultaneous origin sessions one source allows,
  stored with that source; installation defaults for the two kinds that ship a value.
- **Run state `skipped_busy`**: a sixth outcome of an integration run, beside running, succeeded,
  failed, skipped and stopped; amber, never counted as a defect, and the one state that means "the
  origin was full".
- **Retry record**: for a run, the number of attempts made, the delays used and the total time waited,
  kept with the run's details so the history explains the delay.
- **Busy streak**: how many consecutive `skipped_busy` runs an integration has, and whether the
  notification for that streak has already been sent.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100 % of connection-slot refusals from an origin end in a run that either succeeds
  after retrying or is reported as `skipped_busy`; none is reported as a failure.
- **SC-002**: A `skipped_busy` run leaves the served data byte-identical to what it was before, with
  the same freshness timestamp.
- **SC-003**: An operator can tell, from the run alone, that the cause is the origin's limit and find
  the remedies in one click.
- **SC-004**: No source ever has more simultaneous Bizview sessions than its ceiling, measured at the
  origin, across runs, direct reports and structure generation.
- **SC-005**: An administrator at the origin can attribute every Bizview session to an integration
  from the session list alone.
- **SC-006**: A streak of busy runs of any length produces at most one notification.
- **SC-007**: The default ceilings (1 for PostgreSQL origins, 2 for hosted API sources) require no
  configuration to be safe, and raising one is a single field on the source.

## Assumptions

- The origin is PostgreSQL for the retry of connection refusals; the other source kinds inherit the
  classification where a comparable refusal exists and otherwise keep today's behaviour.
- "Consecutive" means consecutive runs of that integration, whatever the run kind (scheduled or
  manual); a stopped run neither extends nor resets a streak.
- The notification channel is the one the installation already has configured (the bot, when it is
  enabled and an operator has linked it); when no channel is configured, the audit trail and the run
  list are the record — the product does not invent a mail server.
- The quietest hour is derived from the run start times already stored; a run history shorter than a
  day yields no suggestion rather than a guess.
- Retry defaults are suited to an hourly integration; an integration with a longer window may raise
  them, and the values are installation settings, not project files.
- Constitution II already says origin reads are read-only and must not harm the origin; this feature
  reads that as also "never hold a slot it does not need, and never take more than it declared".
