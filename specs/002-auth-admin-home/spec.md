# Feature Specification: Platform Foundation — Sign-in, User Administration and Dashboard Home

**Feature Branch**: `002-auth-admin-home`

**Created**: 2026-09-29

**Status**: Implemented (closed 2026-10-08, full suites green)

**Input**: User description: "Simple login with a default super user from SUPER_USER_EMAIL and
SUPER_USER_PASSWORD that can manage everything. Login page; inside, an admin manager to handle
user creation and password change; admin access to dashboards and a home page with the available
dashboards. Modern web interface, 100% mobile-first, must work in all browsers, blue colour
scheme. Create the model and migration in the BI database (DATABASE_URL_BI). A standard product
for different customers. Folder structure: front, backend, report, etl (or the recommended best
practice). Caddy as proxy. Act autonomously and choose the recommended option."

## Clarifications

### Session 2026-09-29

Answered autonomously with the recommended option, at the user's request ("respond the
recommended option and the best practice").

- Q: Who can manage administrators? → A: Only the super user creates, promotes, demotes, or
  deactivates administrators. Administrators manage regular users. Nobody can deactivate, demote,
  or delete the super user.
- Q: What happens when the configured super user password is changed after the first start? →
  A: The configured password is used only to create the super user the first time. Later changes
  in configuration are ignored unless an operator explicitly requests a super-user password
  reset (recovery). A password the super user changed in the interface is therefore not
  overwritten on restart.
- Q: How does a new user get a password, given that no email service exists yet? → A: The
  administrator sets a temporary password when creating the user (or when resetting it) and hands
  it over. The user must replace it at their next sign-in.
- Q: Can users be deleted? → A: No. Users are deactivated, never deleted, so the history of who
  did what stays intact.
- Q: Which dashboards appear on the home page? → A: Dashboards come from a product catalogue that
  ships with each release. Administrators and the super user see all active dashboards; regular
  users see only the dashboards they were granted. A dashboard that is not built yet shows as
  "Próximamente" (coming soon) and cannot be opened.
- Q: What does "standard product for different customers" mean for this feature? → A: One code
  base deployed once per customer organisation. The product name, organisation name, and logo are
  set per deployment; no customer name is hard-coded. (Customer accounts inside a deployment are
  introduced by feature 001.)
- Q: Which browsers are "all browsers"? → A: The current and previous major versions of Chrome,
  Edge, Firefox, and Safari on desktop; Safari on iOS 14 and later; Chrome and Samsung Internet on
  Android 8 and later. Internet Explorer is not supported.

## User Scenarios & Testing *(mandatory)*

Actors:

- **Super user** — the single built-in account defined at deployment time. Manages everything,
  including administrators.
- **Administrator** — manages regular users and their dashboard access; sees all dashboards.
- **User** — a regular person who signs in and opens the dashboards granted to them.

### User Story 1 - Sign in and reach the home page (Priority: P1)

A person opens the product on their phone, sees a clean sign-in page with the product name and
logo, enters their email and password, and lands on a home page that lists the dashboards they
can open as large, tappable cards. They can sign out from any page.

**Why this priority**: nothing else in the product is reachable without it; with only the
built-in super user it is already a working, secured entry point.

**Independent Test**: on a fresh deployment, sign in on a 375 px phone screen with the configured
super-user email and password and verify the home page shows the dashboard catalogue; sign out
and verify protected pages redirect to sign-in.

**Acceptance Scenarios**:

1. **Given** a fresh deployment with the super-user email and password configured, **When** the
   system starts for the first time, **Then** the super user exists and can sign in with those
   credentials.
2. **Given** a person on the sign-in page, **When** they enter a correct email and password,
   **Then** they land on the home page with a greeting and the dashboards available to them.
3. **Given** a person on the sign-in page, **When** they enter a wrong email or password, **Then**
   they see one generic message ("Correo o contraseña incorrectos") that does not reveal which
   of the two was wrong.
4. **Given** five consecutive failed attempts for the same account, **When** a sixth attempt is
   made within 15 minutes, **Then** sign-in is refused with a message that states how many
   minutes remain, even if the password is right.
5. **Given** a signed-out person, **When** they open any page other than sign-in, **Then** they
   are sent to sign-in and, after signing in, return to the page they asked for.
6. **Given** a signed-in person, **When** they choose "Cerrar sesión", **Then** their session ends
   and the back button does not show protected content.

---

### User Story 2 - Administer users (Priority: P2)

The super user or an administrator opens the administration area, sees the list of users with
their role and status, searches it, creates a user with a temporary password, edits a user's
name and role, deactivates or reactivates a user, and resets a user's password.

