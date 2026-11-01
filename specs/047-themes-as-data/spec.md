# Feature Specification: Themes as data, authored outside

**Feature Branch**: `main` (this repository works on `main` only; no feature branches)

**Created**: 2026-10-31

**Status**: Draft

**Input**: User description: "047-themes-as-data — a theme is a data file of tokens (never CSS, fonts or markup) that anyone, a person or any AI, writes outside BizView against a published schema, uploads in Apariencia or ships inside a project zip, and applies to the installation or to any dashboard. Built-in presets become themes in the same format. Every dashboard, share link, TV mode and PDF renders from the theme's tokens only."

## Context

The product already has **palettes** (feature 030): five built-in presets, each a JSON file read
by the web app and mirrored byte-for-byte for the PDF. An installation picks one; a report may
override it. What it does not have is a way for a customer to bring **their own** look — a brand
its blue, its spacing, its font family — except by editing the product's own files.

The palette was the right idea and the wrong shape: the five presets are the only citizens, the
format is internal, and nothing in the product can validate a theme a customer wrote. This feature
makes the theme a **published contract**: a file of tokens, written outside BizView with any AI,
validated before it is accepted, applied to the installation or to one dashboard, and rendered by
every surface from those tokens only.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A customer's brand becomes a theme, and it is accepted on the first try (Priority: P1)

