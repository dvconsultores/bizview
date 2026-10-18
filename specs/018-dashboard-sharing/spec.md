# Feature Specification: Dashboard sharing — email and expiring links

**Feature Branch**: `018-dashboard-sharing`

**Created**: 2026-10-05

**Status**: Implemented (closed 2026-10-08, full suites green)

**Input**: Owner, 2026-10-05: "send dashboard via email; share a dashboard link, establishing how
many days".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Share a dashboard with a link that expires (Priority: P1) 🎯

An administrator opens a dashboard, presses "Compartir", chooses for how many days the link is
valid, and copies a link. Anyone with the link sees that dashboard read-only, without an account,
until the link expires or is revoked.

**Why this priority**: the fastest way to show a dashboard to someone without an account.

**Independent Test**: create a 1-day link, open it in a private window (no session) → the dashboard
renders and its PDF downloads; move the clock past the expiry or revoke it → "Este enlace expiró o
fue revocado"; no other dashboard or API is reachable with that link.

**Acceptance Scenarios**:

1. **Given** sharing is enabled for the installation and an administrator can see a dashboard,
   **When** they press "Compartir" and choose 1–90 days (default 7) and an optional note, **Then** a
   link is created, shown once with a copy button, and listed under "Enlaces activos" with creator,
   expiry, number of visits and last visit.
2. **Given** a valid link, **When** anyone opens it, **Then** the dashboard renders read-only marked
   "Vista compartida · vence el <fecha>": period, comparison and filters work, the PDF downloads if
   the report allows it; no navigation, no account menu, no AI summary generation, no other
   dashboard.
3. **Given** an expired or revoked link, **When** opened, **Then** a neutral page says the link
   expired or was revoked, with no data and no hint of which dashboard it was.
4. **Given** an active link, **When** an administrator presses "Revocar", **Then** it stops working
   immediately; creation and revocation are audited.
5. **Given** the dashboard is removed from the workspace or archived, **Then** its links stop
   working.

---

### User Story 2 - Send a dashboard by email (Priority: P1)

A user who can see a dashboard presses "Enviar por correo", picks recipients, writes an optional
message, and the recipients receive an email with the dashboard PDF for the current period and
filters, and optionally a link valid for N days.

**Why this priority**: the owner's main request; managers expect reports in their inbox.

**Independent Test**: with a test SMTP server, send the dashboard to two users and one allowed
external address → three emails arrive with the PDF attached (same figures as the screen) and the
optional link; the send is listed with its status.

**Acceptance Scenarios**:

1. **Given** email is configured and enabled, **When** a user with access presses "Enviar por
   correo", **Then** a view (not a modal) lets them choose recipients (installation users by name,
   plus external addresses only in allowed domains), subject (prefilled), message (optional), "Adjuntar
   PDF" (on by default, current selection) and "Incluir enlace" with days (administrators only).
2. **Given** a valid request, **When** sent, **Then** the send is queued, the worker renders the PDF
   with the same code as the dashboard download and delivers one email per recipient; the user sees
   the status (en cola, enviado, falló con motivo) in "Envíos".
3. **Given** an address outside the allowed domains or more than 20 recipients, **Then** the request
   is refused with the reason before anything is sent.
4. **Given** SMTP fails for one recipient, **Then** that delivery is retried up to 3 times with
   backoff and then marked failed with a sanitized reason; other recipients are unaffected.

---

### User Story 3 - Scheduled email delivery (Priority: P2)

An administrator subscribes recipients to a dashboard: daily, weekly (day) or monthly (day of month)
at an hour, with the period to send (e.g. ayer, últimos 7 días, mes anterior).

**Independent Test**: a daily subscription at the next minute (test clock) → the worker sends the
email once, records it, and the next run is scheduled; pausing stops it.

**Acceptance Scenarios**:

1. **Given** an administrator, **When** they create a subscription (recipients, frequency, hour,
   period, attach PDF, include link days), **Then** it appears in "Envíos programados" with its next
   run, and can be paused, edited or deleted (audited).
2. **Given** a subscription is due, **When** the worker runs, **Then** it sends exactly once per due
   time even if the worker restarts, using the data available at that moment.
3. **Given** a recipient user is deactivated or loses access to the dashboard, **Then** they stop
   receiving it.

---

### User Story 4 - Configure email (Priority: P1)

The super user configures the SMTP server in Administración → Correo: host, port, security
(STARTTLS / SSL / ninguna — "ninguna" refused in the internet profile), user, password (encrypted,
write-only), sender name and address, allowed external domains, and enables it; "Enviar correo de
prueba" sends to themselves.

**Acceptance Scenarios**:

1. **Given** the super user, **When** they save the settings, **Then** the password is stored
   encrypted and never returned; a test email reports success or a sanitized error.
2. **Given** email is disabled or not configured, **Then** "Enviar por correo" is hidden and the
   API refuses sends.
3. **Given** the super user, **When** they toggle "Enlaces compartidos" (off by default), **Then**
   sharing becomes available or every link stops working while it is off.

### Edge Cases

- A user loses access to the dashboard after queuing a send: the worker re-checks access and skips.
- A link's dashboard report changes version: the link shows the current version.
- Brute-force link guessing: tokens have 256 bits of randomness, only their hash is stored, and
  public access is throttled per address.
