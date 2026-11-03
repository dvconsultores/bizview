# Feature Specification: Themes that actually repaint the application

**Product**: Bizview · **Feature Branch**: `051-theme-application` (worked on `main`) · **Created**:
2026-11-02 · **Status**: Draft

**Input**: Owner, 2026-11-01, with a screenshot of Administración → Apariencia: *"Usar en la
instalación does not produce a visible, consistent change throughout the application"* and *"the
existing themes are visually too similar"*. Both must be fixed: the activation defect **and** four
genuinely different visual identities.

**What exists**: 006 built a semantic colour-token system with one light and one dark value per
token; 030 added an installation palette and the KPI roles; 047 turned themes into data
(`cli/bizview_cli/schemas/theme.schema.json`, five built-ins in `frontend/src/theme/themes/*.json`,
mirrored byte-identically for the PDF). 050 wrote the layout rules and one segmented control. What
no feature did is connect the two halves: **the installation theme repaints the charts, and the
application itself ignores it.**

**Numbering**: the brief names `specs/059-ui-design-system/spec.md` as context. That spec is
`specs/050-ui-design-system` in this repository (050 was implemented while the brief was written with
059 in its body). Recorded rather than silently resolved.

---

## The two defects, with their causes

| Symptom | Cause found in the code |
|---|---|
| **Usar en la instalación** changes the charts and nothing else; the header, sidebar, cards, buttons, borders and page background keep the steel-teal Clásico look whatever theme is chosen | `frontend/src/index.css` defines `--c-canvas`, `--c-surface`, `--c-line*`, `--c-ink*`, `--c-primary*` and the `--brand-*` scale **once per light/dark**, with literals. `applyThemeVariables()` (`theme/palette.ts`) writes only the chart and KPI roles (`--c-chart-1..8`, `--c-kpi-*`) plus the five shape enums. Every component paints with the former, so **no theme can reach the chrome** |
| Switching theme looks like switching two accent colours; Clásico, Impacto, Contraste, Daltónico and Monocromo are near-identical | All five built-ins author the same `surface`/`card`/`text`/`muted`/`grid` (`#FFFFFF`, `#F8FAFC`, `#0F172A`, `#334155`, `#E2E8F0`) and, except Clásico, `radius: md`, `density: normal`, `kpi_scale: lg`, `font: sans`, `badge: filled`. `index.css` carries shape rules for `impacto` **only**. Colour is the sole differentiator, and the *chrome* colour is not even a token a theme may set |
| The change is only visible after a full page reload | `Appearance.tsx` calls `window.location.reload()` after the PUT succeeds, because the installation theme arrives in `GET /api/config`, which `BrandingContext` fetches once at start. There is no shared-state path from "the installation theme changed" to "repaint" |

One sentence for all three: **the theme contract describes a report palette, and the application was
never wired to it.**

## User Scenarios & Testing *(mandatory)*

### User Story 1 — choosing a theme changes the application, at once (P1) 🎯

A super user opens Administración → Apariencia, presses **Usar en la instalación** on a theme card,
and the whole application — page background, header band, sidebar, navigation selected state, cards,
buttons, borders, inputs, tables, dialogs and charts — repaints to that theme **immediately**, with
no reload, no sign-out and no flash of the old look. A toast confirms only after the server has
stored the choice. Reloading, signing in again, or opening the app on another device shows the same
theme.

**Why this priority**: without it the feature does not exist. Everything else depends on a theme
being able to reach the chrome.

**Independent test**: apply each of the four official themes and read back the computed colour of
the header band, a card surface and a primary button without reloading; all differ per theme, and
each equals the value the theme declares.

**Acceptance scenarios**

1. **Given** the installation is on Clásico, **when** the super user applies Impacto, **then** the
   header band, the page background, a card, a primary button and the sidebar's selected item all
   change within one rendered frame, and no reload happens.
2. **Given** the theme was just applied, **when** the page is reloaded, **then** the same theme is in
   force before first paint (no flash of Clásico).
