# Feature Specification: One mobile-first design system, applied to every screen

**Product**: Bizview · **Feature Branch**: `050-ui-design-system` (worked on `main`; the brief calls it
059 — see *Numbering* below) · **Created**: 2026-11-02 · **Status**: Draft

**Input**: Owner, 2026-11-01, with six screenshots from `bi.getbizview.com`: "these are symptoms of
missing shared layout and component rules, not six unrelated bugs", and the standing decision that
BizView is a **mobile-first** application.

**What exists**: feature 006 set the colour-token system, 022/023 added the shell, the bottom
navigation and the guide, 030 gave appearance a palette and a container token (`lib/layout.ts`),
047 made themes data. There is no written rule for page widths, card padding, page headers, split
panes or segmented choices, so each page answers them again on its own — and four of them answered
differently from the rest.

**Numbering**: the brief names the feature 059 in its body and 050 in its title and file
(`pendind_specs/050-ui-design-system.md`). The repository numbers sequentially and 049 was the last
feature, so this is `specs/050-ui-design-system`. Recorded here rather than silently choosing.

---

## The four defects, with their causes

| Evidence | Symptom | Cause found in the code |
|---|---|---|
| 1, 2 | The theme library uses a fraction of the desktop width; previews are tall; the grid is two columns however wide the screen is | `Appearance.tsx` wraps the page in `max-w-4xl` (56 rem) inside a container that reaches 96 rem, and its grid is `sm:grid-cols-2` with no wider step |
| 3, 4 | "Sistema / Claro / Oscuro" stack vertically while the language options sit in a row | `ThemeSwitcher`'s container class list omits `grid` — it emits `grid-cols-3` with nothing to apply it to, so the buttons fall into a block column. `LanguageSwitcher` always emits `grid`. Two components, two answers |
| 5, 6 | The Help list is a narrow column and neither panel scrolls on its own | `Help.tsx` is a `grid` with no bounded height and no `overflow`, so the page — not the article — scrolls, and the topic list runs the full page length |

One theme runs through them: **layout rules live in each page instead of in one place**.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — the app feels like a mobile application (P1) 🎯

On a 375 px phone, every screen is a single comfortable column: a compact header, one page title,
cards that fill the width, a fixed bottom navigation that never covers content, and no sideways
scroll. On a tablet and a desktop the same screen uses the extra room instead of staying narrow.

**Why this priority**: it is the owner's first rule and the reference screenshot's whole point. A
desktop-perfect layout with a compromised phone layout is a failed implementation.

**Independent Test**: the six screens render at 320/375 px with no horizontal overflow, no element
hidden behind the bottom bar, and one column; at 1440 px they use the available width.

**Acceptance Scenarios**:

1. **Given** any page, **When** it renders at 375 px, **Then** content is one column, nothing scrolls
   sideways, and the last card is fully visible above the bottom navigation.
2. **Given** a page with a toolbar, **When** it renders at 375 px, **Then** the primary action is
   reachable without horizontal scrolling and its label is not truncated.
3. **Given** the same page at 1440 px, **Then** the content aligns to the shared container and any
   card grid uses the width (two or three columns where the content allows).

---

### User Story 2 — the appearance choices are one control (P1)

`Sistema / Claro / Oscuro` is a single-row segmented control wherever it appears — Perfil and the
account menu — and so are the language choices. Exactly one is selected, keyboard arrows move
between them, and the choice is persisted as before.

**Why this priority**: it is the most visible of the four defects, it is a two-line cause, and it is
the pattern most likely to drift again if it is not shared.

**Independent Test**: render both switchers; assert the options are siblings in a grid container,
that exactly one is `aria-checked`, and that ArrowRight moves the selection.

**Acceptance Scenarios**:

1. **Given** Perfil at any width ≥ 320 px, **Then** the three appearance options are side by side.
2. **Given** the account menu, **Then** appearance and language are the same control pattern, one
   after the other, and the menu is scrollable if the viewport is short.
3. **Given** a chosen option, **When** the page reloads, **Then** the preference is unchanged.

---

### User Story 3 — the theme library uses the screen (P1)

Apariencia fills the page container: one to three columns depending on width, equal-height cards,
compact light/dark previews, and the upload action in the page toolbar.

**Independent Test**: at 1440 px the grid has three columns and every card's name, version, origin
and actions are visible; at 375 px it has one.

**Acceptance Scenarios**:

1. **Given** 1440 px, **Then** three columns, and no unexplained empty area to the right.
2. **Given** 768 px, **Then** two columns; **given** 375 px, **Then** one.
3. **Given** a card, **Then** the selected theme is distinguishable without colour alone, and the
   apply/export/duplicate actions sit in the same place on every card.
4. **Given** a card, **When** it is opened or focused, **Then** nothing is applied, duplicated or
   deleted by that alone.

---

### User Story 4 — Ayuda is a reading application (P2)

On a desktop the topic list and the article are two bounded panels that scroll independently, with
a readable line length. On a phone the list is the first view, tapping a topic opens the article,
and Back returns to the list with the search intact.

