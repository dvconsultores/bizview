# Specification Quality Checklist: The agent explains the app, Spec Kit and projects

**Purpose**: Validate specification completeness and quality before proceeding to implementation

**Created**: 2026-10-08

**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md) · [tasks.md](../tasks.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
  - The spec names only product concepts and two tool names, `get_app_guide` and
    `get_project_overview`.
  - Tools are product-level contracts in this codebase (as in 017 and 021).
  - The file layout appears only in the plan.
- [x] Focused on user value and business needs: the owner request "train the chat to explain all
  app options, specs and projects".
- [x] Written for non-technical stakeholders: the stories use questions a super user would ask.
- [x] All mandatory sections completed.

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain.
- [x] Requirements are testable and unambiguous: FR-001…FR-008 each map to a test in the tasks
  (T024, T031, T036, T040, T041, T042, T045).
- [x] Success criteria are measurable:
  - SC-001: drift test at 100%.
  - SC-002: ≥ 90% of 50 questions.
  - SC-003: 0 tokens and < 200 ms.
  - SC-004: < 10 min usability check.
- [x] Success criteria are technology-agnostic. SC-002's eval is opt-in and scored
  deterministically (plan §12).
- [x] All acceptance scenarios are defined (US1 AC1–3, US2 AC1–3, US3 AC1–2).
- [x] Edge cases are identified: release drift, non-superuser access, security-internals
  questions.
- [x] Scope is clearly bounded:
  - in scope: grounding on a shipped guide plus tools;
  - out of scope: model fine-tuning, external links, and links for roles that cannot open the
    screen.
- [x] Dependencies and assumptions identified: builds on 017/020/021/022. The guide is drafted by
  Claude and reviewed by the owner.

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria.
- [x] User scenarios cover the primary flows: app questions, the method and `/ayuda`, and
  explaining a concrete project.
- [x] The feature meets the measurable outcomes defined in Success Criteria (each SC has a task).
- [x] No implementation details leak into the specification.

## Constitution alignment (2.0.0)

- [x] VIII (AI optional and private):
  - The Ayuda page and the fixed `/ayuda` reply work without a provider.
  - FR-008 limits the overview to metadata: recipient counts and roles only, no rows and no
    credentials.
- [x] IX (spec-driven, BI-only):
  - App-usage questions are in scope.
  - Both tools are read-only, and `/ayuda` writes no files.
- [x] Bilingual constraint: every topic is in es and en, with a parity test (plan §10).
- [x] No modals: the Ayuda page and the topic view are routed views.

## Notes

- **Spec fixes applied during planning (2026-10-08)**:
  1. **FR-008 added** (`get_project_overview`) and the Key Entity "Project overview" added. Before
     the fix, US2 AC3 ("¿qué falta en este proyecto?") and US3 AC1–AC2 ("explícame este
     proyecto", citing spec lines) had no functional requirement or tool. The 021 FR-004
     inspection list does not include a project-status tool. FR-008 states it extends that list;
     021's spec text is unchanged, because this task was limited to 023 files.
  2. **FR-004 clarified**: links to routes that do not exist are dropped too, and non-`app:`
     schemes stay plain text. This blocks phishing links written by a model and matches the drift
     check of FR-006.
- **Code facts** that shaped the plan (not spec flaws):
  - Assistant messages are rendered as plain text today (`AssistantChat.tsx`).
  - The Administración tiles are a private constant in `AdminHome.tsx` (T003 exports them for the
    drift test).
  - The frontend has no YAML parser (T005 adds `yaml` as a dev-only supporting library).
- **SC-004** is a manual usability check, described in `quickstart.md` (T046).