3. **Given** the PUT fails, **when** the super user applies a theme, **then** nothing repaints, the
   previously active theme stays marked active, and an error is shown — never a success message.
4. **Given** a non-super-user opens Apariencia (or calls the endpoint), **when** they attempt to
   apply a theme, **then** the change is refused and the active theme is unchanged.
5. **Given** an unknown theme identifier, **when** it is applied by API, **then** it is refused with
   a validation error and the installation keeps its theme.

### User Story 2 — four official themes, each with its own identity (P1)

The installation offers exactly four official themes:

| Theme | Identity | What must be true |
|---|---|---|
| **Clásico** | the current BizView design | visually unchanged: same header band, sidebar, cards, buttons, radii, spacing and status colours as production today |
| **Impacto** | Modern Executive | royal blue/cyan family, prominent primary actions, distinctly treated navigation, modern rounded cards, strong KPI hierarchy |
| **Elegante** | Premium Professional | deep charcoal/graphite with warm neutral surfaces and restrained bronze accents, precise typography, understated elevation, distinct card and divider treatment |
| **Contraste** | Precision High Contrast | near-black/navy surfaces, explicitly visible borders, high-visibility accent, strong focus indicators, no ambiguous shadows |

Each carries **both** a light and a dark variant, so eight combinations exist and all eight render
correctly.

**Why this priority**: the second half of the owner's complaint. Two themes that differ only in an
accent colour fail the acceptance test even if activation works.

**Independent test**: render one reference dashboard (header, navigation, KPI cards, table, chart,
buttons, status badge, form control) in all four themes × both modes; a reviewer must name each
theme without reading its label.

**Acceptance scenarios**

1. **Given** production's Clásico, **when** the tokens are compared after the change, **then** every
   colour, radius, shadow and spacing value the screens actually paint with is unchanged.
2. **Given** the reference dashboard on Impacto, **when** compared with Clásico, **then** at least
   the surface colours, the accent family, the card radius and elevation, the navigation treatment
   and the KPI emphasis differ.
3. **Given** the reference dashboard on Elegante, **when** compared with both Clásico and Impacto,
   **then** its surfaces, accents, elevation, divider treatment and heading weight differ from both.
4. **Given** the reference dashboard on Contraste, **when** compared with the other three, **then**
   its borders are explicitly visible, its accent is high-visibility and its shadows are absent or
   minimal, and every text pair still meets 4.5:1.
5. **Given** any of the eight combinations, **when** the mobile shell renders at 375 px, **then**
   there is no horizontal overflow, the bottom navigation stays legible and the header band keeps
   its own foreground colour.

### User Story 3 — the theme and the appearance preference stay independent (P2)

The installation theme is the super user's choice. Sistema/Claro/Oscuro is each person's own. The
eight combinations exist because they multiply: changing the installation theme never rewrites a
user's preference, and changing Claro/Oscuro never changes which theme is installed.

**Independent test**: with the installation on each theme, cycle Sistema → Claro → Oscuro as a user
and confirm both dimensions keep their own value, across a reload and a fresh sign-in.

**Acceptance scenarios**

1. **Given** a user picked Oscuro, **when** the super user switches the installation to Elegante,
   **then** the user's preference is still Oscuro and Elegante's dark variant renders.
2. **Given** the installation is Contraste, **when** a user switches to Sistema on a device that
   prefers dark, **then** Contraste's dark variant renders and the next sign-in still resolves it.
3. **Given** a user with the device preference light, **when** they choose Oscuro, **then** the
   installation theme identity is unchanged.

### User Story 4 — the appearance page tells the truth about a theme (P2)

Each official theme card shows its name, a light preview, a dark preview, a one-line identity
description, its active status and the **Usar en la instalación** action. A preview is painted with
the theme's own tokens — including, from now on, its chrome colours — so a preview cannot show
something the application will not do. The active theme is clearly marked and its action says it is
already in use.

**Acceptance scenarios**

