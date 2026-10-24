# Feature Specification: Export and import projects between installations

**Feature Branch**: `031-project-import`

**Created**: 2026-10-23

**Status**: Draft

**Input**: Owner, 2026-10-23: "same as we can download a project, allow upload; I can build a project
in one installation and move it to another." Today a workspace version can be downloaded as a zip
(014 FR-009). This feature makes the zip a **portable project**: a manifest describes what it
contains and which sources it needs; another installation uploads it, maps the sources to its own,
validates, previews and applies it as a new workspace version through the same path as a Git or
chat apply. The same mechanism later carries reusable templates (free or paid) without any extra
product concept.

**Builds on**: 014 (export zip, `build_tree`, `apply_tree`, preview in a temporary schema), 015
(validation problem format, personal-data flags), 026/030 (layouts and palette travel inside
`report.yaml`). **Changes**: the export gains a manifest and a README; old zips remain importable.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Move a finished project to another installation (Priority: P1) 🎯

The super user of installation A downloads "Ventas y facturación" as a zip. On installation B,
whose ERP source is called differently, they open Espacio de trabajo → "Importar proyecto", upload
the zip, pick which local source stands for each required one, see that every table and column the
project needs exists, validate, preview with B's real data, and apply. The dashboard appears on B
with B's numbers.

**Why this priority**: it is the whole feature; everything else is safety and convenience.

**Independent Test**: two test databases; export on A, import on B with renamed sources; after
apply, B's workspace tree equals A's except for the source rewrite, and the dashboard renders.

**Acceptance Scenarios**:

1. **Given** a zip exported by this version, **When** uploaded, **Then** BizView reads the manifest
   and shows: project name, specs, integrations, reports, the product version it came from, and the
   list of required sources with the tables/columns each uses.
2. **Given** the required sources, **When** the mapping step opens, **Then** each one is preselected
   by exact local name, otherwise by kind plus matching table names (structure only, via
   `describe_source`); missing tables or columns are shown in red per source; the user can change
   any mapping.
3. **Given** a complete mapping, **When** "Validar" runs, **Then** the project is validated with the
   same validator as the workspace, on a tree built from the active version plus the imported files
   with source names rewritten; problems appear with file, path and expected shape (015 FR-003).
4. **Given** a valid import, **When** "Vista previa" runs, **Then** it uses the 014 preview machinery
   (temporary schema, ≤ 7-day window, never `ds_*`) and shows row counts per table.
5. **Given** "Aplicar" with step-up, **Then** a new workspace version is created exactly as a Git
   apply would (`source="import:<id>"`), documents stored, dashboards synced, audit written, rollback
   available.

---

### User Story 2 - Nothing sensitive leaves with the zip (Priority: P1)

**Acceptance Scenarios**:

1. **Given** any export, **Then** the zip contains only declarative files (`.yaml`, `.yml`, `.md`,
   `.sql`, `.json`) plus the manifest and README; never credentials, connection details, data rows,
   preview results, users, audit, run history or installation branding.
2. **Given** `sources_required[]`, **Then** it lists source names, kinds and the tables/columns or
   endpoints referenced — never hosts, ports, databases or secrets.
3. **Given** the export suite, **Then** a seeded password, hostname and distinctive row value never
   appear in the zip (extends 014 SC-002 to exports).

---

### User Story 3 - Uploads are untrusted (Priority: P1)

**Acceptance Scenarios**:

1. **Given** a zip with `..` paths, absolute paths or symlinks, **Then** it is rejected before
   anything is written, naming the offending entry.
2. **Given** a zip over 20 MB, over 400 files, or with a file over 2 MB, **Then** it is rejected with
   the limit in the message.
3. **Given** a file with a disallowed extension or executable content (the 026 content check), or a
   SQL file that is not read-only under sqlglot, **Then** the import is rejected naming the file.
4. **Given** a manifest with a `format_version` newer than the product supports, or a
   `product_version` outside the compatibility range, **Then** the import is refused with "actualiza
   BizView a ≥ X".

---

### User Story 4 - Collisions are resolved, not silently overwritten (Priority: P1)

**Acceptance Scenarios**:

1. **Given** an imported integration, report or spec id that already exists in the active version,
   **Then** the collision step lists it with options `renombrar` (default, suffix `-2`, applied
   consistently to spec folders, `uses:` references and layouts), `reemplazar` (only when "modificar
   existentes" is checked; the new version supersedes the existing definition) or `omitir` (drops the
   artifact and its dependents with a warning).
2. **Given** the same project imported twice into the same installation, **Then** the second import
   is treated as collisions with `renombrar` by default.
3. **Given** `omitir` on an integration a report depends on, **Then** the report is omitted too and
   the user is told.

---

### User Story 5 - Command line for operators (Priority: P2)

An operator moving many installations uses the CLI: `bizview export <version|project> -o file.zip`
and `bizview import file.zip --source "ERP=Origen ERP" [--rename old=new] [--dry-run]`.

**Acceptance Scenarios**:

1. **Given** `--dry-run`, **Then** the CLI prints the mapping, collisions and validation problems and
   writes nothing.
2. **Given** an unmapped required source and no `--source` for it, **Then** the import fails with the
   list of required sources.
3. **Given** the CLI and the backend, **Then** they share one export/import module in `cli/` (as the
   schemas already are), so results are identical.

---

### User Story 6 - Old zips still work (Priority: P2)

**Acceptance Scenarios**:

1. **Given** a zip exported before this feature (no manifest), **When** uploaded, **Then** a manifest
   is generated from the files with a warning, and the flow continues; the required sources are
   inferred from `integration.yaml` files.
2. **Given** a zip whose files were edited after export (checksum mismatch), **Then** the import
   continues with a per-file notice "archivo modificado tras la exportación".

