# Quickstart — reproduce and measure

Feature 059. The two screens are frontend-only; no installation, no database.

## 1. The suites that prove it

```bash
cd frontend
npx tsc --noEmit
npx vitest run tests/unit/sign-in.test.tsx tests/unit/report-sheet-params.test.tsx
```

Expected: green. The unit tests assert the compact classes, the single label per control, the
provider row, the history entry, and that **Listo** only closes.

## 2. The browser proofs

```bash
cd frontend
npx playwright test tests/e2e/mobile-first.spec.ts --project=chromium-375
```

The spec measures, at 360 / 393 / 414 / 768 / 1280 and in both themes:

- `/ingresar` at 393 × 640: every control inside the viewport without scrolling; the language
  toggle's box does not intersect the product name's;
- the sheet at 393: `height === window.innerHeight`, the last control above the footer, Back closes
  it, **Limpiar** restores the defaults;
- no element wider than `innerWidth` at 360 on `/`, `/ingresar`, `/r/<id>`, `/proyectos`;
- axe clean on both screens.

(The repository keeps no image baselines, so "snapshots" are these geometry and accessibility
assertions.)

## 3. By hand

1. `npm run dev`, open the app with the browser device toolbar at 393 × 851 (dark theme).
2. `/ingresar`: the toggle sits under the header; the whole form, **Ingresar** and both providers are
   on one screen; focusing the password field pans the page so the button stays visible.
3. `/r/<id>` → **Parámetros**: the sheet covers the screen, the four controls fit, the footer sits
   below the last one, the palette and theme scroll horizontally, and the phone's Back closes it.
4. Widen past 640 px: the sheet becomes the 85 % bottom sheet, then today's 360 px side sheet at 1024.
