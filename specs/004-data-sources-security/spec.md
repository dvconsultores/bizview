# Feature Specification: Data Sources and Internet-Grade Security

**Feature Branch**: `004-data-sources-security`

**Created**: 2026-09-29

**Status**: Implemented

**Input**: User description: "The BI can have different source origins. Remove DATABASE_URL_ORIGIN
and use origin sources stored in the application, managed by the app admin, with encryption — the
values must be secure. Origin types for this version: 1. PostgreSQL, 2. SQL Server, 3. XML SOAP
(for SAP), 4. REST API including token, bearer, etc. Important: a security option, because the
customer can host the BI on the internet."

## Clarifications

### Session 2026-09-29 (second)

Answered by the user.

- Q: Is SQL Server in this version? → A: No. SQL Server is deferred to a later version; this MVP
  covers PostgreSQL, SOAP (SAP), and REST. The catalogue stays open to new types.
- Q: How does the security option treat HTTP? → A: An explicit installation option,
  `SECURITY_PROFILE`: **`private` allows plain HTTP** (for the product's own address and for
  sources); **`internet` requires HTTPS** everywhere (the product's address, cookies, and every
  source connection). The installer asks for it (or takes `--security-profile`); when left on
  `auto` it is `internet` for a domain and `private` otherwise.

### Session 2026-09-29

Answered autonomously with the recommended option, at the user's request.

- Q: Who manages data sources? → A: The super user only. Sources hold credentials to the
  customer's business systems; they are the most sensitive setting in the product. Regular
  administrators do not see or change them.
- Q: How are credentials protected? → A: Encrypted at rest with a secret key that lives only in the
  installation's settings (never in the database); write-only in the interface and API — once
  saved, a credential is never shown or returned again, only "configured / not configured".
- Q: What happens to `DATABASE_URL_ORIGIN`? → A: It is removed. If an installation still has it,
  the first start imports it once as a PostgreSQL source (encrypted) and asks the super user to
  delete the variable.
- Q: What does "security option for the internet" mean? → A: A security profile. `internet`
  (automatic when the installation has a public domain) enforces two-step sign-in for
  administrators, per-address sign-in limits, HTTPS, re-confirmation of the password for sensitive
  changes, and blocks sources from pointing at the server itself or cloud metadata addresses.
  `private` (on-premises, plain HTTP) keeps the same protections available but optional.
- Q: Which authentication methods per source type? → A: PostgreSQL: user and password with an
  encrypted connection (plain connections only in `private`). SOAP (SAP): basic authentication, WS-
  Security user token, or client certificate. REST: none, bearer token, basic, API key (header or
  query parameter), OAuth 2.0 client credentials, plus custom headers.
