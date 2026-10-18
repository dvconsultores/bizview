---
description: "Task list for feature 010 — Visual redesign (Customer A look)"
---

# Tasks: Visual redesign (Customer A look)

**Input**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md),
[contracts/design-system.md](./contracts/design-system.md), [quickstart.md](./quickstart.md)

**Tests**: included (SC-002…SC-004). **Roles**: DeepSeek writes code; Claude audits/converges.
Frontend only. Keep accessible names (headings, buttons, links, labels) unchanged so existing e2e
selectors keep working; no raw palette classes or hex literals in `src/` (feature-006 guard); no
modals (feature-009 guard).

## Phase 1: Setup

- [X] T001 frontend/src/index.css + frontend/tailwind.config.js: replace the `--brand-*` triplets with the steel-teal scale of contracts/design-system.md; add tokens `--c-field`, `--c-field-focus`, `--c-line-accent`, `--grad-from`, `--grad-to`, `--radius-card` (light and `[data-theme="dark"]` values per contract); set `--c-canvas` light `244 247 250`, accent/accent-soft/chart mappings per contract; expose `field`, `field-focus`, `line-accent` colours and `rounded-card` radius in Tailwind
- [X] T002 [P] Unit test frontend/tests/unit/brand-contrast.test.ts: parse the light/dark token triplets from src/index.css and assert WCAG ratios — white on brand-600, brand-700, brand-800 ≥ 4.5; accent (light) on surface ≥ 4.5; accent (dark) on dark canvas and dark surface ≥ 4.5; field background vs surface ≥ 1.1 (visible) and ink on field ≥ 4.5

## Phase 2: Foundational — shared components (blocking)

