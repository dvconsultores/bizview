# Quickstart — seeing and proving the fix

```bash
cd frontend
npx vitest run tests/unit/segmented.test.tsx tests/unit/appearance-page.test.tsx \
                tests/unit/help-page.test.tsx tests/unit/design-guards.test.ts
```

Expected: the segmented control's options share one grid row and exactly one is checked; the theme
grid declares its column progression; the Help panes are bounded and scrollable; the guards find no
page with a narrow root.

## See it

```bash
npm run dev          # or: npm run build && npm run preview
```

1. **Perfil** — `Sistema / Claro / Oscuro` on one row; pick Claro, reload, still Claro.
2. **Account menu** (top-right) — identity, then the two segmented controls, then the links; on a
   375 × 560 window the menu scrolls instead of overflowing.
3. **Administración → Apariencia** — at 1440 px three columns filling the container; at 768 px two;
   at 375 px one. Cards in a row have the same height.
4. **Ayuda** — at 1440 px scroll a long article: the topic list does not move and the window does not
   scroll. At 375 px open a topic: the list is replaced, Back brings it back with the search intact.

## Prove it in a browser

```bash
cd frontend
npx playwright test tests/e2e/design-system.spec.ts
```

That spec walks the six screens at 375 and 1440 px, in light and dark, asserts there is no horizontal
overflow and that the end of a long article is reachable, and writes the before/after screenshots to
`docs/assets/design-system/`.
