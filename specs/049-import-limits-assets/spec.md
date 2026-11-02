# Feature Specification: Import limits that account for project images, and import as the only way in

**Product**: Bizview · **Feature Branch**: `049-import-limits-assets`

**Created**: 2026-11-01

**Status**: Draft

**Input**: Owner, 2026-11-01, after a production import failed: "un proyecto con `assets/coins/*.png`
(483 logos, 1,8 MB) no se puede importar"; plus the standing decision that projects are authored
outside Bizview and arrive only by import.

**What exists**: 031 set the import budget at ≤ 400 files, ≤ 2 MB per file and ≤ 20 MB per zip, for a
project made of YAML, Markdown and SQL. 044 added `assets/**` (≤ 300 KB per image, ≤ 25 MB of images)
but never gave images their own budget, so they still count against the 400 files and the 20 MB. A
project that ships a logo set is therefore refused before validation, with a message that names
limits the author cannot act on.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A project with a logo set imports (Priority: P1) 🎯

The author has a working project — a few dozen declarative files and 483 coin logos under
`assets/coins/` — and imports it. It imports, validates, applies, and its images render.

**Why this priority**: this is the reported defect. The project is valid and useful; the product
refuses it, and no amount of authoring fixes it. Nothing else matters until a real project with
images can get in.

**Independent Test**: import the 483-logo fixture; the project exists, `assets/` holds every image,
the validation result comes back, and `/api/reports/<id>/assets/…` serves them.

**Acceptance Scenarios**:

1. **Given** a project with 483 images (1.8 MB) and 40 artifacts, **When** it is imported, **Then**
   the import succeeds and the response reports the artifacts and images that came in.
2. **Given** the same project, **When** it is applied, **Then** the report renders its images.
3. **Given** a project with 2 001 images, **When** it is imported, **Then** it is refused with a
   message that names **the images**: how many were found, in which folder, and the limit — never a
   combined artifact-and-image figure.
4. **Given** a project with 401 artifact files, **When** it is imported, **Then** it is refused with
   a message that names **the artifacts**: their total, the folders counted, and the limit.

---

### User Story 2 - The author knows the limits before uploading (Priority: P1)

The author picks the zip. Before anything is sent, the app reads the archive's index and shows the
two counts and sizes against their limits. A zip over a limit is not uploaded at all.

**Why this priority**: the previous failure cost a round trip and produced a message the author
could not use. Telling them before the upload — with the real numbers and the folder that is over —
turns a refusal into an instruction.

**Independent Test**: a unit test over a zip's central directory returns both tallies; the page
disables the import action and names the budget exceeded when one is.

**Acceptance Scenarios**:

1. **Given** a zip with 483 images and 40 artifacts, **When** the author chooses it, **Then** both
   tallies appear with their limits and the import action stays available.
2. **Given** a zip with 2 100 images, **When** the author chooses it, **Then** the images tally is
   shown as over the limit, the reason names `assets/`, and the import action is disabled.
3. **Given** the tallies are shown, **When** the author uploads anyway (the server is the authority),
   **Then** the server re-checks and answers the same way.

---

### User Story 3 - A project folder with pack files still in it imports (Priority: P2)

An author zips their project folder while it still contains the authoring pack's own scaffolding —
`PROMPT.md`, `REQUEST.md`, `request/`, `sources/`, `.bizview/`, a README, editor and OS files.
The import brings in the project part and lists the rest as ignored.

**Why this priority**: the pack and the project live in the same folder by design (043). Refusing
the whole upload teaches nothing; listing what was skipped teaches exactly the right thing.

**Independent Test**: import a zip carrying `PROMPT.md`, `REQUEST.md`, `request/`, `sources/`,
`.bizview/`, `README.md`, `.DS_Store` and `__MACOSX/` beside a valid project; the project imports and
the response lists each of those paths under ignored files.

**Acceptance Scenarios**:

1. **Given** a zip with the pack's files beside a valid project, **When** it is imported, **Then**
   the project imports and every pack path appears in the ignored list.
2. **Given** a zip with a `.js` file anywhere, **When** it is imported, **Then** the import fails:
   harmless noise is skipped, executable or disallowed content is not.

---

### User Story 4 - Import is the only way a project enters Bizview (Priority: P1)

There is no "Crear proyecto" / "Nuevo proyecto" anywhere. Projects are authored outside Bizview with
whatever tool the author prefers, and arrive as a zip. The Projects page offers **Importar proyecto**;
its empty state offers the same.

**Why this priority**: owner decision. A half-present create button is worse than none: it invites an
empty project the product cannot fill, and it contradicts the documentation.

**Independent Test**: the Projects page renders no create affordance in any state; a direct call to
the old creation endpoint cannot create a project; an import still creates one.

**Acceptance Scenarios**:

1. **Given** the Projects page with projects, **When** it renders, **Then** there is no create button
   or form, and **Importar proyecto** is present.
2. **Given** the Projects page with no projects, **When** it renders, **Then** the empty state offers
   **Importar proyecto** and does not suggest creating one.
