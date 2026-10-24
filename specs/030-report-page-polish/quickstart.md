# Quickstart — validating report page polish

A run guide, not an implementation guide. Each scenario names the success criterion it proves. Shapes
live in [contracts/](./contracts/); fields in [data-model.md](./data-model.md).

## Prerequisites

- A database the app may write (`DATABASE_URL_BI`) with `SUPER_USER_EMAIL` / `SUPER_USER_PASSWORD` in
  `.env`; `SECURITY_PROFILE=private`.
- The seeded demo workspace (report `Ventas y facturación`) — `python starter.py` on a fresh
  install does migrations (including `0027`) + bootstrap + seed and starts backend and frontend.

```bash
python starter.py                 # http://localhost:5173, sign in as the super user
cd frontend && npm test           # unit suite, includes the palette gate
cd backend  && uv run pytest      # PDF + API suites
cd cli      && uv run pytest      # report-definition schema/checker suites
cd frontend && npm run e2e        # Playwright, 320/375 px, Chromium/Firefox/WebKit
```

## Scenario 0 — the palette gate (SC-004, FR-010)

```bash
cd frontend && npx vitest run tests/unit/palette-presets.test.ts
```

Expected: 5 presets × 2 themes pass every rule of
[contracts/palette-preset.md](./contracts/palette-preset.md) (contrast, ΔE, semantic pair, badge text,
subtle grid), the backend mirror is byte-identical, and no report-definition fixture in the repo
contains a hex colour. Delete one `series` entry from a preset → the test fails and names the role.

## Scenario 1 — width (US1, SC-001)

1. Open `/tableros` at 1440 px and note the content width of the list.
2. Open `/r/<report>` at the same viewport: the content spans the same width (both inside
   `max-w-screen-2xl` with the app gutters). Repeat at 1920 and 1280 px.
3. Set the viewport to 375 px: 16 px gutters, no horizontal scrollbar.
4. Status → Modo TV: full width, chrome hidden, palette applied.
5. Open the same report through `/s/<token>`: the shared header and main use the same container.

## Scenario 2 — parameters out of the way (US2, SC-002)

1. At 375×667 the first screen shows title, meta line and at least two KPI tiles — no parameters card.
2. "Parámetros" opens the sheet on its Parámetros tab; change the period and the KPIs update with the
   sheet open; "Listo" closes it.
3. The actions row shows Descargar PDF, Compartir, Enviar por correo, Envíos programados, Modo TV as
   icon+label on desktop and inside "⋯" on a phone; Tab reaches every one, Esc closes the menu.
4. "Consultado por" appears nowhere on screen; download the PDF and confirm it is in the PDF footer.

## Scenario 3 — filters as a sheet with chips (US3, SC-003)

1. "Filtros" → the sheet opens on Filtros: one control per declared filter, search inside a long
   list, "Limpiar", "Listo".
2. Pick a value: the URL gains the filter, a chip appears under the meta line (`Estatus: pagada ×`),
   and the charts update in under 500 ms with the sheet still open (network panel: one `/data`
   request per 250 ms burst).
3. Remove the chip: the chart returns. Reload the URL: the same state is restored. Share the URL in a
   second tab: same numbers.
4. At 375 px the sheet is a bottom sheet with a drag handle, the dashboard visible above it; swiping
   down or Esc closes it and focus is back on "Filtros".
5. With the OS "reduce motion" preference on, no slide and no chart transition happens.

## Scenario 4 — shared view theme (US4, SC-005)

1. Create a share link in the report (Compartir) with "Abrir en tema oscuro"; open it in a clean
   browser profile: it opens dark.
2. Toggle to Claro: instant, no reload; reload the page: still light (viewer wins).
3. Clear `localStorage` and reload: dark again (the link's first-load theme).
4. Download the PDF from the shared view in dark mode: the PDF is light.

## Scenario 5 — presets, installation and per report (US5)

1. Administración → Apariencia: five preset cards with a live mini dashboard (KPI + bar + line) in
   both themes; pick "Contraste alto" and save.
2. Open the report: every report without an override now uses Contraste alto (charts, KPI numerals,
   delta badges, PDF).
3. In the report's Parámetros tab set "Paleta" to "Impacto" and save: only this report changes, and
   the PDF follows; the change is a new workspace version.
4. Compare `Ventas y facturación` with `impacto` vs today side by side in both themes for the owner's
   one-time approval (SC-007, recorded in the PR).
5. Set an installation brand primary that clashes with the preset: interface buttons change, chart
   series do not.

## Scenario 6 — declare an unknown preset (IX)

```bash
cd cli && uv run bizview validate /path/to/workspace
```

With `layout.theme.palette: neon` in a report definition the checker reports a `layout_range` issue on
`layout/theme/palette` listing the five ids; with a hex value anywhere in the layout it still reports
the colour-literal issue (026 FR-005 unchanged). The same rules are covered by
`cli/tests/test_report_layout.py`.
