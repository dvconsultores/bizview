# Tasks: themes that repaint the application

**Feature**: `051-theme-application` · **Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)

Legend: `[P]` parallel-safe, `[USn]` user story from the spec, `[T]` contract/theme, `[W]` web,
`[X]` verification. Order is execution order.

## Phase 1 — the contract can describe chrome (FR-001, FR-002, FR-021, FR-022, FR-023)

- [x] T001 Add the seven optional chrome tokens (`canvas`, `chrome`, `chrome_text`, `field`, `line`,
      `accent`, `warning`) to both `light` and `dark` in `cli/bizview_cli/schemas/theme.schema.json`
- [x] T002 Add the six identity enums (`elevation`, `button`, `nav`, `divider`, `heading`,
      `card_border`) to `shape` in the same schema
- [x] T003 Extend `SHAPE_LISTS`/`SHAPE_DEFAULTS` and the token names in `cli/bizview_cli/theme.py`
- [x] T004 Add the three chrome contrast rules to `_shape_problems` in `cli/bizview_cli/theme.py`
- [x] T005 `[P]` Extend `cli/tests/test_theme.py`: new tokens/enums accepted, bad enum refused,
      chrome contrast refusals named, a pre-051 theme file still validates

## Phase 2 — the derivation (FR-002, FR-003, FR-012, NFR-002)

- [x] T006 `[W]` New `frontend/src/theme/derive.ts`: colour maths (`mix`, `triplet`, `contrast`,
      `readableOn`), `chromeOf`, `semanticVariables`, `designVariables`
- [x] T007 `[W]` Extend `frontend/src/theme/themes.ts`: `ThemeTokens` chrome fields, `ThemeShape`
      identity enums and their defaults, `designVariables` mapping
- [x] T008 `[W]` `frontend/src/theme/palette.ts#applyThemeVariables` writes chrome + design
      variables, `data-nav`/`data-elevation`/`data-card-border`, caches to the device and updates
      `meta[theme-color]`; `themeStyle` uses the same derivation
- [x] T009 `[W]` `frontend/src/index.css`: add the `--c-chrome`/`--c-on-chrome` fallbacks, the
      `.nav-active` rules per `data-nav`, `.page-title`/`.section-title` weights, `--card-border`;
      drop the `[data-palette="impacto"]` shape block
- [x] T010 `[W]` `frontend/tailwind.config.js`: `chrome`, `on-chrome`, `rounded-btn`,
      `rounded-field`, `rounded-nav`

## Phase 3 — components follow the tokens (FR-002, FR-012, US1)

- [x] T011 `[W]` `Button`, `SegmentedControl`, inputs: use `--radius-button`/`--radius-field`
- [x] T012 `[W]` `Card`: `--card-border` width and `--radius-card`
- [x] T013 `[W]` `AppShell`: header and sidebar bands paint with `bg-chrome-gradient`/`text-on-chrome`;
      nav items carry `.nav-active` when active
- [x] T014 `[W]` `PageHeader`/section headers use `.page-title`/`.section-title` so `heading` applies

## Phase 4 — the four official themes (FR-008, FR-010, FR-011, FR-013)

- [x] T015 `[P]` `clasico.json`: author the full chrome set from today's `index.css` (byte-identity)
- [x] T016 `[P]` `impacto.json`: Modern Executive identity per `plan.md`
- [x] T017 `[P]` `elegante.json`: new Premium Professional theme
- [x] T018 `[P]` `contraste.json`: Precision High Contrast identity, series ≥ 7:1
- [x] T019 `[P]` `daltonico.json`, `monocromo.json`: chrome authored Clásico-like, keep palettes
- [x] T020 `[W]` Mirror all six files byte-identically into `backend/app/reports/themes/`
- [x] T021 `[P]` Register `elegante` in `models.PALETTE_PRESET_IDS`,
      `reports/palette.PRESET_IDS`, `services/themes.BUILTIN_IDS`, `frontend` `PaletteId` /
      `BUILTIN_THEMES` / `THEMES` / `PALETTES`, and the i18n labels (es + en)
- [x] T022 Migration `0048_official_themes`: upsert the six built-in rows, widen the
      `appearance_settings` check, no data loss, reversible

## Phase 5 — activation end to end (FR-004…FR-007)

- [x] T023 `[W]` `BrandingContext`: expose `refresh()` / `useRefreshBranding()`
- [x] T024 `[W]` `Appearance.apply()`: `await PUT` → `await refresh()` → toast; no reload; error
      keeps the previous active card
- [x] T025 `[W]` `public/theme-init.js`: replay the cached token payload before first paint

## Phase 6 — appearance page (US4, FR-017, FR-019, FR-020)

- [x] T026 `[W]` Official group + compatibility group, identity line per theme, chrome band inside
      the light/dark previews, active marker + disabled action
- [x] T027 `[P]` Spanish and English strings for the four identities and the groups

## Phase 7 — verification (US2, US3, US5, FR-014…FR-018)

- [x] T028 `[X]` `frontend/tests/unit/theme-derive.test.ts`: Clásico golden map vs today's
      `index.css`; AA for the 8 variants; the four themes differ in ≥ 5 dimensions
- [x] T029 `[X]` `frontend/tests/unit/theme-application.test.ts`: variables written, `data-*` set,
      meta theme-color, device cache round-trip
- [x] T030 `[X]` `design-guards.test.ts`: no hex in components, one theme provider, shape enums read
- [x] T031 `[X]` `backend/tests/test_themes_contract.py`: `elegante` registered, unknown refused,
      super-user only, `/api/config` exposes the choice
- [x] T032 `[X]` `frontend/tests/e2e/theme-application.spec.ts`: apply-without-reload, persistence,
      8 combinations no overflow at 375/1440, reference dashboard screenshots ×4 ×2
- [x] T033 `[X]` Report/PDF precedence unchanged: existing palette + PDF suites still green

## Phase 8 — documentation and closure

- [x] T034 `docs/THEMES.md` (the contract, the derivation, how to author one)
- [x] T035 `docs/DESIGN-SYSTEM.md`: the theme dimensions section
- [x] T036 `CHANGELOG.md` under Unreleased
- [x] T037 Commits, push, deploy, live verification of the four themes, closure report
