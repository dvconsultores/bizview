# Specification Quality Checklist: Spec Kit commands in the chat and BI-only scope

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
- [X] Requirements are testable and unambiguous — after the 2026-10-08 fixes, see Notes
- [X] Success criteria are measurable
- [X] Success criteria are technology-agnostic (no implementation details) — accepted deviation, see Notes
- [X] All acceptance scenarios are defined
- [X] Edge cases are identified
- [X] Scope is clearly bounded (nine commands + `/ayuda`; `/speckit-taskstoissues` excluded)
- [X] Dependencies and assumptions identified (017, 020, 022, 023; constitution 2.0.0 IX)

## Feature Readiness

- [X] All functional requirements have clear acceptance criteria
- [X] User scenarios cover primary flows
- [X] Feature meets measurable outcomes defined in Success Criteria
- [X] No implementation details leak into specification — accepted deviation, see Notes

## Notes

- The spec names tools (`edit_draft`, `check_query`, …), paths and `AI_LIVE_TESTS` on purpose: the
  feature constrains the existing 017 agent tools and the Spec Kit file layout of 020, and the owner
  asked for the Spec Kit commands by name. Same practice as 014/017.
- Fixes made while planning (spec vs code, 2026-10-08):
  - FR-004 omitted existing tools: `propose_draft` (a file writer, now gated like `edit_draft`),
    `get_workspace` (inspection) and `update_notes` (working notes, not files).
  - FR-003 let no command write the `**Status**:` line, but the validator
    (`cli/bizview_cli/validate.py`, `spec_not_approved`) requires Approved/Implemented; implement may
    now change only that line (approved after the user confirms in the chat, implemented at the end).
    Clarify may toggle checkboxes of `checklists/requirements.md`, as the Spec Kit clarify step does.
  - Edge case "implement without tasks" said the agent runs the missing steps, which contradicted
    FR-003 (implement cannot write plan/tasks); it now stops and names the command to run first.
- SC-003 needs a live provider and is opt-in only (`AI_LIVE_TESTS=1`); default CI runs the
  deterministic pre-check fixture test and the fake provider.
- SC-005 is a usability check (plan.md, Quickstart), not an automated test.
- Items marked incomplete would require spec updates before `/speckit-clarify` or `/speckit-plan`;
  none remain.
