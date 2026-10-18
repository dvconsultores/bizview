# Research: Visual redesign (Customer A look)

## R1. Palette

**Decision**: a steel-teal brand scale (contracts/design-system.md) replacing the blue `--brand-*`
values; everything else derives through the feature-006 tokens.
**Rationale**: the reference's mid steel-teal (~#5b9ab9) gives only ~3.3:1 with white text, below
AA for normal text. Using 600 (#3a7393, 5.18:1) for filled controls and 600→800 for text-bearing
gradients keeps the look while meeting FR-006. Dark theme uses 400 (#6aa6c3, 7.0:1 on the dark
canvas) for accent text.
**Alternatives**: copying the reference values exactly — fails WCAG AA. Rejected.

## R2. Shared components first

**Decision**: restyle the existing primitives (`Card`, `PageHeader`, `Button`, `Input`, `Badge`,
`BackLink`, `AppShell`) and add `StatTile`, `HubCard`, `WelcomeBanner`, `Breadcrumbs`, `CodeChip`;
screens then only swap markup to these.
**Rationale**: FR-004 (one implementation reused); most screens change for free.

## R3. Shell structure

**Decision**: from `lg`, sidebar fixed full height with the gradient logo block; the top bar moves
to the content column (white). Below `lg`, a compact gradient top strip (logo + account) and the
existing bottom navigation.
**Rationale**: matches the reference desktop layout; phones keep the navigation pattern that the
e2e suite and users already rely on (FR-007, FR-008).

## R4. Gradients and contrast checks

**Decision**: text-bearing gradients run 600→800 with any highlight only decorative; e2e axe cannot
evaluate text over gradients reliably ("incomplete"), so a unit test asserts the computed contrast
of white on the lightest stop (brand-600) ≥ 4.5 from the token values.

## R5. Tests

**Decision**: existing e2e keep role/label selectors; markup changes must preserve accessible
names (headings, buttons, links). New visual checks in `tests/e2e/design.spec.ts`: sidebar active
item is filled (computed background ≠ surface), header card present on every route, banner on
home, no horizontal scroll, axe clean in both themes.