**Why this priority**: the product is useless to anyone except the super user until people can be
added; it is the second step of every deployment.

**Independent Test**: as the super user, create an administrator and a regular user; sign in as
each with the temporary password, confirm each is forced to choose a new password, then
deactivate the regular user and confirm they can no longer sign in.

**Acceptance Scenarios**:

1. **Given** an administrator in the user list, **When** they create a user with email, full
   name, role "Usuario", and a temporary password, **Then** the user appears in the list as active
   and must change the password at first sign-in.
2. **Given** an email that already belongs to a user (in any letter case), **When** an
   administrator tries to create another user with it, **Then** creation is refused with a clear
   message.
3. **Given** an administrator, **When** they try to create, promote, edit, or deactivate an
   administrator, **Then** the action is refused; only the super user may do it.
4. **Given** any administrator (including the super user), **When** they try to deactivate or
   demote the super user or themselves, **Then** the action is refused.
5. **Given** an active user who is signed in on two devices, **When** an administrator deactivates
   them, **Then** both sessions end within one request and further sign-ins are refused.
6. **Given** a user who forgot their password, **When** an administrator resets it to a new
   temporary password, **Then** all the user's sessions end, the old password stops working, the
   lockout is cleared, and the user must change the temporary password at next sign-in.
7. **Given** a regular user, **When** they try to open the administration area (by menu or by
   typing the address), **Then** they see "No autorizado" and no user data.

---

### User Story 3 - Change my own password (Priority: P3)

Any signed-in person opens their profile and changes their password by entering the current one
and the new one twice. A person who signed in with a temporary password is taken to this screen
before anything else.

**Why this priority**: required for security hygiene and for the temporary-password flow of
Story 2, but the product is usable (with admin resets) before it exists.

**Independent Test**: sign in, change the password, sign out, confirm the old password fails and
the new one works; confirm sessions on other devices ended.

**Acceptance Scenarios**:

1. **Given** a signed-in user, **When** they enter the correct current password and a valid new
   password twice, **Then** the password changes, their other sessions end, and the current
   session continues.
2. **Given** a wrong current password, **When** they submit, **Then** the change is refused and
   counts as a failed attempt for lockout purposes.
3. **Given** a new password that does not meet the rules (fewer than 10 characters, equal to the
   current one, or containing the email name), **When** they submit, **Then** the form explains
   which rule failed, next to the field.
4. **Given** a user who must change a temporary password, **When** they try to open any other page,
   **Then** they are kept on the change-password screen until they finish or sign out.

---

### User Story 4 - Control dashboard access (Priority: P4)

An administrator opens a regular user's detail and switches on or off each dashboard from the
catalogue. The user's home page then shows exactly the granted dashboards. Administrators and the
super user always see every active dashboard.

**Why this priority**: until more than one dashboard exists, every user can be granted the single
sales dashboard; per-dashboard control matters as the catalogue grows.

**Independent Test**: grant a regular user one of two catalogue dashboards, sign in as that user,
verify only that card appears, and verify opening the other dashboard's address shows
"No autorizado".

**Acceptance Scenarios**:

1. **Given** a regular user with no grants, **When** they sign in, **Then** the home page shows a
   friendly empty state ("Aún no tienes tableros asignados. Contacta a tu administrador.").
2. **Given** an administrator, **When** they grant a dashboard to a user, **Then** the card appears
   on the user's home page at their next page load.
3. **Given** a revoked grant, **When** the user opens that dashboard's address directly, **Then**
   access is refused.
4. **Given** a dashboard marked "Próximamente", **When** any user sees its card, **Then** the card
   is visibly disabled and cannot be opened.

---

### User Story 5 - Deploy the same product for a new customer (Priority: P5)

An operator deploys the product for a new customer organisation by setting the product name,
organisation name, logo, public address, database connection, and super-user credentials,
without changing any code. The existing data in the customer's BI database is left untouched.

**Why this priority**: it turns the work into a reusable product; the first deployment works
without it, but every later customer depends on it.

**Independent Test**: start two deployments with different names and logos from the same build;
verify each shows its own branding on sign-in and home, and verify that tables already present
in the BI database are unchanged (same structure and row counts) after setup.

**Acceptance Scenarios**:

1. **Given** a deployment configured with product name "X" and organisation "Y", **When** a
   person opens sign-in, **Then** "X" and "Y" (and the logo, if configured) appear, and the browser
   tab title shows "X".
2. **Given** a BI database that already contains tables, **When** the product sets up its own
   data, **Then** it creates only its own separate area and does not alter or read existing
   tables.
3. **Given** a public address with a domain name, **When** the product starts, **Then** it is
   reachable over an encrypted connection with a valid certificate obtained automatically.

