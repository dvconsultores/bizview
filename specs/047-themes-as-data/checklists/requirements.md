# Specification Quality Checklist: Themes as data, authored outside

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-31
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

- Validation pass 1: every item passes. Two deliberate checks: the requirements never name a file, a
  framework or a command (the brief's `theme.schema.json`, `bizview theme validate` and
  `layout.theme.id` appear in the plan, not here), and every success criterion is observable by a
  person or by a check without reading the code.
- **One recorded tension with the brief, resolved as an assumption**: the brief asks the built-in
  presets to become "themes in the same format" with a schema whose token names differ from what
  the product's own renderers already read (030's flat `series1..8` / `kpi_text` / `kpi_delta_bg`).
  The spec resolves it as a superset: the authored format is the published one, and the runtime
  tokens the screens and the PDF already consume are derived from it, so the built-ins' rendering
  and 030's gates stay intact. A reviewer should confirm that reading before the plan.
- Scope boundary: the site's marketing pages are out of scope; the theme reaches them only as the
  installation's chosen theme in the product.