1. **Given** a theme card, **when** its preview is compared with the application after applying it,
   **then** the surfaces, accent and header band match.
2. **Given** the active theme's card, **when** rendered, **then** the action is disabled/labelled as
   active and the card carries a non-colour-only selected indicator.
3. **Given** an error applying a theme, **when** it fails, **then** the message names the reason and
   the card returns to its previous state.

### User Story 5 — legacy and third-party themes keep working (P3)

Daltónico and Monocromo remain valid identifiers: reports, projects and saved configurations that
name them must keep rendering, and the PDF must keep resolving them. They move out of the four
official picks into a clearly labelled compatibility group. A theme uploaded before this feature —
one that declares only the report tokens — must still theme the whole application, falling back to
derived chrome values rather than failing validation or leaving the chrome at Clásico.

**Acceptance scenarios**

1. **Given** a report whose layout names `daltonico`, **when** it renders on the web and as a PDF,
   **then** the colours are the ones it had before this feature.
2. **Given** an uploaded theme that predates the chrome tokens, **when** it is applied, **then** it
   validates, applies, and the chrome derives from its own report tokens (not from Clásico).
3. **Given** the compatibility group, **when** the super user applies Monocromo, **then** it applies
   exactly like an official theme.

## Root-cause requirements

- **FR-001** The installation theme MUST supply the application's chrome tokens, not only the chart
  and KPI roles. The chrome set covers: page background, content surface, subtle/elevated surfaces,
  header and navigation backdrop with its own foreground, sidebar, primary and secondary text,
  muted text, borders (soft/line/strong), input surfaces, primary/secondary buttons and their hover
  and active states, accent and its soft/line variants, focus ring, selected state, success/warning/
  error roles, chart series, KPI emphasis, table headers and rows, dialogs and popovers.
- **FR-002** Those tokens MUST be **data**: a theme declares them; a component MUST NOT contain a
  theme-specific colour. Applying a new theme MUST NOT require code changes or a rebuild.
- **FR-003** A theme that declares no chrome tokens MUST still be accepted and MUST derive a
  complete, contrast-safe chrome set from its declared report tokens.
- **FR-004** Applying a theme MUST repaint every mounted component without a page reload, and MUST
  NOT require signing out.
- **FR-005** The success confirmation MUST be shown only after the server has stored the choice;
  a refusal MUST leave the previous theme in force and MUST be reported as an error.
- **FR-006** The installation theme MUST be in force before first paint after a reload (no flash of
  the previous theme), and a fresh authenticated session MUST resolve it.
- **FR-007** Only a super user may change the installation theme; an unknown identifier MUST be
  refused without changing the installation.
- **FR-008** Four official themes MUST exist: `clasico`, `impacto`, `elegante`, `contraste`, each
  with `light` and `dark`.
- **FR-009** `elegante` MUST be valid everywhere a theme identifier is validated: the published
  schema's consumers, the backend registry, the report/PDF renderer, the CLI and the frontend.
- **FR-010** `clasico` MUST keep today's appearance: production's rendered values are the baseline
  and MUST NOT be replaced by a re-derivation.
- **FR-011** `impacto`, `elegante` and `contraste` MUST differ from `clasico` and from each other in
  **more than** accent colour: surfaces, border treatment, elevation, radii, navigation selected
  state, typography hierarchy and KPI emphasis are all available dimensions.
- **FR-012** Shape choices MUST remain from a fixed, validated list so a theme cannot request
  geometry the components cannot honour.
- **FR-013** `daltonico` and `monocromo` MUST remain valid and renderable (web and PDF) but MUST NOT
  appear among the four official picks; they are shown in a clearly labelled compatibility group.
- **FR-014** Report-level theme declarations MUST keep precedence over the installation theme, and
  the PDF MUST keep rendering the light variant; this feature MUST NOT change precedence.
- **FR-015** Every light/dark variant MUST meet WCAG 2.2 AA for text and component contrast, and the
  identity MUST NOT depend on colour alone.