3. **Given** a direct request to the removed creation endpoint, **When** it is sent, **Then** it is
   refused with a documented, stable error and no project is created.
4. **Given** a valid zip, **When** it is imported, **Then** the project is created, and export,
   validation, history, apply and rollback keep working.

---

### Edge Cases

- **Zip size** is the sum of both budgets (45 MB by default) with the existing ratio and total-bytes
  protection unchanged; a zip that decompresses past either budget is still refused.
- **A single artifact file over 2 MB** and **a single image over 300 KB** are still refused
  individually, naming the file.
- **An image outside the project's own folder** (`assets/` at the wrong depth) is skipped as
  unknown, not counted as an asset.
- **A directory entry with no files**, and **an empty zip**, are refused as before.
- **Both budgets over at once**: the artifact message wins, because artifacts are what the project is.
- **A zip whose top folder is the pack name** (e.g. `bizview-starter/`) is stripped, then the pack
  files inside are ignored; the project part still imports.
- **An existing installation's settings**: budgets are settings with defaults; an installation that
  never touched them gets the new defaults, and an operator's explicit values are kept.
- **Re-importing an exported zip** imports cleanly: the export carries the same files the import
  accepts, and nothing in it is "unknown".

## Requirements *(mandatory)*

- **FR-001**: Two budgets, counted separately: **artifacts** (`project.yaml`, `specs/**`,
  `integrations/**`, `reports/**`, `themes/**`, `distributions/**`, and the constitution) at ≤ 400
  files / ≤ 2 MB per file / ≤ 20 MB total, and **assets** (`assets/**`) at ≤ 2 000 files / ≤ 300 KB
  per file / ≤ 25 MB total. All six numbers are settings with those defaults.
- **FR-002**: The zip size limit is the sum of the two totals. The zip-bomb protection (entry count,
  per-entry ratio, cumulative uncompressed bytes) measures each entry against the budget its path
  belongs to.
- **FR-003**: Every refusal names the budget that was exceeded, the path or folder counted, the
  measured value and the limit. A refusal never reports a combined figure.
- **FR-004**: The browser reads the zip's central directory before uploading and shows both tallies
  against their limits; over a limit, the import action is disabled and names the reason. The server
  repeats the check and is authoritative.
- **FR-005**: Files outside the layout are listed as ignored and do not fail the import, provided
  they are harmless (text, images). Executable or otherwise disallowed content anywhere still fails.
- **FR-006**: The CLI (`bizview validate`, and an import dry run) reports the same two budgets and the
  same ignored files as the server, from the same code.
- **FR-007**: `docs/IMPORT.md`, the guide topic **Importar un proyecto** (both languages) and
  `PROMPT.md` in the authoring pack state the two budgets, that only project files are imported, and
  that a new project enters Bizview only by import.
- **FR-008**: No interface — page, empty state, menu, shortcut — offers manual project creation. The
  creation endpoint refuses direct calls with a documented error and creates nothing.
- **FR-009**: Import keeps its own internal path to project creation (it is not an API caller), so
  import, validation, assets, apply, rollback, history and export keep working unchanged.
- **FR-010**: Existing projects, their files, reports and records are untouched by this feature.

### Key entities

- **Budget**: a named allowance — `artifacts` or `assets` — with a file count, a per-file size and a
  total size. Two exist; each is measured over the paths it owns.
- **Tally**: what a given zip (or folder) actually contains for one budget: files, total bytes, the
  largest file, and the paths that belong to no budget (ignored).
- **Ignored file**: a path inside the archive that no budget owns and the product will not store.

## Success Criteria *(mandatory)*

- **SC-001**: The 483-logo project from the report imports, applies and renders its images.
- **SC-002**: 100 % of refusals name exactly one budget, with a measured value and a limit; no
  message reports a combined figure.
- **SC-003**: A zip over a limit is refused in the browser, before any byte is uploaded, and the
  reason names the same budget the server would.
- **SC-004**: A project folder that still carries the pack's files imports without manual cleanup,
  and every skipped path is listed.
- **SC-005**: The CLI and the server report identical tallies for the same project — same files,
  same bytes, same ignored paths.
- **SC-006**: No route, endpoint or screen in the product can create an empty project; import is the
  only path, verified by test.
- **SC-007**: Every project that imported before this release still imports, unchanged.

## Assumptions

- The budgets are settings, not constants: an installation may raise them, and the defaults are the
  numbers above (043 WS-C precedent).
- Images are the only binary content a project may carry; "assets" means `assets/**` and nothing else.
- The pre-flight reads only the archive's index (names and declared sizes); it never decompresses.
  The declared size is what the server measures too, and a lie in the index is caught by the server's
  own reading of the bytes.
- "Executable or disallowed content" keeps the 031 and 044 rules as they are; this feature only
  changes what is counted against what, and what is skipped instead of failing.
- Removing manual creation is a product decision made by the owner; the API surface it removes has no
  other caller inside the product.
