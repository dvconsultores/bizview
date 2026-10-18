# Specification Quality Checklist: Direct-source reports (no ETL)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-08
**Feature**: [spec.md](../spec.md)

## Content Quality
- [X] No implementation details (languages, frameworks, APIs) — accepted deviation: names the
  artifact keys (`report.yaml`, `direct`, `uses`), the read-only session (`BEGIN READ ONLY`,
  `statement_timeout`) and installation settings, because constitution 2.0.0 principle II binds the
  exception to exactly these guarantees and the report artifact is the user-facing contract
- [X] Focused on user value and business needs (owner case: existing BI table → dashboard without ETL)
- [X] Written for non-technical stakeholders (stories and acceptance scenarios in product terms;
  technical terms confined to FR Safety)
- [X] All mandatory sections completed

## Requirement Completeness
- [X] No [NEEDS CLARIFICATION] markers remain (defaults chosen: cache 300 s, timeout 15 s, table
  rows 500, concurrency 2 per source, stale ≤ 24 h, warn above 5 M rows, PostgreSQL family only,
  `bi` enabled by default, catalogue flag off by default)
- [X] Requirements are testable and unambiguous (FR-003 clarified 2026-10-08: the five spec lines
  are named and each missing line fails validation)
- [X] Success criteria are measurable (SC-001 e2e, SC-002 p95/timeout on 1 M rows, SC-003 zero
  writes / zero product tables, SC-004 100 % stale + timeout + 1 s, SC-005 byte-identical)
- [X] Success criteria are technology-agnostic — accepted deviation: SC-003 refers to the product
  schema metadata to define "every product table" precisely
- [X] All acceptance scenarios are defined (US1 4, US2 4, US3 4)
- [X] Edge cases are identified (mixed dashboards, materialize, personal data, large tables,
  structure drift, concurrency, sharing/email, internet profile, reserved name `bi` — added
  2026-10-08)
- [X] Scope is clearly bounded (one data path per report; PostgreSQL family only; no Supabase REST,
  SOAP or REST)
- [X] Dependencies and assumptions identified (005, 004, 017, 015, 018; existing report cache)

## Feature Readiness
- [X] All functional requirements have clear acceptance criteria (FR-001…FR-015 mapped to stories,
  edge cases or success criteria; FR-015 storage made explicit as the "Direct read log entry"
  key entity — added 2026-10-08)
- [X] User scenarios cover primary flows (BI table, catalogue source, agent/CLI authoring)
- [X] Feature meets measurable outcomes defined in Success Criteria
- [X] No implementation details leak into specification (see deviations above)

## Notes
- Spec edits made during planning (2026-10-08): FR-003 names the five required lines; Edge case
  for a catalogue source named `bi`; Key entity "Direct read log entry".
