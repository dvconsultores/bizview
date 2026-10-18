# Specification Quality Checklist: Interface in Spanish and English (i18n)

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-10-08
**Feature**: [spec.md](../spec.md)

## Content Quality
- [X] No implementation details (languages, frameworks, APIs) — accepted deviation: names the existing catalogue file, the preferences endpoint, ReportLab, `DEFAULT_LOCALE`, `BIZVIEW_LANG` and `<html lang>` to bind the behaviour to what exists (same practice as 006/018)
- [X] Focused on user value and business needs (mixed-language teams, per-user choice)
- [X] Written for non-technical stakeholders (stories and scenarios; FRs carry the technical bindings)
- [X] All mandatory sections completed

## Requirement Completeness
- [X] No [NEEDS CLARIFICATION] markers remain (defaults chosen: two languages only, `es` default, US English formatting, `es-ES` formatting kept for Spanish, no machine translation, optional `_en` labels for authored reports)
- [X] Requirements are testable and unambiguous — FR-001 (build fails), FR-010 (guard tests), FR-005 (envelope fields), FR-002 (resolution order)
- [X] Success criteria are measurable (SC-001 e2e walk with 0 foreign strings, SC-002 100 % parity, SC-003 < 300 ms with state kept, SC-004 0 Spanish fixed texts in English PDFs/emails)
- [X] Success criteria are technology-agnostic — SC-002 mentions unit tests as the measuring instrument only
- [X] All acceptance scenarios are defined (US1 AC1–4, US2 AC1–5, US3 AC1–3)
- [X] Edge cases are identified (authored content, shared links, missing key, RTL out of scope, screen readers)
- [X] Scope is clearly bounded (es/en only; authored content as written; RTL out)
- [X] Dependencies and assumptions identified (no i18n library, team-written English, supersedes 002 FR-024, constitution 2.0.0)

## Feature Readiness
- [X] All functional requirements have clear acceptance criteria (each FR maps to a scenario or SC; see tasks.md "per FR-…")
- [X] User scenarios cover primary flows (switch, server outputs, guards)
- [X] Feature meets measurable outcomes defined in Success Criteria
- [X] No implementation details leak into specification (see deviation above)

## Notes
- Spec corrected during planning (2026-10-08): US2 listed password-reset/temporary-password and
  alert emails, which the product does not send (temporary passwords are shown to the admin; no
  alert mail exists). The email list is now: dashboard send, scheduled subscription, mail test;
  Telegram bot messages added with their own resolution order (linked account → Telegram client
  language → `DEFAULT_LOCALE`).
- Spec corrected: `project.yaml` `language` (US2 AC4) belongs to feature 020, which lands after
  022; until then the agent writes specs in the session owner's language.
- Plan-level decisions not in the spec (recorded in plan.md): migration `0017_user_locale` also
  adds `integration_run.message_key/message_params` so fixed run messages are translated by code
  (US2 AC5); model-facing agent tool texts and JSON-schema descriptions stay single-language
  because they are not user-visible (plan D9); users with `locale = NULL` receive emails in
  `DEFAULT_LOCALE`.
