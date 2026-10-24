# Feature Specification: BizView connector for Claude (remote MCP server)

**Feature Branch**: `029-claude-connector`

**Created**: 2026-10-13

**Status**: Draft

**Input**: Owner, 2026-10-13: "a new feature in Claude and it is important to integrate it". BizView
exposes a remote MCP (Model Context Protocol) server so a user can add BizView as a **custom
connector** in Claude (web, desktop, mobile) with their own Claude account, sign in to BizView through
OAuth, and ask Claude about their sales. Claude can then answer, chart and build dashboards from live
BizView data. The direction is inverted compared with 014/015: BizView does not call an AI; Claude
calls BizView. BizView stays the data/ETL layer; Claude becomes a conversational reporting layer,
complementary to BizView's own dashboards and ReportLab PDFs.

**Out of scope**: signing BizView into Claude with a Claude subscription (BizView's own AI features
keep using API keys, 003/014/015); authoring integrations or reports from Claude (stays in the in-app
Asistente, 015); any access to origin databases.

**Constitution**: requires amendment 1.8.0 before planning (see "Constitution impact").

## Facts about Claude custom connectors this spec relies on

From Claude's help center (Oct 2026); re-verify at plan time:

- Remote connections are made from Anthropic's cloud, not from the user's device, so the MCP server
  must be reachable from the internet over HTTPS.
- Transports: Streamable HTTP (SSE also supported but expected to be deprecated).
- Auth: authless or OAuth. Claude supports Dynamic Client Registration (RFC 7591); a client ID/secret
  can also be entered under "Advanced settings". OAuth callback: `https://claude.ai/api/mcp/auth_callback`,
  possibly `https://claude.com/api/mcp/auth_callback` in the future; client name "Claude".
- A deleted DCR client is signalled with HTTP 401 `invalid_client` from the token endpoint, and Claude
  re-registers.
- Each user connects individually; on Team/Enterprise an Owner adds the connector first.
- "Interactive connectors" can render inline cards and fullscreen apps (e.g. dashboards) inside the
  conversation, using the permissions granted to the connector.
- Users approve tool calls, but Research mode may call tools without per-call approval, so every tool
  must be safe to run unattended (read-only).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Connect BizView to Claude (Priority: P1) 🎯

The super user enables "Conector para Claude" in Administración. BizView shows the connector URL
(`https://<installation>/mcp`) and short instructions. A user adds that URL as a custom connector in
Claude, presses "Connect", lands on BizView's sign-in page (same credentials and two-step sign-in as
the product), sees a consent screen listing what Claude will be able to do, accepts, and returns to
Claude connected.

**Why this priority**: without it nothing else works.

**Independent Test**: on a test installation behind HTTPS, add the URL in claude.ai, complete sign-in
and consent, and see BizView's tools listed in Claude; repeat with the MCP Inspector.

**Acceptance Scenarios**:

1. **Given** the connector is disabled (default), **When** anyone calls `/mcp` or the OAuth endpoints,
   **Then** they get 404, and the Administración screen explains how to enable it.
2. **Given** the installation runs the `private` security profile, **When** the super user tries to
   enable the connector, **Then** it is refused with the reason (Claude connects from the internet;
   the `internet` profile is required).
3. **Given** the connector is enabled, **When** Claude connects without a token, **Then** `/mcp` returns
   401 with `WWW-Authenticate: Bearer resource_metadata=…`, and Claude discovers the authorization
   server, registers (DCR), and starts the authorization-code flow with PKCE.
4. **Given** the consent screen, **When** the user accepts, **Then** Claude receives tokens limited to
   the scopes shown, and the connection appears in the user's Perfil → "Aplicaciones conectadas".
5. **Given** a user whose role is not allowed to use the connector, **When** they sign in, **Then**
   consent is refused with a clear message and no token is issued.

---

### User Story 2 - Ask Claude about my sales (Priority: P1)

Connected, the user asks Claude "¿cómo van las ventas por marca este mes comparado con el anterior?".
Claude lists the user's dashboards, reads the report's definition (metrics, dimensions, how each
number is computed, last refresh), queries the declared metrics with the needed dimensions and
period, and answers with figures and charts — the same figures the user sees in BizView.

**Independent Test**: for a seeded report, every figure returned by the tools equals the figure shown
by the BizView dashboard for the same filters and period.

