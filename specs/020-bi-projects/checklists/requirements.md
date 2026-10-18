# Specification Quality Checklist: BI projects — a workspace per chat with numbered specs

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-08
**Feature**: [spec.md](../spec.md)

## Content Quality

- [X] No implementation details (languages, frameworks, APIs) — accepted deviation, see Notes
- [X] Focused on user value and business needs
- [X] Written for non-technical stakeholders — accepted deviation, see Notes
- [X] All mandatory sections completed

## Requirement Completeness

- [X] No [NEEDS CLARIFICATION] markers remain
- [X] Requirements are testable and unambiguous — after the planning fixes listed in Notes
- [X] Success criteria are measurable
- [X] Success criteria are technology-agnostic (no implementation details) — accepted deviation, see Notes
- [X] All acceptance scenarios are defined — US6 has scenarios but no "Independent Test" line; its scenarios are independently testable (see tasks Phase 8 goal)
- [X] Edge cases are identified
- [X] Scope is clearly bounded
- [X] Dependencies and assumptions identified

## Feature Readiness

- [X] All functional requirements have clear acceptance criteria
- [X] User scenarios cover primary flows
- [X] Feature meets measurable outcomes defined in Success Criteria
- [X] No implementation details leak into specification — accepted deviation, see Notes

## Constitution alignment (2.0.0)

- [X] I Mobile first — US3 AC4, FR-010, SC-004 (375 px, tabs, axe)
- [X] IV Projects folder outside the repository — FR-002 (`PROJECTS_DIR`, installation `projects/`)
- [X] V Fixed stack — editor libraries are supporting libraries (plan, research R11); no Git binary
- [X] VII One product — generic names only; projects are installation data
- [X] VIII AI optional and private — fixed during planning: distributions name recipient roles,
  never people (US2 AC4); credentials never in project files (Assumptions); projects work with AI off
- [X] IX Numbered specs per project, kind line mandatory, "no spec, no run" unchanged — FR-004, FR-013

## Notes

- Like 014/016/017, the spec names paths, settings and tools (`PROJECTS_DIR`, `cli/`, CodeMirror,
  `edit_draft`) on purpose: they are fixed by the constitution (IV folders, V stack) and by the
  017 baseline the feature extends.
- Spec changes made during planning (minimal, recorded in plan.md "Spec changes"):
  1. US2 AC4 + Key Entities: distribution recipients by role only — "by user" would put people's
     names or emails into files the agent reads (constitution VIII).
  2. SC-005: "same checksum of artifacts" was unreachable because the import rewrites each
     artifact's `spec` path; now "same artifact definitions apart from the rewritten `spec` paths,
     and the same artifact files".
  3. US6 AC3 / FR-018: Spec Kit's scripts are produced by its own CLI (not in the image); the zip
     README documents the one-time `specify init --here`.
  4. FR-002: non-layout files in a Git checkout or an imported zip are ignored and listed (a Spec
     Kit project folder always contains `.specify/scripts`, `.claude/`, etc.).
- Kind line: the spec mandates `**Tipo**:`; the existing validator and golden examples use
  `**Spec type**: integration|report`. Not a spec change: the plan accepts both (and `**Type**:`)
  as aliases mapped to the Spanish canonical kind (research R7), so legacy specs keep validating.
- The edge case "last save wins" is implemented as an explicit choice: a stale editor save offers
  "Sobrescribir" (force), a stale agent `write` must re-read first (research R5); both revisions
  are always kept.
- Status "cambios sin aplicar" (FR-001) is derived from the active version, not stored, so
  rollback (005) never leaves a stale project status (plan §2, §7).