---

### Edge Cases

- **Super-user credentials missing or weak in configuration** on first start: the system refuses
  to start and states which setting is wrong (no product running without an administrator).
- **Super user already exists** and configuration changes: configuration is ignored unless the
  operator requests a recovery reset; the event is recorded.
- **Configured super-user email already used by a regular user**: that account is promoted to
  super user on first start and the event is recorded.
- **Email case and spaces**: " Ana@Example.com " and "ana@example.com" are the same user.
- **Deactivated user signs in** with the right password: refused with the same generic message as
  a wrong password (no account-state disclosure).
- **Session expires while a form is open**: on submit, the person is sent to sign-in and returns
  to the same page; unsaved form input may be lost, and the page says the session ended.
- **Two administrators edit the same user at once**: the last save wins; both see the result on
  reload.
- **Slow or offline phone**: buttons show a busy state while a request is in progress and cannot
  be tapped twice; network errors show a retry message instead of a blank screen.
- **Very narrow screens (320 px) and large text settings**: no horizontal scrolling; long names
  and emails wrap or truncate with the full value available.
- **Browser without JavaScript**: the page states that JavaScript is required.

## Requirements *(mandatory)*

### Functional Requirements

**Sign-in and sessions**

- **FR-001**: The system MUST let people sign in with email and password; emails are compared
  without regard to letter case or surrounding spaces.
- **FR-002**: Failed sign-ins MUST show one generic message that does not reveal whether the email
  exists, the password was wrong, or the user is deactivated.
- **FR-003**: After 5 consecutive failed attempts on an account, sign-in to that account MUST be
  refused for 15 minutes; the message states the minutes remaining. A successful sign-in resets
  the count.
- **FR-004**: A session MUST end after 7 days without activity or 30 days after sign-in, whichever
  comes first, and immediately on sign-out, deactivation, password change (other sessions), or
  password reset (all sessions).
- **FR-005**: Every page except sign-in MUST require a valid session; a signed-out visitor is sent
  to sign-in and returned to the requested page afterwards (only pages of this product).
- **FR-006**: Passwords MUST never be stored or logged in readable form, and MUST never be shown
  back to anyone after being entered.

**Super user**

- **FR-007**: On first start the system MUST create the super user from the configured email and
  password if no super user exists; it MUST refuse to start if either is missing or the password
  breaks the password rules (FR-015).
- **FR-008**: After creation, configuration changes to the super-user password MUST NOT change the
  stored password, unless the operator explicitly requests a recovery reset; the recovery reset
  MUST clear lockout and end the super user's sessions.
- **FR-009**: There MUST be exactly one super user. It cannot be deactivated, demoted, or have its
  email changed from the interface, by anyone.

**User administration**

- **FR-010**: Administrators and the super user MUST be able to list users (name, email, role,
  status, last sign-in) with search by name or email, and filter by role and status.
- **FR-011**: Administrators and the super user MUST be able to create a user with email, full
  name, role, and a temporary password; emails MUST be unique regardless of letter case.
- **FR-012**: Administrators MUST be able to edit the name of, deactivate, reactivate, and reset
  the password of regular users. Only the super user may do this for administrators, and only the
  super user may give or remove the administrator role.
- **FR-013**: Nobody may deactivate or demote themselves.
- **FR-014**: A password set by someone else (creation or reset) MUST be temporary: the user must
  replace it before using any other page.
- **FR-015**: Password rules: 10 to 128 characters, not equal to the email or containing the part
  of the email before "@", and a new password MUST differ from the current one. The form MUST
  show the rules before submit.
- **FR-016**: Users are never deleted; deactivation keeps the record and its history.

**Own password**

- **FR-017**: Every signed-in person MUST be able to change their own password by giving the
  current password and the new one twice. A wrong current password counts towards lockout.

**Dashboards and home**

- **FR-018**: The system MUST keep a catalogue of dashboards with name, short description, icon,
  display order, and status (available, coming soon, or hidden). The catalogue ships with each
  release; feature 001's sales dashboard ("Ventas") is its first entry, marked "coming soon"
  until feature 001 is delivered.
- **FR-019**: Administrators and the super user MUST be able to grant and revoke individual
  dashboards to regular users; administrators and the super user always have access to all
  dashboards that are not hidden.
- **FR-020**: The home page MUST show the signed-in person's accessible dashboards as cards in
  catalogue order, a greeting with their name, and an empty state when none are granted.
- **FR-021**: Opening a dashboard address without access, or a "coming soon" dashboard, MUST be
  refused, whether reached from the home page or by typing the address.

**Audit**