**Acceptance Scenarios**:

1. **Given** a connected user, **When** Claude calls `list_dashboards`, **Then** it gets only the
   dashboards and reports that user can see in BizView, and only reports whose spec exposes them to
   the connector.
2. **Given** a report, **When** Claude calls `describe_report`, **Then** it gets metrics and dimensions
   with labels, plain-language definitions from the approved report spec, units/currency, allowed
   filters and periods, and the dataset's last successful refresh time.
3. **Given** a query with declared metrics, dimensions, filters and period, **When** Claude calls
   `query_report`, **Then** it gets aggregate rows from BizView's optimized models (never the origin),
   capped in size, plus totals and the refresh time.
4. **Given** an undeclared metric or dimension, free-form SQL, or a filter outside the report's
   allowed values, **When** Claude sends it, **Then** the tool returns a validation error listing what
   is allowed.
5. **Given** the dataset is stale (last refresh older than twice its schedule) or the last run failed,
   **Then** every result says so, so Claude can warn the user.

---

### User Story 3 - Get the official PDF from Claude (Priority: P2)

The user asks Claude for "el PDF del resumen de ventas de septiembre". Claude calls `export_report_pdf`
and gets a short-lived download link to the PDF generated by BizView with ReportLab.

**Acceptance Scenarios**:

1. **Given** a report the user can see, **When** `export_report_pdf` is called with filters and period,
   **Then** the backend renders the PDF (`backend/app/reports/`) and returns a single-use link valid
   for 10 minutes that does not require a BizView session.
2. **Given** the link was used once or expired, **When** it is opened again, **Then** it returns 410.

---

### User Story 4 - The BizView dashboard inside Claude (Priority: P3)

When the user asks to "ver el tablero", Claude shows BizView's dashboard as an interactive connector
component (inline card or fullscreen) with filters, using the same tools and permissions.

**Acceptance Scenarios**:

1. **Given** a client that supports interactive connectors, **When** `open_dashboard` is called,
   **Then** the BizView dashboard renders inside the conversation, mobile-first, and filter changes
   call `query_report` with the user's token.
2. **Given** a client without that support, **When** the tool is called, **Then** it returns the same
   data as structured content and text, plus a link to the dashboard in BizView.

---

### User Story 5 - Control and revoke (Priority: P2)

The super user sees every connected client and user, last use and call counts, and can revoke any
connection or disable the connector. Each user can revoke their own connections.

**Acceptance Scenarios**:

1. **Given** a revoked connection, **When** Claude calls a tool, **Then** it gets 401 within 1 minute of
   revocation and must reconnect.
2. **Given** the connector is disabled, **Then** all tokens stop working immediately and are deleted.
3. **Given** any tool call, **Then** an audit entry records user, client, tool, report id, row count,
   duration and outcome — never the returned values.

### Edge Cases

- A report is removed, or its exposure withdrawn, in a new workspace version: its tools return "no
  disponible" from the next call.
- A user loses access to a dashboard: the next call reflects it (permissions checked on every call,
  not at token issue).
- Personal-data dimensions (flagged in the dataset contract, 015 FR-007) are never queryable through
  the connector, even if the report shows them in BizView.
- Bursts of calls from Research mode: per-token and per-user rate limits; 429 with retry time.
- Prompt injection through data: labels and descriptions come from approved specs; free-text dimension
  values are length-capped and returned as data fields, never inside instruction-like text.
- One installation = one connector URL (constitution VII); no tenant switching inside a token.
- A DCR client deleted by the super user: the token endpoint answers 401 `invalid_client` so Claude
  re-registers.
- Access tokens are short-lived; refresh tokens rotate; reuse of a rotated refresh token revokes the
  whole grant.

## Requirements *(mandatory)*

### Server and transport
- **FR-001**: The backend MUST expose an MCP server at `/mcp` over Streamable HTTP, mounted in the
  FastAPI app and proxied by Caddy; it MUST be off by default and enabled only by the super user.
- **FR-002**: The connector MUST only be enabled with `SECURITY_PROFILE=internet` (HTTPS, throttling).

### Authorization (BizView is the OAuth 2.1 authorization server)
- **FR-003**: Publish authorization-server metadata (RFC 8414) and protected-resource metadata
  (RFC 9728); support Dynamic Client Registration (RFC 7591), authorization code with PKCE S256 only,
  refresh tokens with rotation, and tokens bound to the `/mcp` resource (RFC 8707).
