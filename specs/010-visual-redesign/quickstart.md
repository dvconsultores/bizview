# Quickstart: validate feature 010

1. Open BizView and app.example-customer.com side by side at 1920 × 1080: compare shell (sidebar
   gradient block, filled active pill, white top bar, grey-blue canvas), header cards, tiles,
   tables, filled inputs, buttons (SC-001).
2. Home: banner "Bienvenido de nuevo, <nombre>" with today's date in Spanish; dashboards as cards.
3. Administración: hub cards + summary tiles; Usuarios: header card with count, toolbar, table with
   chips and pills; Nuevo usuario: filled inputs, required marks.
4. A report: breadcrumb, header card, KPI tiles, steel-teal charts.
5. Toggle dark theme and repeat 2–4.
6. 320/375 px: every screen, no horizontal scroll; bottom navigation present.
7. `cd frontend && npm test && npm run build && npm run check:compat && npx playwright test`
   (all green; `design.spec.ts` included).