- **FR-016** The appearance control MUST keep working on mobile first: no horizontal overflow at
  320/375/390/430 px, touch targets ≥ 44 px for primary actions, and the same behaviour at 200 %
  zoom.
- **FR-017** Theme previews MUST be painted from the same token derivation the application uses, so
  a preview cannot contradict what applying the theme does.
- **FR-018** A theme change MUST NOT alter navigation behaviour, layout semantics, business logic,
  authentication, schemas beyond the theme contract, sharing or report calculations.

### Key entities

- **Theme**: the authored data — `id`, `name`/`name_en`, `version`, `strategy`, per-mode report
  tokens (`surface`, `card`, `text`, `muted`, `grid`, `primary`, `positive`, `negative`, `neutral`,
  `delta_positive`, `delta_negative`, `series`), optional per-mode chrome tokens, and `shape`.
- **Shape**: fixed enums — radius, density, KPI scale, font, badge, plus the new identity dimensions.
- **Installation appearance**: one row, the chosen theme id; the fallback chain is unchanged.
- **User appearance preference**: `system | light | dark`, per account, independent of the theme.

## Requirements *(mandatory)*

### Functional

- **FR-019** Administración → Apariencia groups the four official themes first and the compatibility
  themes second, and states each theme's identity in one line (Spanish and English).
- **FR-020** The active theme's action MUST be disabled and labelled as already in use; the selected
  card MUST indicate selection without relying on colour alone.
- **FR-021** The chrome token set MUST be included in the published theme contract as **optional**
  fields, so every previously authored theme stays valid.
- **FR-022** The contract's shape enums MUST gain the identity dimensions (elevation, button shape,
  navigation treatment, divider weight, heading weight) with a default per dimension, so an authored
  theme may omit them.
- **FR-023** Validation MUST check the new pairs — header foreground against header backdrop, text
  against the input surface, accent against the content surface — with the same rules and messages
  as the existing pairs.
- **FR-024** `/api/config` MUST keep exposing the installation theme so a cold start can paint it
  before first paint, and the value MUST be readable by the running page after a change.

### Non-functional

- **NFR-001** Applying a theme MUST complete visually within one rendered frame of the confirmation
  response; no timer, no reload, no spinner-based workaround.
- **NFR-002** The token derivation MUST be pure and unit-testable, and the same function MUST feed
  the application, the previews and (for report roles) the PDF.
- **NFR-003** No new styling system, no second theme provider, no per-theme component copies.
- **NFR-004** Adding a theme MUST remain a data-only change.

## Success criteria

1. A super user applies each of the four official themes and sees the application — not just the
   charts — change, with no reload.
2. Clásico's rendered appearance is unchanged against a production baseline captured before the
   change.
3. The four themes are distinguishable from screenshots alone, without labels, in both modes.
4. All eight theme × mode combinations pass the contrast gate.
5. Theme choice survives a reload and a new session; user preference survives a theme change and
   vice versa.
6. Legacy references (Daltónico, Monocromo) render exactly as before on the web and in the PDF.
7. A theme authored against the previous contract still applies, with derived chrome.
8. No horizontal overflow at 320–1920 px in any of the eight combinations.

## Assumptions

- The eight combinations are `4 themes × {light, dark}`; "Sistema" resolves to one of the two and is
  not a third variant.
- Clásico's baseline is measured from the deployed installation (`bi.getbizview.com`, commit
  `bb2a8a9`) before any code changes, and recorded as values rather than impressions.
- The four official themes are the ones the brief names; Daltónico and Monocromo are kept, not
  deleted.
- The report palette keeps the **light** variant for PDF, as 047 decided.
- Chrome tokens default by derivation, so the contract stays additive.

## Out of scope

- Redesigning Clásico.
- Per-user themes (a user still chooses only Sistema/Claro/Oscuro).
- Theme authoring UI beyond what exists (upload stays).
- Changing report layouts, dashboards, sharing or business logic.