### Edge Cases

- Personal-data flags (015 FR-007) travel in the manifest per column; on import, flagged columns stay
  excluded unless the local dataset contract allows them explicitly. Import never widens exposure.
- Installation branding and palette preset are not imported; a report's own `layout.theme.palette`
  override (030) is kept because it is report-level.
- Import never creates sources, users or controls and never changes settings; if a required source
  has no local candidate, the mapping step says "crea la fuente primero" with a link to Fuentes de
  datos.
- Imports not applied within 24 h are deleted by the worker, like previews.
- Two imports or an import and a chat apply at the same time: the workspace lock serialises
  applies; the second is re-validated against the new active version.
- A project exported from a chat conversation carries no transcript; the applied version is enough.
- Very large projects (dozens of reports): the stepper paginates the collision list; validation and
  preview run in the worker with progress.
- The `internet` profile: step-up includes the two-step code; upload goes through the same throttling
  as other authenticated writes.

## Requirements *(mandatory)*

### Project package format
- **FR-001**: The export zip MUST contain `bizview-project.yaml` (manifest: `format_version: 1`,
  `product_version`, `exported_at`, project slug and name, `specs[]`, `integrations[]`, `reports[]`,
  `sources_required[]` with name, kind and referenced tables/columns/endpoints, per-file checksums,
  personal-data flags per column), a generated `README.md` (what the project needs), and the
  declarative files: `specs/<id>/**`, `integrations/<id>/**`, `reports/<id>/**`.
- **FR-002**: The zip MUST NOT contain credentials, connection details, data rows, preview results,
  users, audit, run history or branding. Enforced by an allowlist of paths and extensions at export
  and a test with seeded secrets.
- **FR-003**: The manifest schema lives in `cli/` with the other artifact schemas and is validated at
  export and import. Unknown higher `format_version` is refused.

### Import pipeline (super user, CSRF)
- **FR-004**: `POST /api/workspace/import` (multipart, zip only, ≤ 20 MB) unpacks into a temporary
  directory with protection against path traversal, absolute paths and symlinks; limits ≤ 400 files
  and ≤ 2 MB per file; allowed extensions `.yaml .yml .md .sql .json`; content check (026) and
  sqlglot read-only on SQL. Any failure rejects the whole import before persisting anything.
- **FR-005**: The import record (`workspace_import`: manifest, mapping, renames, status, problems,
  preview, created_by, created_at, applied_version_id) is stored and drives a 6-step view:
  Subir → Fuentes → Identificadores → Validar → Vista previa → Aplicar.
- **FR-006**: Source mapping proposals use exact name, then kind + table-name overlap via
  `describe_source` (structure only); missing tables/columns are reported per source and become
  validation errors.
- **FR-007**: Collision handling per US4; renames are applied consistently across all references.
- **FR-008**: Validation builds the tree with `build_tree` (active version + imported files with
  source rewrite and renames), runs the workspace validator, and returns problems in the 015
  format.
- **FR-009**: Preview reuses the 014 preview machinery and constraints; at most one preview running
  per import.
- **FR-010**: Apply requires step-up (password; two-step on `internet`), re-validates against the
  then-active version, calls `apply_tree` with `source="import:<id>"`, stores documents, syncs
  dashboards, audits with the manifest summary and mapping, and keeps rollback.
- **FR-011**: Unapplied imports are deleted after 24 h by the worker.

### CLI
- **FR-012**: `bizview export` and `bizview import` (US5) share one module with the backend; same
  manifest, same validation, same messages.

### UI
- **FR-013**: "Importar proyecto" in Espacio de trabajo next to "Descargar (zip)", as a `View` with
  a stepper; Spanish strings in `es.ts`; feature-010 look; mobile-first; no modals; WCAG AA; blocking
  problems shown as a pill on the step.

### Compatibility
- **FR-014**: Zips without a manifest are imported with a generated manifest and a warning (US6).
- **FR-015**: `product_version` compatibility range declared in the manifest; outside it the import
  is refused with the required version.

## Success Criteria *(mandatory)*

- **SC-001**: Round trip A → B with renamed sources yields a workspace tree on B equal to A's except
  the source rewrite (and chosen renames), the dashboards render, and `ds_<integration>` is created
  by the engine — automated with two test databases.
- **SC-002**: 0 secrets, hostnames or row values in any exported zip in the suite.
- **SC-003**: 100% of adversarial zips (traversal, symlink, oversize, forbidden extension,
  executable content, non-read-only SQL, future format) are rejected with nothing written.
- **SC-004**: An imported apply is byte-identical to a Git apply of the same files (reuse of the 014
  equivalence test).
- **SC-005**: A super user moves a one-integration/one-report project between two demo
  installations in under 5 minutes in a guided test, including source mapping.
- **SC-006**: `bizview import --dry-run` writes nothing and prints the same problems the UI shows.

## Constitution check

- II/III/VI: import carries only declarative definitions; ETL and optimized models are built by the
  engine on the target; origin stays read-only and untouched.
- V: no new stack component (zip handling and schema validation with existing libraries; anything
  else is a supporting library listed in the plan).
- VII: projects are configuration moved between installations; the product stays generic.
- VIII: no AI involved; personal-data flags preserved and never widened.
- IX: "no spec, no run" — the zip carries complete specs; the validator refuses incomplete ones.
- Constraints: Alembic migration for `workspace_import`; worker idempotent cleanup; step-up on
  `internet` includes two-step.

→ PASS, no amendment needed.

## Assumptions

- A target installation already has its sources configured; import never creates them.
- Templates (free or paid) are ordinary project zips distributed outside the product; a catalogue
  that calls this import is a later feature.
- `describe_source` is fast enough for mapping proposals on typical sources; otherwise the plan adds
  caching of the last structure per source.