- **FR-022**: The system MUST record: sign-in success, failure, and lockout; sign-out; user
  created, edited, deactivated, reactivated; role changed; password changed or reset; dashboard
  granted or revoked; super-user created, promoted, or recovered. Each record has time, acting
  user, affected user, and network address, and never contains a password.
- **FR-023**: The super user MUST be able to view the audit history, newest first, filtered by
  user and event kind. Records are kept for 12 months.

**Interface**

- **FR-024**: All interface text MUST be in Spanish; dates and numbers use the Spanish locale.
- **FR-025**: Every screen MUST be designed for phones first (usable from 320 px wide, without
  horizontal scrolling) and adapt to tablets and desktops; the administration list shows cards on
  phones and a table on wide screens.
- **FR-026**: The visual identity MUST use a blue palette with sufficient contrast, a clear visual
  hierarchy, and touch targets of at least 44 × 44 px.
- **FR-027**: The interface MUST work in the browsers listed in Clarifications (Chrome, Edge,
  Firefox, Safari: current and previous major; iOS Safari 14+; Android 8+ Chrome and Samsung
  Internet).
- **FR-028**: Screens MUST meet WCAG 2.2 level AA (as feature 001), including labelled fields,
  visible focus, messages announced to screen readers, and no information by colour alone.
- **FR-029**: Buttons that send a request MUST show a busy state and ignore repeated taps until the
  request finishes; network failures show a retry message.

**Product and deployment**

- **FR-030**: Product name, organisation name, logo, and public address MUST be set per
  deployment without code changes; no customer name may be hard-coded in the product.
- **FR-031**: The product's own data MUST live in the BI database (`DATABASE_URL_BI`), in the
  database's standard schema, created and upgraded by versioned, repeatable migrations that
  never modify or read any table that is not the product's own.
- **FR-032**: All traffic MUST pass through a single public entry point that serves the
  interface, forwards data requests to the service, and provides encrypted connections with
  automatically renewed certificates when a domain name is configured.

### Key Entities

- **User**: a person who can sign in. Email (unique, case-insensitive), full name, role
  (administrator or user), super-user flag, active/inactive, must-change-password flag, failed
  attempt count, locked-until time, last sign-in, created/updated times.
- **Session**: a signed-in device for a user; created time, last activity, device description.
  Ends by idle timeout, absolute timeout, sign-out, or administrative action.
- **Dashboard**: an entry in the product catalogue: code, name, description, icon, order, status
  (available, coming soon, hidden), address within the product.
- **Dashboard Access**: the grant of one dashboard to one regular user; who granted it and when.
- **Audit Event**: something that happened: time, kind, acting user, affected user, network
  address, and details without secrets.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person with valid credentials goes from opening the address to seeing the home page
  in under 30 seconds on a phone, and the home page appears within 2 seconds of sign-in on a 4G
  connection.
- **SC-002**: An administrator creates a new user and grants a dashboard in under 1 minute on a
  phone.
- **SC-003**: 100% of attempts to reach administration pages or non-granted dashboards by regular
  users are refused in automated tests covering every protected page and data request.
- **SC-004**: After 5 wrong passwords, 100% of further attempts within 15 minutes are refused.
- **SC-005**: Every screen is usable at 320 px and 375 px wide with no horizontal scrolling, and
  passes an automated WCAG 2.2 AA check with zero serious or critical findings.
- **SC-006**: The sign-in, home, profile, and user administration flows complete successfully in
  each browser listed in FR-027.
- **SC-007**: Setting up the product on a BI database with existing tables leaves those tables'
  structure and row counts unchanged, and running the setup twice produces no change and no
  error.
- **SC-008**: A second customer deployment is brought up with its own branding by changing
  configuration only, in under 30 minutes.
- **SC-009**: Every administrative action in FR-022 produces exactly one audit record with the
  acting and affected user.

## Assumptions

- This feature is the platform foundation that feature 001 (sales dashboard) builds on: 001's
  sign-in, sessions, lockout, and user-administration requirements are delivered here, and 001
  later adds customer accounts and links regular users to them.
- The BI database named in configuration is the database this product owns data in, and it is
  shared with existing BI tables that other processes maintain; the product never touches them.
- No email service is available yet; password recovery is done by an administrator reset
  (self-service recovery by email can be added later).
- Only email and password sign-in; single sign-on and two-factor authentication are out of scope
  for this release.
- One deployment per customer organisation (single organisation per deployment); roles are global
  within a deployment.
- Dashboards themselves (charts and data) are delivered by their own features; this feature only
  provides the catalogue, access control, and the home page.
- Folder layout, proxy technology, and hosting details are decided in the plan, following the
  project constitution and the user's stated preferences (a front-end, back-end, ETL and report
  split, and Caddy as the proxy).
