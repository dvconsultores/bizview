# {name} — Bizview Project Constitution (Vibe Reporting)

## Core Principles

### I. No Spec, No Run
Every source, integration, report and distribution of this project MUST be a Spec Kit feature in
`specs/NNN-<name>/` with `spec.md`, `plan.md`, `tasks.md` and a `**Tipo**:` line. Numbers are
consecutive and never reused. Its `**Status**` MUST be `Approved` before implementation and
`Implemented` after. The Bizview engine refuses anything else.

### II. One Integration, Many Reports
Integrations own the data (datasets from one source); reports only consume datasets. A new report
reuses existing integrations; a missing dataset means a new or amended integration spec first.

### III. Declarative Only
Artifacts are YAML plus read-only SQL or request definitions. No scripts, no code. SQL is one
SELECT/WITH per dataset, filtered by `:window_start`/`:window_end` for incremental loads.

### IV. No Secrets, No Rows
Credentials live only in the installation's encrypted catalogue; artifacts reference sources by
name. Never write passwords, tokens, or business data values into specs, artifacts, commits, or AI
prompts. Use `bizview describe` for structure.

### V. Exact Definitions
Every metric is defined exactly in its spec (what is summed, sign of returns, what counts as an
order) and implemented exactly as written. When the business changes a definition, the spec
changes first.

### VI. Recipients by Role
Distributions send reports only to roles (`admin`, `user`), never to email addresses.

### VII. Validated Before Applied
The project MUST validate with zero errors before it is applied; Git workspaces run
`bizview validate --write-lock` before a commit is pushed.

## Installation Rules

<!-- bizview:reglas-instalacion -->
These rules come from the Bizview installation; `/speckit-constitution` keeps this block unchanged.

- Credentials live only in the installation's encrypted catalogue; files name sources, never
  hosts, users, passwords or tokens.
- Sources are read-only: one SELECT/WITH per query, no writes to any origin.
- No row values or personal data in specs, artifacts, commits or prompts; structure only.
- The assistant works only on reports, integrations, ETL, data sources and the use of BizView.
- Applying a project is a human action with password confirmation; the assistant never applies.
<!-- /bizview:reglas-instalacion -->

## Governance

This constitution governs the project's specs. Amend it with `/speckit-constitution`.

**Version**: 2.0.0 | **Ratified**: {date}
