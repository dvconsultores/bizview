# Tasks — 047 themes as data

**Input**: [spec.md](./spec.md) · [plan.md](./plan.md) · [research.md](./research.md) ·
[data-model.md](./data-model.md) · [contracts/](./contracts) · [quickstart.md](./quickstart.md)

Six commits, as the brief asks. Every commit leaves the tree green and the product rendering what it
rendered before.

## Phase 1: Schema, validator, built-ins, CI (commit 1)

- [X] T001 Write `cli/bizview_cli/schemas/theme.schema.json` as the published contract (data-model
  §Theme): required keys, `#RRGGBB`, `series` 3–8, the `shape` enums, `additionalProperties: false`
- [X] T002 Write `cli/bizview_cli/theme.py`: `validate_theme(data) -> list[Problem]` with the codes
  of contracts/theme-format.md (including the contrast, series-ΔE and polarity checks against each
  mode's own surface) and `derive_tokens(theme, mode)` producing `series1..8`, `kpi_text`,
  `kpi_surface`, `kpi_delta_bg` from the authored tokens
- [X] T003 Convert the five built-ins to the authored format under
  `frontend/src/theme/themes/*.json`, mirror them byte-identically to
  `backend/app/reports/themes/*.json`, and assert in a test that each one's `derive_tokens` output
  equals today's `frontend/src/theme/palettes/*.json` (the five looks must not change)
- [X] T004 Extend the CI gate: `frontend/tests/unit/themes.test.ts` validates every built-in and
  every fixture with the same rules, and the CLI's `tests/test_theme.py` covers valid files and one
  fixture per refusal code
- [X] T005 `bizview theme validate <file>` in `cli/bizview_cli/__main__.py`, with exit codes 0/1/2
  and every problem printed
- [X] T006 `bizview theme preview <file> --out <svg>` rendering the same card the admin page draws
  (KPI + badge, four bars, two-series sparkline), light and dark side by side
- [X] T007 Keep 030's `palette-presets.test.ts` and `test_palette.py` green against the derived
  tokens

## Phase 2: Storage, API, migration (commit 2)

- [X] T008 `Theme` model in `backend/app/models.py` (data-model §Theme stored row) with the
  `ck_theme_origin` and `ck_theme_version` checks and an index on `project_id`
- [X] T009 Migration `0042_themes`: create the table, seed the five built-ins from the mirrored
  JSON, add `appearance_settings.theme_id`, and backfill it from `palette_preset`
- [X] T010 `backend/app/api/themes.py` with the endpoints of contracts/theme-api.md (list, upload
  with replace confirmation, delete with the in-use refusal, download, viewer read with `ETag`,
  installation setting) and the four audit kinds
- [X] T011 `tests/test_themes.py` over a real database: upload → listed with origin; replace bumps
  `version` and needs `?replace=true`; delete refused with the report named; built-in immutable;
  viewer read 304s on the second call with the same `ETag`
- [X] T012 The bootstrap refreshes a built-in row from the product's file so a shipped colour change
  reaches an installation that never touched it

## Phase 3: Apariencia (commit 3)

- [ ] T013 `frontend/src/pages/admin/Appearance.tsx` becomes the library: a grid of cards (light and
  dark side by side, drawn from the theme's tokens), origin badge, and the actions upload,
  download, duplicate, delete, apply
- [ ] T014 The upload dialog: paste or choose a `.yaml`, show every problem the server returned with
  its path, and offer the replace confirmation when the id exists
- [ ] T015 `frontend/tests/unit/themes.test.tsx`: the grid renders every theme, a refusal shows its
  message, applying calls the endpoint and the store invalidates
- [ ] T016 i18n `es.ts`/`en.ts` for every new label, and `no-literals.test.ts` stays green

## Phase 4: Report fields, resolution, mode, share, PDF (commit 4)

- [ ] T017 `layout.theme.id` and `layout.theme.mode` accepted by the report schema, `palette` kept
  as a deprecated alias; the project validator reports an unknown theme id as a problem
- [ ] T018 Resolve the theme once per report into CSS custom properties on the report's container
  (colours, plus `--t-radius`, `--t-density`, `--t-kpi-scale`, `--t-font`, `--t-badge`), with the
  report → installation → `impacto` order
- [ ] T019 The mode: `auto|light|dark` on the container's `data-mode`, the sun/moon toggle writing
  `sessionStorage` per report, and the share link opening in the report's mode
- [ ] T020 The PDF resolves the theme's **light** variant through `reports/palette.py`
- [ ] T021 Tests: the tokens flip on a rendered report (now and after reload), a dark report inside
  a light app keeps the chrome light, the share link opens dark, the PDF uses the light variant

## Phase 5: Projects carry themes (commit 5)

- [ ] T022 Import `themes/*.yaml` from a project zip, validating with `validate_theme`, storing with
  `origin = project` and the project id, and reporting a refusal as a problem (never a half-store)
- [ ] T023 Collisions: rename, replace or skip when the id exists, naming the owner (a built-in can
  only be renamed or skipped); removal when the project is deleted
- [ ] T024 Export writes the project's themes back into the zip
- [ ] T025 Tests over the import/export round trip and the three collision answers

## Phase 6: CLI, pack, docs, changelog (commit 6)

- [ ] T026 `THEME.md` and `theme.schema.json` in `cli/bizview_cli/workspace_template/files/`, plus
  the five built-ins as examples so an author has something to start from
- [ ] T027 `docs/THEMES.md` (the contract, the authoring steps, the accessibility table, the mode
  rules) and a help topic `temas` in both languages with its `index.yaml` entry
- [ ] T028 `CHANGELOG.md` under *Unreleased* and the field reference in `docs/VIBE-REPORTING.md`
- [ ] T029 Run the gates and the suites, record every result in `evidence.md`

## Dependencies

- T001–T003 before everything: the contract and the derived tokens are what the rest reads.
- T008–T012 before T013 (the grid reads the API) and before T022 (the import writes rows).
- T017–T018 before T019–T021.
- T022 before T024.
- T026–T028 last: they document what exists.

## Parallel opportunities

- T001/T002 (schema and validator) with T003 (the built-ins' conversion) once the token names are
  fixed.
- T010 (API) with T013 (the UI) once the endpoint shapes are in contracts/.
- T016 (i18n) with T017 (report fields) — different files.

## MVP scope

T001–T007 + T008–T012 + T013–T015: an author can write, validate, upload and apply a theme and the
installation renders with it. Everything after that is per-report control and shipping.
