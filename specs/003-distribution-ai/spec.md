# Feature Specification: Distribution & AI — one open-source product, installed per customer

**Feature Branch**: `003-distribution-ai`

**Created**: 2026-09-29

**Status**: Implemented (closed 2026-10-08, full suites green)

**Input**: User description: "Remove the customer name. How can this be a general project to install
on every customer — a folder per customer? It will be installed on each customer, it is AI powered,
and it is open source. Proceed with the recommended option (one open-source product, one
installation folder per customer, versioned images, AGPL-3.0, configurable AI provider)."

## Clarifications

### Session 2026-09-29

Answered autonomously with the recommended option, at the user's request ("proceed").

- Q: Is there a code folder per customer? → A: No. One open-source product; each customer gets an
  *installation* (a folder of settings on their server). A folder per customer exists only in an
  optional private operations repository that holds configuration, never code.
- Q: Which license? → A: AGPL-3.0-or-later (network use counts as distribution; hosted forks must
  share their changes). The product name "Bizview" is not granted by the license.
- Q: Which AI providers? → A: Claude (Anthropic) by default, or any OpenAI-compatible endpoint
  (including local models such as Ollama) for customers who cannot send data outside; AI can be
  switched off and is off until configured.
- Q: What data may reach an AI provider? → A: Only aggregated figures and metadata the product
  itself composes — never raw source records, passwords, or personal data of users.
- Q: How are customers upgraded? → A: By changing the product version in their installation and
  restarting; database migrations run automatically.

## User Scenarios & Testing *(mandatory)*

Actors: the **implementer** (installs and upgrades the product at a customer), the **super user**
of an installation, **contributors** to the open-source project, and the **maintainer** who
publishes releases.

### User Story 1 - Install the product for a new customer (Priority: P1)

An implementer runs one installer on a customer's server. It asks for (or accepts as options) the
database connection, the super-user email, the public address, and the product version; it
creates the installation folder with the settings, a generated super-user password shown once,
and a place for the customer's logo. Starting it brings the product up at the given address.

**Why this priority**: installing at many customers is the business model; without a repeatable
installation there is no product.

**Independent Test**: on a clean Linux server with Docker, run the installer non-interactively
with a database URL, email, and address; start the installation; sign in as the super user with
the printed password.

**Acceptance Scenarios**:

1. **Given** a server with Docker, **When** the installer runs with the required answers, **Then**
   an installation folder exists containing the settings file (readable only by its owner), the
   service definition pinned to one product version, and empty `branding/` and `queries/` folders.
2. **Given** an installation folder, **When** it is started, **Then** the database is migrated, the
   super user is created, and the sign-in page is served at the configured address (with HTTPS
   when the address is a domain).
3. **Given** the installer is run on a folder that already has settings, **When** it runs again,
   **Then** it refuses to overwrite them unless explicitly told to.
4. **Given** Docker or Docker Compose is missing, **When** the installer runs, **Then** it stops
   with a clear message and changes nothing.

---

### User Story 2 - Brand and configure each customer without code changes (Priority: P2)

The implementer sets the product name shown to users, the organisation name, the logo, the
public address, and the AI settings only by editing the installation's settings and branding
folder. No customer name appears anywhere in the product's source.

**Why this priority**: one codebase for every customer is only possible if every difference is
configuration.

**Independent Test**: two installation folders with different settings, same product version,
show different names and logos.

**Acceptance Scenarios**:

1. **Given** an installation, **When** the organisation name is empty, **Then** only the product
   name is shown (no placeholder customer name).
2. **Given** a logo file in the branding folder and its path in the settings, **When** the product
   restarts, **Then** the logo appears on sign-in and in the header.
3. **Given** the public source repository, **When** it is searched for customer names or
   credentials, **Then** none are found.

---

### User Story 3 - Configure and verify the AI provider (Priority: P3)

The super user opens *Inteligencia artificial* and sees whether AI is enabled, which provider and
model are configured, and whether a key is set (never the key itself). A *Probar conexión* action
sends a tiny test request and reports success with response time, or a clear reason for failure
(invalid key, model not found, provider unreachable, rate limited, refused).

**Why this priority**: "AI powered" features (later specs) need a working provider per customer;
implementers need to verify it at install time without reading logs.

**Independent Test**: configure a provider with a wrong key, run the test, see "clave inválida";
configure it correctly, run it again, see success and latency; switch AI off, see it disabled for
everyone.

**Acceptance Scenarios**:

1. **Given** no AI settings, **When** the product starts, **Then** AI is off, the product works
   fully, and the AI page says how to enable it.
2. **Given** a configured provider, **When** the super user runs the test, **Then** the result shows
   provider, model, success/failure, and response time; the key never appears in the page, the API,
   or the logs.
3. **Given** an administrator who is not the super user, **When** they try to open the AI page or
   its API, **Then** access is refused.
4. **Given** a provider that is unreachable, **When** the test runs, **Then** it fails within the
   configured timeout with a "no se pudo conectar" reason.

---

### User Story 4 - Publish a release that every customer can install (Priority: P4)

The maintainer tags a version. Automated checks run, and the product images for that version are
published for both common server architectures, together with the installer. The release notes
describe changes.

**Why this priority**: installations pull published versions; without releases there is nothing
to install or upgrade to.

**Independent Test**: tag a version in the repository; the pipeline publishes images tagged with
that version; an installation pinned to it starts.

**Acceptance Scenarios**:

1. **Given** a version tag, **When** the release pipeline runs, **Then** backend and web images
   tagged with that version (and `latest`) are published and a release with the installer is
   created.
