---
description: "Task list for feature 015 — Dashboard auto-refresh and TV mode"
---

# Tasks: Dashboard auto-refresh and TV mode

**Roles**: DeepSeek writes code; Claude audits/converges. Run after feature 012 (params panel).

- [X] T001 [US1] backend/app/api/reports.py `GET /api/reports/{id}/version` + tests
- [X] T002 [P] [US1] frontend/src/lib/autoRefresh.ts hook + frontend/tests/unit/auto-refresh.test.ts
- [X] T003 [US1] ReportView + params panel control + status line; refresh keeps selection, draft and scroll
- [X] T004 [US2] TV mode: URL flag, AppShell hide flag, TvLayout, fullscreen enter/exit, Esc
- [X] T005 frontend/tests/e2e/autorefresh.spec.ts (data-mode refresh, interval mode with clock, TV mode) ; CHANGELOG.md
- [X] T006 Run backend report tests + frontend suites; `/speckit-converge`

---

## Phase 2: Convergence (review polish)

- [X] T007 TV mode: hide shell chrome before first paint (useLayoutEffect or read the tv flag synchronously) so the sidebar/header never flash; no extra page scrollbar (TvLayout height accounts for main padding); KPI labels enlarged in TV mode (StatTile size prop); Esc exits even when the browser does not consume it in fullscreen
- [X] T008 autoRefresh: on tab visible in data mode, check only if the last check is older than the interval; skipped refreshes (load in flight / query changed) are not reported as "actualizado"; unit tests call stop() (no leaked listeners)