Someone who has the brand guide (or only a screenshot of the company's website) asks an AI to
produce a theme file. The AI writes it against the published schema; the author validates it
locally and sees a preview before touching the server; when it is accepted, the whole installation
looks like the brand.

**Why this priority**: this is the feature. Everything else — the library, the per-dashboard
override, the project shipping — is only useful once a theme can be *authored outside and
accepted*.

**Independent Test**: give the published schema and the authoring page to a person who has never
seen the product, with a brand colour; they produce a file that uploads without an error message.

**Acceptance Scenarios**:

1. **Given** the published theme schema and a brand description, **When** an author (or their AI)
   writes a theme file, **Then** a validator accepts it or names every problem with the pair and
   the measured value that failed.
2. **Given** a theme file with a colour that fails the contrast rule, **When** it is validated,
   **Then** the message names the two tokens and the ratio it measured, not just "invalid".
3. **Given** a theme file with a key the schema does not define, **When** it is validated, **Then**
   it is refused, because a theme is data and nothing else.
4. **Given** a theme that validates, **When** the author previews it, **Then** they see the same
   cards the admin page will show, without a server.

---

### User Story 2 - A theme is uploaded, kept, and applied (Priority: P1)

A super user uploads a theme in the appearance page, sees it among the built-ins with a live
preview in both modes, and makes it the installation's theme.

**Why this priority**: an approved theme has to reach the product without a deployment.

**Independent Test**: upload a valid theme, apply it, and see the installation's colour tokens
change — in the same session and after a reload.

**Acceptance Scenarios**:

1. **Given** the appearance page, **When** the super user uploads a valid theme, **Then** it
   appears in the library with its preview in light and dark and its origin.
2. **Given** a theme with an id that already exists, **When** the super user uploads it, **Then**
   they are asked to confirm the replacement and the stored version increases.
3. **Given** a theme referenced by a report, **When** the super user tries to delete it, **Then**
   the deletion is refused and the report is named.
4. **Given** a built-in theme, **When** the super user tries to delete it, **Then** it cannot.
5. **Given** a theme applied to the installation, **When** any user opens a dashboard, **Then** the
   colours, the density and the radius come from it.
6. **Given** an uploaded theme, **When** the super user downloads it, **Then** they get the same
   file they uploaded, so it can be edited and uploaded again.

---

### User Story 3 - One dashboard renders in its own theme and its own mode (Priority: P2)

A report declares the theme it wants and whether it is light, dark or follows the viewer; the
viewer may still flip it. A share link opens the report the way its author chose.

**Why this priority**: per-dashboard control is where a theme stops being an installation setting
and becomes part of the report the author ships.

**Independent Test**: set a report's theme and mode, open it with the app in the other mode, and
see the report area follow the report while the surrounding app keeps the viewer's choice; take a
PDF and see the light variant.

**Acceptance Scenarios**:

1. **Given** a report with a theme, **When** it renders, **Then** its colours come from that theme
   and not from the installation's.
2. **Given** a report whose mode is dark, **When** a viewer with a light app opens it, **Then** the
   report area is dark and the surrounding chrome stays light.
3. **Given** a report in dark mode, **When** the viewer flips the toggle, **Then** the report area
   follows the viewer for that session and nothing is written to the report.
4. **Given** a share link to a report in dark mode, **When** somebody opens it, **Then** it opens
   dark, whether or not they are signed in.
5. **Given** any report, **When** its PDF is produced, **Then** it uses the theme's light variant.
6. **Given** a report that declares a theme the installation does not have, **When** it renders,
   **Then** it falls back to the installation's theme and says so in the validation, instead of
   failing.

---

### User Story 4 - A project carries its theme (Priority: P2)

An author ships the theme with the project zip, so the dashboard arrives looking as intended: the
import validates it, the library lists it with the project as its origin, and the export gives it
back.

**Why this priority**: the whole point of authoring outside is that the artifact travels complete.

**Independent Test**: zip a project with a theme, import it into a clean installation, and see the
dashboard rendered with that theme without a manual upload.

**Acceptance Scenarios**:

1. **Given** a project with `themes/<id>.yaml`, **When** it is imported, **Then** the theme is
   validated like any other artifact and listed with the project as its origin.
2. **Given** an imported project whose theme id already exists with different tokens, **When** the
   import runs, **Then** the author is offered rename, replace or skip, and told which project owns
   the existing one.
3. **Given** a project with a theme, **When** it is exported, **Then** the zip carries the theme
   back.
4. **Given** a theme whose tokens fail validation, **When** the project is imported, **Then** the
   import reports it as a problem and does not store a half-broken theme.

---

### User Story 5 - The five built-ins are themes like any other (Priority: P3)

An installation's existing choice keeps working, and the built-ins obey the same schema and the
same checks as an uploaded file — so the format is proven by the product's own data.

**Why this priority**: without it, the schema describes a format only customers use and the
product's own presets could drift from it.

**Independently Testable**: validate the built-ins with the same validator a customer's file goes
through; they all pass, and they render identically to before.

**Acceptance Scenarios**:

1. **Given** the five built-ins, **When** the validator runs over them, **Then** every one passes
   and the check runs in CI.
2. **Given** an installation that chose a built-in before this feature, **When** it upgrades,
   **Then** it keeps the same look with no setting to change.
3. **Given** a theme that changes only the shape (radius, density) and not the colours, **When**
   applied, **Then** the dashboards change shape and keep the installation's colours.

---

### Edge Cases

- **A theme with one series colour too few or too many**: the schema defines 3–8; the message says
  what is allowed, because an AI that reads "3–8" writes 3 or 8.
- **A colour that is a CSS function or a named colour**: refused — tokens are `#RRGGBB`, and a
  theme that sneaks in CSS is exactly what "data, never CSS" forbids.
- **A font family that is not installed**: the schema accepts only the built-in families, so a
  theme cannot ask for a font the PDF cannot embed.
- **A theme in a project whose id collides with a built-in**: the built-in wins and the project's
  theme must be renamed; a built-in cannot be replaced by an import.
- **A theme deleted while a report references it**: refused; a theme orphaned because its project
  was deleted falls back to the installation's and the report says so.
- **A very large theme file**: refused above a size cap, since a theme is tokens, not a stylesheet.
- **A dark theme that passes contrast but whose series are indistinguishable on the dark surface**:
  the distinguishable check runs on the surface each mode actually paints.
- **Two themes whose ids differ only in case with a trailing space after the colon**: normalised,
  because a YAML file written by an AI will contain both.

## Requirements *(mandatory)*

### Functional Requirements

**The contract**

- **FR-001**: A theme MUST be a declarative file of tokens with an id, a name in both languages, a
  version, a light set, a dark set and an optional shape set, and MUST be defined in exactly one
  published schema read by the product, the CLI and the authoring pack.
- **FR-002**: The light and dark sets MUST both carry every colour token the product renders with,
  and MUST NOT carry any key the schema does not define.
- **FR-003**: Colours MUST be six-digit hexadecimals, and a series MUST have between three and
  eight entries.
- **FR-004**: The shape tokens MUST come from fixed lists (radius, density, KPI scale, font family,
  badge style), so a theme cannot introduce a typeface or a layout the renderers do not have.
- **FR-005**: A theme MUST fit in a small size cap: it is tokens, not a stylesheet.
- **FR-006**: Every theme MUST pass the accessibility checks in both modes — text against its
  surface, series against the surface it is drawn on and against each other, the positive and
  negative colours distinguishable — and a failure MUST name the tokens and the value measured.
- **FR-007**: The validator MUST run over the product's own built-in themes, and that check MUST be
  part of the automated gates.

**Authoring outside**

- **FR-008**: An author MUST be able to validate a theme without a server, and MUST get the same
  answer the server would give.
- **FR-009**: An author MUST be able to see a theme rendered before uploading it.
- **FR-010**: The authoring pack MUST carry the theme schema and one page that tells an AI how to
  produce a theme from a brand guide, a screenshot or a description.

**Upload, library, apply**

- **FR-011**: A super user MUST be able to upload a theme, and MUST be told why a theme is refused.
- **FR-012**: Uploading an id that already exists MUST require a confirmation and MUST increase the
  stored version; a built-in MUST NOT be replaceable.
- **FR-013**: The library MUST show built-in, uploaded and project-shipped themes with a preview in
  both modes, and MUST say where each came from.
- **FR-014**: A theme MUST NOT be deletable while a report references it, and the refusal MUST name
  those reports; a built-in MUST NOT be deletable at all.
- **FR-015**: A super user MUST be able to download a stored theme so it can be edited and uploaded
  again, and to duplicate one as a starting point.
- **FR-016**: A super user MUST be able to make any theme the installation's theme, and every
  viewer MUST see the change without a deployment.

**Per report**

- **FR-017**: A report MUST be able to declare a theme and a mode (follow the viewer, light, dark).
- **FR-018**: A report's theme MUST win over the installation's, which MUST win over the product's
  default; a theme the installation does not have MUST fall back and be reported as a validation
  problem, never as a rendering failure.
- **FR-019**: A report in a forced mode MUST paint its own area in that mode while the rest of the
  application keeps the viewer's choice, and the viewer MUST be able to flip it for their session
  without changing the report.
- **FR-020**: A share link MUST open in the report's mode, signed in or not.
- **FR-021**: A PDF MUST render the theme's light variant.

**Projects**

- **FR-022**: A theme shipped inside a project MUST be validated like any other artifact when the
  project is imported, and MUST be listed with the project as its origin.
- **FR-023**: A colliding theme id in an import MUST offer rename, replace or skip, and MUST say
  which project or built-in owns the existing one.
- **FR-024**: A project's export MUST carry its themes.

**Every surface renders from tokens**

- **FR-025**: Dashboards, share links, TV mode and PDFs MUST take their colours, radius, density
  and font from the resolved theme's tokens, and no component MAY read a colour literal.

### Key Entities

- **Theme**: id, names in two languages, version, light tokens, dark tokens, optional shape tokens,
  origin (built-in, uploaded, project) and, for a project theme, the project it belongs to.
- **Theme tokens**: the colour roles a chart, a card and a badge paint with, plus the shape choices
  from their fixed lists.
- **Report theme choice**: the theme id and mode a report declares, both optional.
- **Installation theme choice**: the theme the installation applies to every dashboard that
  declares none.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A person who has never used the product produces a theme that uploads without an
  error, using only the published schema and the authoring page.
- **SC-002**: An AI given the authoring page and a brand description produces a theme that
  validates on the first attempt in at least four runs out of five.
- **SC-003**: A refused theme always says which rule failed and the value it measured: 100 % of
  refusals name a token pair or a schema key, never a bare "invalid".
- **SC-004**: Every built-in theme passes the same validation a customer's file goes through, and
  that check runs on every change.
- **SC-005**: An installation that chose a built-in before this feature looks the same afterwards,
  with no setting changed.
- **SC-006**: Changing the installation's theme is visible on the next dashboard opened, in the
  same session, without a deployment or a restart.
- **SC-007**: A dashboard renders in its own theme and mode while the surrounding application keeps
  the viewer's choice, in both themes, at 320 px and on desktop.
- **SC-008**: A project exported from one installation and imported into another renders its
  dashboard with its own theme, with no manual step.
- **SC-009**: Zero colour literals in components: every colour a screen or a PDF paints comes from
  the resolved theme.

## Assumptions

- **The theme format is a superset of what the renderers already read.** The five built-ins keep
  their visual result; the new schema is what an author writes, and the runtime tokens the screens
  and the PDF already consume are derived from it. This keeps 030's rendering and its tests intact
  while the *authored* format becomes the published one.
- **`layout.theme.palette` stays as a deprecated alias** for one version, as the brief says, so a
  project written yesterday still validates.
- **Fonts stay the built-in families** (`sans`, `serif`, `mono`): the PDF embeds from a fixed set,
  and a customer uploads tokens, not typefaces.
- **The accessibility thresholds are the ones the product already enforces** (text 4.5:1, series
  3:1, adjacent series distinguishable), so a customer's theme is held to the product's own bar.
- **Themes are installation data, not product data**: they live in the database, travel in a
  project zip and are exported, and they never enter this repository except as the built-ins.
- **No constitution amendment**: a theme is configuration and data (principle VII), declarative and
  validated (IX), adds no stack component (V) and no new screen paradigm (I).
