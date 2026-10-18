# Implementation Plan: Visual redesign (Customer A look)

**Branch**: `010-visual-redesign` | **Date**: 2026-10-01 | **Spec**: [spec.md](./spec.md)

## Summary

Adopt the owner's Customer A visual language: steel-teal brand scale (AA-checked), full-height
sidebar with a gradient logo block and filled active pill, white top bar over the content, header
cards, stat tiles, hub cards, a welcome banner, chip/pill tables and filled inputs. Implemented by
restyling the shared primitives and adding five small components, then swapping screen markup —
frontend only, no behaviour change (research R1–R5, contracts/design-system.md).

## Technical Context

**Language/Version**: TypeScript 5.9 (frontend only)
**Primary Dependencies**: existing — React 19, Tailwind 3.4, Lucide React. No new libraries.
**Storage**: none (no data model change; data-model.md not needed)
**Testing**: Vitest (token contrast unit test, guard tests unchanged), Playwright (existing suites
+ new `design.spec.ts`, axe in both themes, 3 engines × 320/375 px)
**Target Platform**: existing browser matrix (Safari/iOS ≥ 14)
**Project Type**: web application (frontend part)
**Constraints**: feature-006 token guard (no raw colours), WCAG 2.1 AA both themes, mobile-first,
CSP unchanged, no modals (feature 009)
**Scale/Scope**: ~10 shared components restyled, 5 new, ~20 screens re-marked-up

## Constitution Check

| Rule | Status | Evidence |
|---|---|---|
| I. Mobile-first, Tailwind only | PASS | tokens + Tailwind classes only; bottom nav kept on phones |
| II–III, VI, VIII | N/A | no data/backend change |
| IV. Folders | PASS | `frontend/` only |
| V. Fixed stack | PASS | no library added |
| VII. One product, many installations | PASS | palette is the product default; customer logo unchanged |
| IX. Spec-driven reporting | PASS | report renderer restyled only |
| License: source link on every page | PASS | `SourceFooter` kept |

Post-design re-check: all PASS.

## Project Structure

```text
specs/010-visual-redesign/  plan.md research.md quickstart.md contracts/design-system.md tasks.md
frontend/
├── src/index.css, tailwind.config.js          brand scale, new tokens, radii
├── src/components/{AppShell,PageHeader,Card,Button,Input,Badge,BackLink,PasswordField,View}.tsx  restyle
├── src/components/{StatTile,HubCard,WelcomeBanner,Breadcrumbs,CodeChip}.tsx                      new
├── src/components/report/{KpiGrid,TrendChart,RankingTable,DataTable,PeriodPicker}.tsx            restyle
├── src/pages/{Home,Profile,ReportView,SignIn,ChangePassword,TwoFactorSetup}.tsx
├── src/pages/admin/*.tsx
└── tests/{unit/brand-contrast.test.ts, e2e/design.spec.ts}
```

## Implementation notes for tasks

1. Tokens + brand scale + contrast unit test.
2. Shared primitives restyle + new components (one batch).
3. Shell.
4. Screens in three batches (home/admin home; lists; forms/details/report/sign-in).
5. design.spec.ts, full suites, converge.

## Complexity Tracking

None.