**Independent Test**: at 1440 px the article scrolls while the topic list stays in place; at 375 px
opening a topic hides the list and shows Back.

**Acceptance Scenarios**:

1. **Given** a long article at 1440 px, **When** the reader scrolls, **Then** the topic list keeps
   its position and the page itself does not scroll.
2. **Given** a phone, **When** a topic is opened, **Then** the list is replaced by the article and
   Back restores the list with the same search and scroll position.
3. **Given** either layout, **Then** the bottom navigation does not cover the end of the article.

---

### User Story 5 — one set of rules, and a guard so it stays (P2)

The rules live in a documented design-system guide and in code tokens (`lib/layout.ts`); a component
that repeats a rule badly is visible in review, and one regression is caught by a test rather than by
a screenshot.

**Acceptance Scenarios**:

1. **Given** the docs, **Then** page container, gutters, spacing, card padding, header, split panes,
   segmented controls and focus rings are each stated once with their token.
2. **Given** a page that hard-codes a narrow maximum width or stacks a segmented choice, **Then** a
   unit test fails.

---

### Edge Cases

- **320 px** (the narrowest supported width) with a long Spanish label: the segmented control must
  shrink, not clip or scroll the page.
- **200 % zoom** on a 1024 px window behaves like 512 CSS px: the Help split becomes one column and
  no content is lost.
- **A very short viewport** (e.g. 375 × 560): the account menu scrolls; the Help panes shrink; the
  bottom navigation still does not cover content.
- **A phone with a display cutout / gesture bar**: `env(safe-area-inset-*)` still applies.
- **An imported theme** with unusual tokens: contrast and the segmented control's selected state must
  remain legible, because the control reads theme tokens only.
- **Empty states** (no dashboards, no projects, no topics found) keep the same spacing as filled ones.

## Requirements *(mandatory)*

- **FR-001**: One page container and one gutter, from `lib/layout.ts`; no page may set its own
  `max-width` for the content column.
- **FR-002**: One page-header pattern: title, optional subtitle, actions in a predictable place,
  compact enough that it does not consume the viewport on a phone.
- **FR-003**: One segmented-control component, used by both the theme and the language choices, in
  Perfil and in the account menu; single-selection, keyboard, screen-reader labelled.
- **FR-004**: The theme library uses the container width with a 1 / 2 / 3 column progression and
  equal-height cards with a compact preview.
- **FR-005**: Ayuda is two independently scrollable, viewport-bounded panels from `lg` up, and a
  list ⇄ article flow below it, preserving search and position.
- **FR-006**: The account menu groups identity, appearance, language, links and sign-out, is
  viewport-bounded with its own scroll, and restores focus to its trigger when closed.
- **FR-007**: Mobile-first: base styles are the phone's; enhancements are `min-width` only; touch
  targets ≥ 24 px, 44 px for primary actions; no horizontal overflow at 320 px.
- **FR-008**: Every surface reads theme tokens (`006`/`047`); no literal colour in a screen or
  component, and an imported theme keeps working.
- **FR-009**: The rules are documented in `docs/DESIGN-SYSTEM.md` and enforced by at least one
  automated check per rule that can be checked statically.
- **FR-010**: No behaviour changes: authentication, permissions, imports, reports, sharing, theme
  persistence and preferences are untouched.

### Key entities

- **Layout token**: a named class string in `lib/layout.ts` (container, gutter, page stack, card
  padding, panel height, split breakpoint).
- **Segmented control**: a group of mutually exclusive options, rendered as radios (or menu radio
  items inside a menu), with one selected.

## Success Criteria *(mandatory)*

- **SC-001**: 0 screens have horizontal overflow at 320, 375, 768, 1024, 1440 and 1920 px.
- **SC-002**: 0 pages define their own content `max-width`.
- **SC-003**: The three appearance options occupy one row at every width ≥ 320 px, in Perfil, in the
  account menu, in Spanish and in English.
- **SC-004**: The theme grid shows 1 column at 375 px, 2 at 768 px and 3 at 1440 px, with equal card
  heights per row.
- **SC-005**: At 1440 px a long Ayuda article scrolls without moving the topic list, and the page
  itself does not scroll.
- **SC-006**: At 375 px opening a topic replaces the list, and Back restores it with the same search.
- **SC-007**: The full existing test suite passes unchanged in meaning; the axe checks at 375 px
  report no serious or critical violation on the six screens.
- **SC-008**: A page that reintroduces a narrow `max-width` or a stacked segmented control fails a
  unit test.

## Assumptions

- The reference mobile screenshot's identity (brand gradient header, rounded cards, bottom bar) is
  kept; this feature changes rules and spacing, not the product's look.
- Breakpoints follow content, using Tailwind's `sm`/`md`/`lg`/`xl`/`2xl` as the vocabulary the code
  already uses; the numbers in the brief are the test matrix, not a second system.
- The six screenshots are the acceptance set; the rest of the frontend is audited and corrected
  where it repeats the same mistakes, without redesigning it.
- Playwright screenshots are evidence, not assertions: no pixel-diff gate is introduced.