- **FR-004**: Redirect URIs MUST be restricted to an allowlist, by default Claude's callbacks on
  claude.ai and claude.com; the super user can add others (e.g. a test client).
- **FR-005**: Sign-in uses BizView's existing authentication, including two-step sign-in where it
  applies. The consent screen (Spanish, mobile-first, no modals) lists the scopes:
  `reportes:leer` (dashboards, report definitions, queries) and `reportes:pdf` (PDF export).
- **FR-006**: Tokens and codes MUST be stored hashed; client secrets encrypted at rest and write-only;
  nothing token-like is logged.
- **FR-007**: Users can revoke their connections in Perfil; the super user can list and revoke any
  connection and delete registered clients.

### Tools (all read-only, annotated `readOnlyHint: true`, `destructiveHint: false`)
- **FR-008**: `list_dashboards()`, `describe_report(report_id)`, `query_report(report_id, metrics,
  dimensions, filters, period, compare_to?, sort?, limit≤500)`, `export_report_pdf(report_id, filters,
  period)`, and (P3) `open_dashboard(dashboard_id)` as an interactive component.
- **FR-009**: Tools MUST read only BizView's optimized models through the same report engine as the
  dashboard API (constitution II, III). No tool accepts SQL, connects to an origin, or changes the
  workspace, controls, users or settings.
- **FR-010**: Only reports whose approved spec declares a `connector` section are visible, and only the
  metrics and dimensions that section lists; personal-data dimensions are never exposed
  (constitution VIII, IX).
- **FR-011**: Permissions are evaluated on every call with the same rules as the BizView UI.
- **FR-012**: Results include units, currency, period, refresh time and stale/failed status, as
  structured content plus a short text summary for clients that only read text.

### Operation
- **FR-013**: Rate limits per token and per user; size caps per result.
- **FR-014**: Every tool call and every grant/revoke is audited (no returned values in the log).
- **FR-015**: Administración → "Conector para Claude": enable/disable, connector URL to copy,
  instructions for Pro/Max and Team/Enterprise plans, list of connections, usage.

## Success Criteria *(mandatory)*

- **SC-001**: A user adds the connector in claude.ai and makes the first successful query in under 3
  minutes, following the in-product instructions.
- **SC-002**: 100% of figures returned by `query_report` equal the BizView dashboard's figures for the
  same report, filters and period (automated comparison).
- **SC-003**: Connector calls open 0 origin connections (asserted in tests) and return 0 personal-data
  dimensions or undeclared metrics.
- **SC-004**: p95 tool latency under 500 ms on the optimized models (API target 200 ms plus MCP
  overhead); PDF export under 10 s.
- **SC-005**: A revoked connection or disabled connector fails the next call within 1 minute in 100% of
  tests.
- **SC-006**: The server passes the MCP Inspector checks and an e2e test with the official MCP Python
  client (DCR → PKCE → tools/list → tools/call → refresh → revoke).

## Constitution impact (amend to 1.8.0 before `/speckit-plan`)

- **V. Fixed Technology Stack**: add the official MCP Python SDK (server, Streamable HTTP) under
  Backend; the OAuth 2.1 authorization server is built with supporting libraries listed in the plan.
- **VIII. AI Is Optional and Private**: add that BizView MAY expose data to AI clients a user connects
  with their own account (connector) — off by default, read-only, aggregates from approved reports
  only, never origin records, credentials or personal-data dimensions. The "local model" guarantee
  does not apply to the connector, because the user chooses the AI client; the admin screen says so.
- **IX. Spec-Driven Reporting**: clarify that "no free-form AI entry point" also covers the connector:
  AI clients can only query reports whose approved spec exposes them, within the declared metrics and
  dimensions.
- **Constraints**: the connector requires `SECURITY_PROFILE=internet`; `/mcp` and the OAuth endpoints
  are JSON (the consent screen is served by the frontend, keeping "no HTML from the API").

## Assumptions

- Installations that want the connector have a public HTTPS hostname (Caddy automatic HTTPS).
- Users have a Claude plan that supports custom connectors.
- The report spec format (005/011) gains an optional `connector` section; reports without it stay
  invisible to Claude.
- Listing BizView in Claude's public connector directory is a later, separate decision (review
  criteria, privacy policy).
