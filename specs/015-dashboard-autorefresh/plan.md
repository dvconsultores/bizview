# Implementation Plan: Dashboard auto-refresh and TV mode

**Branch**: `015-dashboard-autorefresh` | **Date**: 2026-10-01 | **Spec**: [spec.md](./spec.md)

## Design

- Backend: `GET /api/reports/{id}/version` → `{data_version, updated_at}` using
  `engine.data_version(db, ctx)` (same access checks as `/data`); no aggregation; tests (access,
  value changes after a run).
- Frontend:
  - `lib/autoRefresh.ts`: hook `useAutoRefresh({reportId, mode, onRefresh})` — `visibilitychange`
    aware, polls `/version` every 60 s in "data" mode and calls `onRefresh` when `data_version`
    changes; interval mode uses timers; offline → retry with backoff and status "offline";
    persisted mode in `localStorage["bizview.autorefresh.<id>"]` (try/catch).
  - ReportView: "Actualización automática" control in the 012 params panel (Select: Desactivada,
    Al llegar datos nuevos, Cada 1/5/15/60 min) and a status line ("Actualización automática ·
    última hh:mm"); refresh = re-fetch data with the applied selection, preserving scroll.
  - TV mode: URL flag `tv=1`; `ReportView` renders a `TvLayout` (no shell nav/footer — AppShell
    reads a context flag to hide them), large typography tokens, header with title/period/freshness,
    "Salir del modo TV" button; Fullscreen API on enter (ignored if refused); Esc exits.
- Tests: Vitest for the hook (fake timers, visibility, version change → one refresh); Playwright
  `autorefresh.spec.ts`: data-mode refresh after triggering a manual integration run in the e2e
  backend (or a test hook that bumps the data version), TV mode layout and exit.
