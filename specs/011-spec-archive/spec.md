# Feature Specification: Spec archive in the installation

**Feature Branch**: `011-spec-archive`

**Created**: 2026-10-01

**Status**: Implemented (closed 2026-10-08, full suites green)

**Input**: Owner, 2026-10-01: store the full text of each integration/report spec in the database
when a workspace version is applied (today only folder, status, title and fingerprint are kept),
so it can be read from the administration screen without the Git repository.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Read the spec behind what is running (Priority: P1)

The super user opens **Administración → Espacio de trabajo** and sees, for the active version, the
list of specs (integrations and reports) with title and status. Choosing one shows its spec, plan
and tasks exactly as they were when the version was applied.

**Why this priority**: it is the whole feature: know what was asked and approved for each running
integration and report, from the installation itself.

**Independent Test**: apply a workspace, open Espacio de trabajo, open a report's spec and compare
its text with `spec.md` in the workspace; edit the file afterwards and confirm the installation
still shows the applied text.

**Acceptance Scenarios**:

1. **Given** an applied version, **When** the super user opens Espacio de trabajo, **Then** every
   integration and report of that version is listed with its title, type and status.
2. **Given** the list, **When** they open one, **Then** a view (no modal) shows the applied
   `spec.md`, `plan.md` and `tasks.md`, one after another or selectable, as plain readable text.
3. **Given** the workspace files changed after applying, **When** they read the spec in the
   installation, **Then** they see the text as applied, not the current files.
4. **Given** a version applied before this feature, **When** they open a spec, **Then** they see its
   title, status and fingerprint and the message "Texto no disponible para esta versión".
5. **Given** a rollback to the previous version, **When** they open Espacio de trabajo, **Then** the
   specs shown are those of the now-active version.

### Edge Cases

- A spec folder has an extra file (e.g. notes): only `spec.md`, `plan.md`, `tasks.md` are stored.
- Very long specs: shown fully, scrollable, readable at 375 px (no horizontal page scroll; long
  lines wrap).
- Non-UTF-8 content cannot happen (validation already reads the files as text); if a file cannot be
  decoded, apply fails with today's validation error style.

## Requirements *(mandatory)*

- **FR-001**: Applying a workspace version MUST store, per integration and report, the full text of
  its `spec.md`, `plan.md` and `tasks.md` with that version, consistent with the fingerprints in
  the lock.
- **FR-002**: Only the super user MAY read stored spec texts (same access as Espacio de trabajo).
- **FR-003**: Espacio de trabajo MUST list the active version's specs and show any of them in a view
  (feature 009), with a back action; texts are shown as written (no execution of their content).
- **FR-004**: Versions without stored texts MUST still list their specs with the "Texto no
  disponible para esta versión" message.
- **FR-005**: Texts MUST be in Spanish in the UI; content is shown as stored.
- **FR-006**: No migration of the table structure beyond what the stored text needs; existing rows
  remain valid.

## Success Criteria *(mandatory)*

- **SC-001**: For 100% of specs in an applied version, the text shown equals the applied file byte
  for byte (its SHA-256 matches the lock).
- **SC-002**: A spec opens in under 1 second.
- **SC-003**: Non-super users get "no autorizado" for 100% of spec text requests.

## Assumptions

- Spec files contain no secrets (workspace rule); storing them in the BI database is acceptable.
- Rendering Markdown as formatted text is not required; readable plain text with wrapping is enough.