- [X] T003 Restyle per contract: frontend/src/components/{Card,PageHeader,Button,Input,PasswordField,Badge,BackLink}.tsx (Card `tone` prop "plain" | "accent", default plain; PageHeader as header card with optional `badge`/`actions` slots; Input/PasswordField filled `bg-field`, `min-h-[3.25rem]`, bold labels, required asterisk when `required`)
- [X] T004 [P] New components per contract: frontend/src/components/{StatTile,HubCard,WelcomeBanner,Breadcrumbs,CodeChip}.tsx (Breadcrumbs embeds the restyled BackLink "Volver"; WelcomeBanner takes `name` and formats today's date with `Intl.DateTimeFormat("es", { dateStyle: "full" })`)
- [X] T005 [P] Unit tests frontend/tests/unit/design-components.test.tsx: StatTile renders label/value/footnote and delta text with sign; Breadcrumbs last item marked `aria-current="page"`; WelcomeBanner shows "Bienvenido de nuevo" and the first name; HubCard is a link with its title as accessible name

## Phase 3: User Story 1 — The app looks like Customer A (P1) 🎯 MVP

- [X] T006 [US1] frontend/src/components/AppShell.tsx: shell per contract (≥ lg full-height sidebar with gradient logo block, filled active pill, white top bar over content with theme switcher + account menu; < lg compact gradient top strip + existing bottom nav; content `bg-canvas`); keep nav labels, `aria-label`s and the account menu items (feature 006 switcher inside it)
- [X] T007 [US1] frontend/src/components/View.tsx: view header uses the PageHeader card style with its back button inside (feature-009 contract otherwise unchanged)
- [X] T008 [US1] frontend/src/pages/SignIn.tsx and ChangePassword.tsx: hero panel uses `--grad-from`→`--grad-to`; inputs filled (via T003); layout unchanged
- [X] T009 [US1] Dark-theme pass: walk every screen in dark, fix token mappings in frontend/src/index.css only (no per-screen colour overrides)

## Phase 4: User Story 2 — Home and administration home (P2)

- [X] T010 [US2] frontend/src/pages/Home.tsx: WelcomeBanner (first word of `user.full_name`) then dashboards as HubCard grid `sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4`; empty state kept
- [X] T011 [US2] frontend/src/pages/admin/AdminHome.tsx: PageHeader "Administración" → StatTile row using counts already returned by existing list endpoints the page can call (users, sources, integrations; omit a tile if its endpoint is not allowed for the role) → sections as HubCard grid

## Phase 5: User Story 3 — Lists, forms and reports (P2)

- [X] T012 [P] [US3] Lists frontend/src/pages/admin/{Users,Audit,Sources,Integrations,Tokens}.tsx: PageHeader with count badge → toolbar card (filled search, filters, primary action right) → table card per contract (CodeChip for emails/codes where it helps, bold name + muted second line, soft status pills, IconButton actions); phones keep stacked rows
- [X] T013 [P] [US3] Forms/details frontend/src/pages/admin/{UserForm,UserDetail,SourceForm,Security,AI,Workspace}.tsx and frontend/src/pages/{Profile,TwoFactorSetup}.tsx: Breadcrumbs (detail screens) → PageHeader → section cards (`tone="accent"` for the main card)
- [X] T014 [US3] Report: frontend/src/pages/ReportView.tsx (Breadcrumbs + PageHeader + toolbar card) and frontend/src/components/report/{KpiGrid,TrendChart,RankingTable,DataTable,PeriodPicker}.tsx (KPIs as StatTile with delta, chart colours via tokens, tables per contract)

## Phase 6: Polish

- [X] T015 New frontend/tests/e2e/design.spec.ts: at 1920 px and the project widths, light and dark — sidebar active link's computed background differs from the surface (desktop); every route in theme.spec's ROUTES shows a header card (`h1` inside an element with the card radius); home shows "Bienvenido de nuevo"; no horizontal scroll; axe 0 serious/critical
- [X] T016 Update existing e2e only where markup changed (keep accessible names); CHANGELOG.md Unreleased entry "Nuevo diseño (estilo Cliente A)"
- [X] T017 Run frontend suites (detached): `npm test && npm run build && npm run check:compat && npx playwright test`; then `/speckit-converge`

## Dependencies

T001 → T002; T001 → T003/T004 → T005 → T006 → T007–T009 → US2 (T010–T011) ‖ US3 (T012–T014) → T015 → T016 → T017.
T012 ‖ T013 (different files); T014 after T004.

## Implementation strategy

MVP = T001–T009 (palette, primitives, shell, dark): the whole app already reads as Customer A.
Then home/admin home, then lists/forms/reports, then tests.

---

## Phase 7: Convergence

- [X] T018 Replace `text-brand-100` (4.33:1 on brand-600) with `text-on-primary` for the organisation name on the brand gradient in frontend/src/components/AppShell.tsx (sidebar block and phone strip) and frontend/src/pages/SignIn.tsx; add brand-100/brand-600 is NOT used for text (or the on-primary pair) to frontend/tests/unit/brand-contrast.test.ts, per FR-006 / US1/AC4 / research R4 (contradicts)
- [X] T019 Put NotFound and Forbidden (frontend/src/pages/NotFound.tsx, Forbidden.tsx) inside a header card with `ButtonLink` instead of a hand-styled link, and remove their exemption from the header-card check in frontend/tests/e2e/design.spec.ts, per FR-003 / SC-001 (partial)
- [X] T020 Add a shared `IconButton` (44 px icon action, aria-label required) in frontend/src/components/IconButton.tsx and use it for row actions in frontend/src/pages/admin/{Users,Sources,Tokens,Integrations}.tsx, per FR-004 / contracts/design-system.md tables row (missing)
- [X] T021 Restyle PEM/textarea fields as filled inputs (`bg-field border-transparent rounded-xl focus:ring-field-focus`, labels `text-sm font-semibold text-ink-2`) in frontend/src/components/SecretField.tsx and frontend/src/pages/admin/SourceForm.tsx, per FR-004 / US3/AC2 (partial)
- [X] T022 Polish from the convergence review: PEM textareas (SecretField.tsx, SourceForm.tsx) get `required`, error/help ids and `aria-describedby` (reuse one PemField); `text-white` → `text-on-primary` in Users.tsx and AppShell.tsx; Users "Nuevo usuario" desktop link → `ButtonLink`; brand-contrast.test.ts checks on-primary on the dark gradient stops instead of the duplicate light pair, per FR-004 / FR-006 (partial)
