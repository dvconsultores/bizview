# Quickstart — 053-parameters-sheet

**Feature**: Parámetros into the same sheet as Filtros · **Date**: 2026-11-04

## Automated gates

```bash
cd frontend
npx tsc -b                      # types, including the new props
npx vitest run                  # every unit suite (report sheet, chips, export, i18n gates)
```

Removal gate (must print nothing):

```bash
grep -rn "param-bar\|ParamBar\|Generar reporte\|exportSection" src
```

Playwright, when the e2e stack is up (`frontend/playwright.config.ts`):

```bash
npx playwright test tests/e2e/report-params.spec.ts tests/e2e/appearance.spec.ts \
                    tests/e2e/autorefresh.spec.ts
```

## Manual checks

1. **One sheet, two tabs.** Open `/r/ventas`. Press **Parámetros**: the right sheet appears with
   `Filtros | Parámetros`, Parámetros selected, the KPI row still visible to its left. Press
   **Filtros**: the same panel switches tab (no second panel). Press **Filtros** again: it closes and
   focus returns to the button.
2. **Rows, in order.** In Parámetros: Período, Comparar con, Frecuencia de actualización, Paleta,
   Tema del reporte — one per row, label above. Pick **Mes anterior**: exactly one data request (the
   network tab shows one `/data` call for the burst) and the numbers update behind the sheet.
3. **Custom range.** Período → **Personalizado**; Desde/Hasta appear under it; clearing one sends no
   request and the sheet says nothing until both are valid.
4. **Paleta.** The row shows eight colour swatches of the chosen theme and the first option is
   **Usar la de la instalación**. Choosing `contraste` repaints the dashboard and adds `theme=contraste`
   to the URL.
5. **Chips and reload.** Close with **Listo**: under the meta line there is `Período: Mes anterior`,
   `vs: período anterior`, `Paleta: contraste`, next to any filter chips. Reload: all three survive.
   Remove `Paleta: contraste`: the chip disappears, the URL loses `theme` and the dashboard repaints
   with the declared theme.
6. **Export is an action.** Open `⋯`: **Descargar PDF**, **Descargar CSV** and the caption
   "Se exporta la selección aplicada." Download CSV: the file matches the filtered selection. While
   the report loads, the caption says so and CSV is absent.
7. **Phones.** At 375 px both tabs open a bottom sheet of ≤72 % height with the tab strip at the top,
   the dashboard visible above, no horizontal scroll; Esc closes and focus returns.
8. **Keyboard and motion.** With the sheet open, ArrowLeft/ArrowRight change tab, Tab enters the
   panel, Esc closes. With `prefers-reduced-motion: reduce`, the sheet opens without transition.

## Shared view

Open a share link (`/s/<token>`) of a report with filters: the same two tabs, Parámetros offering
period and comparison only, no palette/refresh/mode row and no export block inside the sheet.