2. **Given** any change proposed to the repository, **When** checks run, **Then** type checks,
   unit tests, the browser-compatibility check, and the build must pass.
3. **Given** a running installation, **When** its version is changed and it is restarted, **Then**
   it runs the new version and migrates the database automatically.

---

### User Story 5 - Contribute to the open-source project (Priority: P5)

A developer finds the license, how to run the project locally, how to run tests, how to propose
changes, and how to report security issues privately. Every user of an installation can reach
the source code from the interface, as the license requires.

**Why this priority**: open source only works when people can contribute and when license
obligations are met.

**Independent Test**: a new contributor follows the contributing guide from a fresh clone to a
passing test run and a running local copy.

**Acceptance Scenarios**:

1. **Given** the repository, **When** a visitor opens it, **Then** it has the license, a README with
   install and development instructions, a contributing guide, a code of conduct, a security
   policy, and issue/PR templates.
2. **Given** any signed-in user, **When** they look at the footer or their profile, **Then** they see
   the product version and a link to its source code and license.

---

### Edge Cases

- AI provider set but key missing → AI reported as "no configurado", not "activo"; test explains.
- Model name wrong → test reports "modelo no encontrado".
- Provider returns a refusal → reported as such, not as a crash.
- Very slow provider → test stops at the timeout (default 30 s) and reports it.
- Installer run as a user without Docker permission → clear message.
- Installation version older than the database (downgrade) → refused by migrations; documented as
  unsupported (restore a backup instead).
- A contributor's pull request cannot access maintainer secrets → checks that need a database run
  only when a database is configured for the pipeline; the rest always run.

## Requirements *(mandatory)*

### Functional Requirements

**Product neutrality**

- **FR-001**: The source MUST NOT contain any customer name, customer logo, database address, or
  credential. Everything customer-specific MUST come from the installation's settings or branding
  folder.
- **FR-002**: When no organisation name is configured, the interface MUST show only the product
  name.

**Installation**

- **FR-003**: An installer MUST create an installation folder containing: the settings file
  (owner-only permissions), the service definition pinned to a product version, a `branding/`
  folder, and a `queries/` folder reserved for source-database queries.
- **FR-004**: The installer MUST accept all answers as command-line options (unattended use) and
  otherwise ask for them interactively; it MUST generate a strong super-user password when none is
  given and show it once.
- **FR-005**: The installer MUST refuse to overwrite existing settings unless forced, and MUST check
  that Docker and Docker Compose are available before changing anything.
- **FR-006**: An installation MUST run from published images only (no build on the customer's
  server) and MUST be upgradable by changing its version and restarting.
- **FR-007**: The product MUST report its version in the health check, the public configuration,
  and the interface.

**AI**

- **FR-008**: AI MUST be optional and off by default; the product MUST work fully without it.
- **FR-009**: Supported providers: Claude (Anthropic), and any OpenAI-compatible endpoint (e.g.
  local models). Provider, model, key, endpoint address, and timeout MUST be settings.
- **FR-010**: The AI key MUST never be returned by any API, shown in the interface, or written to
  logs or audit records.
- **FR-011**: Only the super user MAY view AI status and run the connection test.
- **FR-012**: The connection test MUST report provider, model, success, response time, and on
  failure one of: `invalid_key`, `forbidden`, `model_not_found`, `rate_limited`, `unreachable`,
  `timeout`, `refused`, `provider_error`, `not_configured`.
- **FR-013**: Data sent to an AI provider MUST be limited to what the product composes for the
  request (aggregates and metadata); no raw source rows and no user credentials or personal data.
  Each future AI feature MUST state what it sends.

**Open source**

- **FR-014**: The repository MUST be licensed AGPL-3.0-or-later, with the full license text,
  license metadata in each package, a contributing guide, code of conduct, security policy, and
  issue/PR templates.
- **FR-015**: Every page of the application MUST offer a link to the corresponding source code
  (configurable address) and name the license, satisfying the license's network-use clause.

**Releases**

- **FR-016**: Every proposed change MUST pass automated checks: backend lint, frontend type check,
  unit tests, build, and browser-compatibility check; database tests MUST run when a database is
  configured for the pipeline.
- **FR-017**: A version tag MUST publish backend and web images for amd64 and arm64 tagged with the
  version and `latest`, and a release containing the installer and installation template.

### Key Entities

- **Installation**: one customer deployment — settings, branding, queries, pinned version.
- **Release**: a published version — images + installer + notes.
- **AI provider configuration**: provider, model, endpoint, key presence, timeout, enabled state.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new customer installation, from a server with Docker to a working sign-in, takes
  under 10 minutes following the documentation.
- **SC-002**: Two customers on the same version differ only in their installation folders — zero
  source changes per customer.
- **SC-003**: Upgrading an installation to a new version takes one settings change and one restart,
  with no manual database steps.
- **SC-004**: The AI connection test returns a result (success or a named reason) within the
  configured timeout plus 2 seconds in 100% of runs.
- **SC-005**: A search of the repository finds zero customer names or credentials.
- **SC-006**: A new contributor reaches a running local copy and a passing test run in under 30
  minutes using only the contributing guide.

## Assumptions

- Customers' servers run Linux with Docker Engine and Compose v2; the database is always external
  (constitution).
- Images are published to GitHub Container Registry under the project's organisation; until the
  public repository exists, its address is a placeholder set in one place.
- The AI features that use the provider (summaries, questions about sales) come in later specs; this
  feature delivers the provider layer, settings, and verification.
- Default Claude model is `claude-opus-5-5` (current default recommended by Anthropic); customers may
  choose another model in settings.
- Backups of the customer database are the customer's responsibility and are documented, not
  automated, in this feature.