- Search engines: shared pages send `noindex` and `no-store`.
- Large PDFs: attachments over 10 MB are not attached; the email carries the link instead (or a
  failure if no link was requested).
- The SMTP password or server errors never appear in API responses, logs or audit text.

## Requirements *(mandatory)*

### Functional Requirements

#### Share links
- **FR-001**: Administrators and the super user MAY create share links for dashboards they can see,
  with an expiry of 1–90 days (default 7) and an optional note (≤ 200 chars); at most 20 active links
  per dashboard.
- **FR-002**: The link token MUST have ≥ 256 bits of randomness; only its hash is stored; the full
  link is shown once at creation.
- **FR-003**: A valid link grants read-only access to exactly one dashboard (definition, data,
  filter values, PDF) and nothing else; AI narrative generation is not available through links
  (a cached narrative may be shown).
- **FR-004**: Links stop working at expiry, on revocation, when sharing is disabled, or when the
  dashboard is no longer available. Visits are counted (count, last visit time; no IP stored beyond
  the audit/throttle rules).
- **FR-005**: Creation, revocation and the sharing toggle are audited; public access is throttled
  per address.

#### Email
- **FR-006**: Email settings are a singleton managed by the super user; the password is encrypted
  at rest (AES-256-GCM, like source secrets) and write-only; test email to the super user.
- **FR-007**: Any user with access to a dashboard MAY send it by email to installation users; external
  addresses only in super-user-allowed domains; ≤ 20 recipients per send; ≤ 30 sends per user per hour.
- **FR-008**: Emails contain subject, optional message, the PDF of the selected period/filters
  rendered by `backend/app/reports/pdf.py`, and optionally a share link (administrators only) valid
  for N days; HTML + plain-text parts; organization name/branding from installation settings.
- **FR-009**: Delivery happens in the worker from a queue; per-recipient status, up to 3 retries
  with backoff; errors sanitized.
- **FR-010**: Scheduled subscriptions (P2): frequency daily / weekly (weekday) / monthly (day 1–28),
  hour, installation timezone, period preset, recipients as in FR-007, attach PDF, include link
  days; exactly-once per due time; paused/edited/deleted by administrators; audited.

#### UI
- **FR-011**: Dashboard view: "Compartir" (administrators) and "Enviar por correo" (users with
  access, when email is enabled) as views, not modals; "Enlaces activos", "Envíos" and "Envíos
  programados" lists per dashboard; Administración → Correo settings page; phones supported.

### Key Entities

- **Share link**: dashboard, token hash, note, created by, created at, expires at, revoked at/by,
  visits, last visit.
- **Email settings**: host, port, security, username, password (encrypted), sender name/address,
  allowed domains, enabled, sharing enabled, last test result.
- **Email send**: dashboard, requested by, recipients, subject, message, selection (period, filters),
  attach PDF, link days, status per recipient, attempts, sanitized error, created/sent times.
- **Subscription**: dashboard, created by, recipients, frequency, hour, weekday/day, period preset,
  attach PDF, link days, paused, last run, next run.

## Success Criteria *(mandatory)*

- **SC-001**: A shared link opened without an account renders the dashboard and its PDF within the
  same time as a signed-in view, and stops working within 1 minute of expiry or revocation.
- **SC-002**: 0 data reachable through a link other than its one dashboard (API probe test over every
  route).
- **SC-003**: An email send to 3 recipients arrives with a PDF whose figures equal the screen for the
  same selection, in 100% of e2e runs against a test SMTP server.
- **SC-004**: A due subscription is sent exactly once across a worker restart.
- **SC-005**: The SMTP password never appears in any API response, log line or audit entry.

## Assumptions

- SMTP is reached with Python's standard library (`smtplib`, `email`); no new stack component (an
  external mail server is installation configuration, like the Telegram bot).
- Links are built from `SITE_ADDRESS`; in the private profile without a domain, the address the
  administrator used is used.
- Share links show the dashboard as administrators see it (reports have no per-user row filtering
  today).
- Recipients' email addresses are installation users' own addresses or addresses the super user
  allowed by domain; no newsletter or bulk mail features.

## Amendment 2026-10-07 (owner): email configuration from the environment

Owner, 2026-10-07: "correo email will get values from env, do not use an option for this".
Supersedes US4 AC1/AC3 and FR-006's settings form:

- **FR-012**: SMTP and sharing settings come only from the installation environment, like the AI
  settings: `SMTP_HOST`, `SMTP_PORT` (default 587), `SMTP_SECURITY` (`starttls` | `ssl` | `none`;
  default `ssl` when the port is 465, else `starttls`; `none` refused at startup in the internet
  profile), `SMTP_USER`, `SMTP_PASSWORD` (secret: never returned, shown or logged), `SMTP_FROM`
  (sender address), `SMTP_FROM_NAME`, `EMAIL_ALLOWED_DOMAINS` (comma-separated external domains,
  default none), `SHARE_LINKS_ENABLED` (default `false`). Email is enabled when `SMTP_HOST` and
  `SMTP_FROM` are set.
- **FR-013**: There is no email option in Administración (no Correo tile or page). Email and shared
  links are available in the dashboard views when the environment enables them; the setup is checked
  with `python -m app.cli mail-test <address>` (sends a test email, prints a sanitized result).
