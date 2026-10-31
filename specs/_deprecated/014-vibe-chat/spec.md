# Feature Specification: Vibe-reporting chat

**Feature Branch**: `014-vibe-chat`

**Created**: 2026-10-01

**Status**: Implemented (closed 2026-10-08, full suites green)

**Input**: Owner, 2026-10-01: "chat view to vibe report, store sessions in database". The super user
describes in a chat inside BizView what they need (which source, which tables, which report, how
often to update, how the dashboard looks); the AI drafts the integration and report specs and
artifacts; BizView validates them, shows a preview with real figures, and applies them as a new
workspace version after approval. Conversations are stored and can be resumed. Supersedes the
2026-09-29 decision "no in-app assistant" while keeping "no spec, no run".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Describe what I need and get a validated draft (Priority: P1)

The super user opens Administración → Asistente, starts a conversation ("Quiero ventas por marca
del ERP, actualizado cada 30 minutos, con ranking de marcas y tabla por producto"). The assistant
asks what it needs (source, tables, metrics' exact definitions), looks at the source's structure
(tables and columns, never row values), and produces a draft: the integration spec and files (SQL,
columns, keys, window, schedule, checks) and the report spec and definition (metrics, dimensions,
views, filters). BizView validates the draft with the same rules as the workspace and shows any
errors in the conversation, which the assistant fixes.

**Why this priority**: the core of the feature.

**Independent Test**: with a test source, ask for a simple sales report; the conversation ends with
a draft that passes validation, with spec, integration and report shown as readable cards.

**Acceptance Scenarios**:

1. **Given** the Asistente screen, **When** the super user writes a request, **Then** the assistant
   answers in Spanish, asks for missing decisions, and may consult the structure of the configured
   sources (shown in the conversation as "Consultó la estructura de «Origen ERP»").
2. **Given** the assistant has enough information, **When** it proposes a draft, **Then** the draft
   appears as cards (Spec de integración, Integración, Spec de reporte, Reporte) with their content
   readable and a validation status ("Válido" or the list of problems).
3. **Given** validation problems, **When** the assistant receives them, **Then** it corrects the draft
   and validation is re-run automatically, up to a bounded number of attempts; then it asks the user.
4. **Given** an existing integration, **When** the request only needs a new report on it, **Then** the
   draft reuses the integration (no duplicate) and only adds the report.

---

### User Story 2 - Preview with real figures, then apply (Priority: P1)

Before applying, the super user previews the report with real data: BizView runs the draft
integration on a short window into a temporary area and renders the draft report. If it looks right,
they approve with their password; BizView applies the draft as a new workspace version (validated
again), the integration starts on its schedule and the dashboard appears. Rollback stays available.

**Why this priority**: nothing reaches users without a human checking real numbers and approving.

**Independent Test**: preview a valid draft; check the figures against a direct query; apply; check
the dashboard appears and the workspace shows a new version; roll back.

**Acceptance Scenarios**:

1. **Given** a valid draft, **When** "Vista previa" is pressed, **Then** the draft integration runs on a
   short window (last 7 days or the spec's incremental window, whichever is shorter) into a temporary
   area, and the draft report is rendered like a normal report, marked "Vista previa".
2. **Given** the preview, **When** the super user presses "Aplicar", **Then** password confirmation is
   required (step-up view), the draft is validated again together with the active version, and a new
   active version is created; the previous one stays available for rollback.
3. **Given** the preview fails (query error, checks fail), **When** it finishes, **Then** the error is
   shown in the conversation and passed to the assistant (without row values) so it can fix the draft.
4. **Given** the AI provider is not configured, **When** the Asistente is opened, **Then** it explains how
   to configure it (as the AI administration screen does) and nothing else is possible.

---

### User Story 3 - Conversations are kept and can be resumed (Priority: P2)

Every conversation is stored: messages, drafts, validations, previews and the version applied. The
super user sees a list of conversations (title, date, status: En curso, Aplicada, Archivada), opens
one, continues it, or archives it.

**Independent Test**: start a conversation, leave, come back on another device, continue it; apply
it; see it marked "Aplicada" with a link to the version.

**Acceptance Scenarios**:

1. **Given** past conversations, **When** the Asistente opens, **Then** they are listed newest first with
   title, last activity and status.
2. **Given** a conversation, **When** it is reopened, **Then** all messages and the latest draft are shown,
   and the user can continue.
3. **Given** an applied conversation, **When** it is opened, **Then** it shows which workspace version it
   produced, and a new request in it creates a new draft based on the current active version.

### Edge Cases

- The assistant must never receive row values, credentials or connection details: only names of
  sources, table/column structure, validation messages, run status and row counts.
- The assistant cannot run SQL against sources, apply, or change controls by itself; only the super
  user's explicit actions (Vista previa, Aplicar) do.
- Two conversations try to apply at the same time: the second is validated against the new active
  version and may need re-validation (the user is told).
- Very long conversations: the AI receives a bounded history plus the current draft.
- Cost control: each conversation has a token budget; when exceeded the assistant says so.
- Preview data is removed after the conversation is applied/archived, or after 24 hours.
- The Git workspace remains supported; a version created from the chat can be downloaded as a
  workspace folder (zip) to commit elsewhere.

## Requirements *(mandatory)*

- **FR-001**: The Asistente MUST be available only to the super user and only when an AI provider is
  configured.
- **FR-002**: Conversations, messages, drafts, validations, previews and outcomes MUST be stored in the
  database and be resumable.
- **FR-003**: The assistant MAY consult source structure (as `bizview describe` does) and the active
  workspace's specs/definitions; it MUST NOT receive row values, credentials or connection details.
- **FR-004**: Drafts MUST consist of complete specs (spec, plan, tasks) and artifacts (integration and/or
  report files) following the workspace rules; they MUST be validated with the same validator as the
  workspace, including "no spec, no run".
- **FR-005**: Preview MUST run the draft on a bounded window into a temporary area, never touching
  published datasets, and render the draft report only for the super user.
- **FR-006**: Applying MUST require password confirmation, re-validate against the current active
  version, create a new workspace version (with spec texts stored, feature 011), audit the action,
  and keep rollback.
- **FR-007**: Every assistant action that consults a source or produces a draft MUST be visible in the
  conversation.
- **FR-008**: Each conversation MUST have a configurable token budget; usage is shown.
- **FR-009**: A version can be exported as a workspace folder (zip).
- **FR-010**: Spanish UI, feature-010 look, no modals, mobile-first, WCAG AA.

## Success Criteria *(mandatory)*

- **SC-001**: A super user without SQL knowledge obtains a validated, previewed and applied report on an
  existing source in under 15 minutes in a guided test.
- **SC-002**: 0 row values, credentials or connection strings appear in any request sent to the AI
  provider (verified by logging the outgoing payloads in tests).
- **SC-003**: 100% of applied chat versions pass the same validation as Git-applied versions.
- **SC-004**: Conversations survive restarts and are resumable on another device in 100% of tests.

## Assumptions

- The configured provider supports tool/function calling (Anthropic and OpenAI-compatible, incl.
  DeepSeek, do).
- Preview uses the BI database in a temporary schema per conversation.
- The chat produces the same file formats as the Git workspace, so both paths stay interchangeable.