- Q: Does this feature extract data? → A: No. It delivers the source catalogue, secure storage, and
  connection testing. Extraction (feature 001's worker) reads its sources from this catalogue.

## User Scenarios & Testing *(mandatory)*

Actors: the **super user** (manages sources and security), **administrators** and **users**
(affected by the security profile), and the **implementer** (installs, holds the secret key).

### User Story 1 - Register a database source securely (Priority: P1)

The super user opens *Fuentes de datos*, adds a PostgreSQL source by entering its
address, database, user and password, and the encryption option, confirms their own password, and
tests the connection. The product reports success, the server version, and whether the account has
more rights than read-only access. From then on the password is never displayed again.

**Why this priority**: the sales dashboard and any future dashboard need their origin; today the
only way is a plain-text setting, which is unacceptable when the product faces the internet.

**Independent Test**: add a PostgreSQL source pointing at a real database, test it, reload the page
and the API — the password is nowhere in the responses; the database table holds only encrypted
bytes; the audit log shows who created and tested it.

**Acceptance Scenarios**:

1. **Given** the super user, **When** they save a PostgreSQL source with a password, **Then** the
   list shows it with "credencial configurada" and the password field is empty on edit.
2. **Given** a saved source, **When** anyone reads it through the interface or the API, **Then** no
   secret value is present; only which secret fields are configured.
3. **Given** a saved source, **When** the super user edits the address but leaves the password
   empty, **Then** the stored password is kept; **When** they type a new one, **Then** it replaces
   the old one.
4. **Given** a source whose account can write or is a database superuser, **When** it is tested,
   **Then** the result warns that a read-only account is required.
5. **Given** an administrator who is not the super user, **When** they try to open or call anything
   about sources, **Then** access is refused.

---

### User Story 2 - Register SOAP (SAP) and REST sources (Priority: P2)

The super user adds a SOAP source from its WSDL address with basic, WS-Security, or client-
certificate authentication, and the test lists the operations the service offers. They add a REST
source with a base address, an authentication method (bearer token, basic, API key in a header or
query parameter, or OAuth 2.0 client credentials) and optional headers, and the test calls a
chosen path and reports status and response time.

**Why this priority**: SAP and cloud systems expose data through web services, not SQL.

**Independent Test**: register a public SOAP service WSDL and a REST API requiring a bearer token;
tests succeed; a wrong token yields "credenciales rechazadas".

**Acceptance Scenarios**:

1. **Given** a SOAP source, **When** tested, **Then** the WSDL is loaded with the configured
   authentication and the available operations are listed.
2. **Given** a SOAP document that tries to read local files or external entities, **When** it is
   loaded, **Then** it is rejected.
3. **Given** a REST source with OAuth 2.0 client credentials, **When** tested, **Then** a token is
   obtained from the token address and used for the test call; the token itself is never shown.
4. **Given** a REST endpoint that redirects to another host, **When** tested, **Then** credentials
   are not forwarded to the other host.

---

### User Story 3 - Choose the security profile for an internet-facing installation (Priority: P3)

An installation published on a public domain runs with the `internet` profile: administrators must
set up two-step sign-in (an authenticator app code) before using administration; repeated failed
sign-ins from one address are slowed down; sensitive changes (sources, security, users' roles)
require re-entering the password; optionally administration is limited to listed network
addresses. The super user sees the active profile and its checks on a *Seguridad* page.

**Why this priority**: the same product must be safe on a public address, where attackers can reach
the sign-in page and try stolen passwords.

**Independent Test**: install with `--security-profile internet` and a domain; sign in as super
user; the product requires enrolling
two-step sign-in before anything else in administration; from one address, 20 wrong passwords
across different accounts are answered with "demasiados intentos"; the *Seguridad* page shows all
checks green.

**Acceptance Scenarios**:

1. **Given** the `internet` profile, **When** an administrator without two-step sign-in signs in,
   **Then** they must enroll (scan a code, confirm a 6-digit code, save recovery codes) before
   using any administration page.
2. **Given** two-step sign-in is enabled for a user, **When** they sign in, **Then** a correct
   password is not enough — a current authenticator code or an unused recovery code is required.
3. **Given** 20 failed sign-in attempts from one network address within 15 minutes, **When** another
   attempt comes from that address, **Then** it is refused for the rest of the window, regardless of
   the account.
4. **Given** the super user last confirmed their password more than 5 minutes ago, **When** they save
   or delete a source, **Then** the product asks for the password again first.
5. **Given** an allowed-address list for administration, **When** an administrator connects from
   another address, **Then** administration is refused while the rest of the product keeps working.
6. **Given** the `private` profile, **When** users sign in, **Then** two-step sign-in is optional
   (each user may enable it in their profile) and the same protections are available.
7. **Given** the `private` profile, **When** the super user saves a REST source with an `http://`
   address, **Then** it is accepted; **Given** the `internet` profile, **Then** it is refused with
   "se requiere HTTPS en el perfil internet".

---

### User Story 4 - Keep the secret key safe and rotate it (Priority: P4)

The implementer's installation has a secret key generated at install time. The product refuses to
start without a valid key when encrypted data exists, never stores the key in the database, and can
rotate to a new key re-encrypting all stored secrets. Losing the key means re-entering source
credentials, which the documentation states plainly.

**Why this priority**: encryption is only as strong as the key handling.

**Independent Test**: start without the key while sources exist → clear refusal; rotate the key →
all sources still test successfully; the old key no longer decrypts.

**Acceptance Scenarios**:

1. **Given** encrypted secrets exist, **When** the product starts without a key or with a wrong key,
   **Then** it refuses to start and says which setting is wrong, without revealing anything else.
2. **Given** a new key and the old key configured, **When** the rotation command runs, **Then** every
   stored secret is re-encrypted with the new key in one transaction and the old key can be removed.
3. **Given** a copy of the database without the settings file, **When** someone reads the sources
   table, **Then** no credential can be recovered from it.

---

### User Story 5 - Move from the old origin setting (Priority: P5)

An installation that still has `DATABASE_URL_ORIGIN` starts; the product imports it once as a
PostgreSQL source named "Origen (importado)", encrypted, audits it, and shows the super user a
notice to delete the variable.

**Independent Test**: start with the variable set and no sources → one source exists with the same
host/database/user, the password encrypted; restart → no duplicate.

**Acceptance Scenarios**:

1. **Given** the variable and no sources, **When** the product starts, **Then** exactly one source is
   created and the super user sees a notice.
2. **Given** the variable and existing sources, **When** the product starts, **Then** nothing is
   imported and a warning is logged.

---

### Edge Cases

- Source name duplicated → refused ("ya existe una fuente con ese nombre").
- Source host resolves to the server itself, a link-local or cloud metadata address → refused in
  every profile; private network addresses → allowed unless the installation disables them.
- A name that resolves to an allowed address when saved and a blocked one when connecting (DNS
  rebinding) → checked again at every connection.
- Connection test hangs → stops at the source's timeout (default 15 s, max 60 s).
- Very large REST/SOAP responses during a test → read at most 1 MB.
- Certificates: invalid TLS certificate → failure "certificado no válido" unless the source
  explicitly allows it (not allowed in the `internet` profile).
- Deleting a source used by a dashboard (future) → refused while in use; disabling is allowed.
- Lost authenticator device → recovery codes; lost recovery codes → the super user resets the
  user's two-step sign-in; the super user's own reset uses a server command.
- Clock drift on the authenticator → codes from one period before/after are accepted.
- Reused authenticator code within its period → refused.

## Requirements *(mandatory)*

### Functional Requirements

**Data sources**

- **FR-001**: The product MUST keep a catalogue of data sources with: name (unique), type
  (`postgresql`, `soap`, `rest` in this version; new types can be added later, starting with SQL
  Server), description, enabled flag, type-specific settings,
  type-specific credentials, and the result of the last test.
- **FR-002**: Only the super user MAY list, create, edit, enable/disable, test, or delete sources.
- **FR-003**: Settings per type:
  - PostgreSQL: host, port (5432), database, user, password, TLS mode (`require` default;
    `verify-full` with an optional CA certificate; `prefer` and `disable` only in the `private`
    profile), timeout.
  - SOAP: WSDL address (`http://` only in `private`, `https://` in both), optional service/port,
    authentication (`basic`, `wsse_username_token`, `client_certificate`), optional CA
    certificate, timeout.
  - REST: base address (`http://` only in `private`, `https://` in both), test path,
    authentication (`none`,
    `bearer`, `basic`, `api_key_header`, `api_key_query`, `oauth2_client_credentials` with token
    address, client id, client secret, scope), custom headers (values may be secret), optional CA
    certificate, timeout.
- **FR-004**: Credentials (passwords, tokens, API keys, client secrets, private keys, secret header
  values) MUST be write-only: never returned by any API, never shown, never logged or written to
  the audit log. Responses list only which secret fields are configured.
- **FR-005**: On edit, an omitted secret field keeps its stored value; an explicit "clear" removes
  it; a new value replaces it.
- **FR-006**: A connection test MUST report success or a named reason (`unreachable`, `timeout`,
  `tls_error`, `auth_failed`, `not_found`, `blocked_address`, `not_allowed_in_profile`,
  `invalid_response`,
  `permission_warning`, `error`), response time, and type-specific details (server version;
  SOAP operations; REST status code). Database tests MUST warn when the account is not read-only.
- **FR-007**: Tests and future extraction MUST connect to databases in read-only mode where the
  engine supports it.
- **FR-008**: Destination addresses MUST be checked at every connection: loopback, link-local,
  cloud metadata, and unspecified addresses are always refused; private-network addresses are
  refused when the installation disables them.
- **FR-009**: SOAP/XML processing MUST refuse document type declarations, external entities, and
  external references.
- **FR-010**: HTTP clients (SOAP, REST, OAuth) MUST verify TLS certificates, cap response size at
  1 MB for tests, and never forward credentials across a redirect to another host.
- **FR-011**: Deleting a source MUST require confirmation; a source referenced by a dashboard
  dataset MUST NOT be deletable (only disabled).
- **FR-012**: `DATABASE_URL_ORIGIN` MUST no longer be used; on start it MUST be imported once as an
  encrypted PostgreSQL source when no sources exist, audited, and flagged to the super user.

**Encryption and key**

- **FR-013**: Credentials MUST be encrypted at rest with authenticated encryption using a 256-bit
  key held only in the installation settings (`BIZVIEW_SECRET_KEY`); each value MUST be bound to its
  source and field so encrypted values cannot be swapped between sources.
- **FR-014**: The installer MUST generate the key; the product MUST refuse to start when encrypted
  data exists and the key is missing or wrong.
- **FR-015**: A command MUST rotate the key (old key accepted for reading during rotation) and
  re-encrypt every stored secret atomically.

**Security profile**

- **FR-016**: The installation MUST have an explicit security option `SECURITY_PROFILE` with values
  `private`, `internet`, or `auto` (`internet` when the public address is a domain, `private`
  otherwise). The installer MUST ask for it or accept `--security-profile`. It is an installation
  setting — not changeable from the interface — and MUST be visible to the super user.
- **FR-017**: The profile MUST govern HTTP versus HTTPS as follows:

  | | `private` | `internet` |
  |---|---|---|
  | Product address | HTTP allowed (HTTPS optional) | HTTPS required; the product refuses to start without a domain and secure cookies |
  | Session cookies | `Secure` optional | `Secure` required |
  | SOAP / REST / OAuth token addresses | `http://` or `https://` | `https://` only |
  | PostgreSQL connection | encrypted by default; plain (`disable`, `prefer`) allowed | encrypted and verified certificate policy (`require`, `verify-full`) only |
  | Two-step sign-in for administrators | optional | mandatory |

  A source saved as `http://` or with a plain connection MUST be refused by validation and by the
  connection test if the installation later switches to `internet`, with the reason
  `not_allowed_in_profile`, until it is edited.
- **FR-018**: Two-step sign-in (time-based one-time codes, RFC 6238) MUST be available to every
  user: enrollment with a scannable code and a manual key, confirmation with a valid code, 10
  single-use recovery codes shown once and stored hashed, codes accepted within ±1 period, a code
  never accepted twice, and disabling requires the password and a code.
- **FR-019**: The super user MUST be able to reset another user's two-step sign-in (audited); a
  server command MUST reset the super user's.
- **FR-020**: Sign-in attempts MUST be limited per network address (default 20 failures per 15
  minutes, in both profiles) in addition to the per-account lockout, and answered with a generic
  "demasiados intentos" message.
- **FR-021**: Sensitive actions — creating, editing, deleting, or testing sources; changing roles;
  resetting another user's two-step sign-in; changing one's own two-step sign-in — MUST require the
  password to have been confirmed within the last 5 minutes.
- **FR-022**: An optional list of allowed network ranges MUST restrict administration pages and API
  to those ranges.
- **FR-023**: The client address used for limits, allow-lists, and the audit log MUST come only
  from the product's own proxy, never from headers a client can set.
- **FR-024**: Every source and security action MUST be audited: source created/updated/deleted/
  tested/enabled/disabled/imported, two-step sign-in enabled/disabled/reset, recovery code used,
  password re-confirmed, address rate-limited, administration refused by address.
- **FR-025**: The *Seguridad* page MUST show the profile and a checklist: HTTPS, secure cookies,
  secret key present, two-step sign-in coverage of administrators, address allow-list, private
  networks allowed for sources, and the key's last rotation date.

### Key Entities

- **Data Source**: name, type, description, enabled, settings (non-secret), encrypted credentials,
  which secret fields are set, last test (time, outcome, details), created/updated by.
- **Secret Key**: 256-bit key identified by a short id; current and (during rotation) previous.
- **Two-step Sign-in**: per user — encrypted shared secret, enabled time, last used period,
  hashed recovery codes.
- **Sign-in Throttle**: failures per network address per time window.
- **Security Profile**: `internet` or `private`, and the derived enforcement.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No credential of any source can be read from the database, API responses, logs, audit
  records, or the interface — verified by searching all of them for the test credentials.
- **SC-002**: The super user registers and tests a source of each type in under 5 minutes each.
- **SC-008**: Under `internet`, 0 connections leave the product unencrypted (sources over `http://`
  or plain PostgreSQL are refused in 100% of attempts); under `private` they work.
- **SC-003**: A connection test returns a result within the source timeout plus 2 seconds in 100%
  of runs.
- **SC-004**: With the `internet` profile, 100% of administrator sign-ins require a second factor.
- **SC-005**: Automated credential stuffing (many accounts, one address) is stopped after at most
  20 failed attempts per 15 minutes.
- **SC-006**: Key rotation completes for 1,000 sources in under 1 minute with zero failed decryptions.
- **SC-007**: Sources pointing at the server itself or cloud metadata addresses are refused in
  100% of attempts, including through name resolution tricks.

## Assumptions

- This version covers exactly three origin types: PostgreSQL, SOAP (SAP and similar), and REST
  (JSON). SQL Server is deferred to a later version (driver choice recorded in research R2).
- Extraction pipelines (feature 001) will read sources from this catalogue and add dataset
  definitions (query or endpoint per dashboard); this feature does not extract data.
- The secret key is backed up by the implementer separately from database backups; losing it
  requires re-entering credentials and re-enrolling two-step sign-in.
- Customers hosting on the internet use a domain name so HTTPS certificates can be issued.
- Authenticator apps (Google Authenticator, Microsoft Authenticator, 1Password, etc.) are available
  to administrators.
