---
description: "Task list for feature 012 — Report parameters panel"
---

# Tasks: Report parameters panel

**Roles**: DeepSeek writes code; Claude audits/converges. Start after feature 010 is complete
(ReportView and report components are restyled there). Rules: tokens only, no modals, Spanish,
mobile-first, accessible names stable.

## Phase 1: Foundational

- [X] T001 backend/app/engine/report.py + backend/app/api/reports.py: multi-value filters per plan.md (repeated `filter.<id>`, bound `IN`, ≤ 50 values → 422 `too_many_values`, `multi_items()` everywhere incl. PDF and narrative, cache key with sorted values); filters endpoint `q` search (bound ILIKE, escaped) + `truncated`
- [X] T002 [P] Backend tests: two values = sum of each alone (SC-003); old single-value link same result; unknown filter ignored; 51 values → 422; `q` narrows and escapes `%`/`_`; values with quotes/semicolons are bound (no SQL error, no injection); PDF and narrative honour multi-values; cache distinguishes selections
- [X] T003 [P] frontend/src/lib/reportQuery.ts + frontend/tests/unit/report-query.test.ts (round-trip, repeated params, legacy single value, defaults)
- [X] T004 [P] frontend/src/lib/csv.ts + frontend/tests/unit/csv.test.ts (BOM, `;`, quoting of `;`/`"`/newlines, dot decimals, ISO dates, header labels)

## Phase 2: User Story 1 — Parameters form (P1) 🎯

- [X] T005 [US1] frontend/src/components/MultiSelect.tsx (accessible searchable multi-select per plan) + unit tests
- [X] T006 [US1] frontend/src/components/report/ParamsForm.tsx (sections, draft/applied, pending count, validation, Aplicar/Limpiar) + frontend/tests/unit/params-form.test.tsx (three edits + apply → one onApply call; invalid custom range blocks apply; Limpiar resets to defaults)
- [X] T007 [US1] frontend/src/components/report/ParamsPanel.tsx + frontend/src/pages/ReportView.tsx desktop layout (panel + content, collapse remembered), URL = applied state via reportQuery

## Phase 3: User Story 2 — Context block (P1)

- [X] T008 [US2] frontend/src/components/report/ContextBlock.tsx in ReportView (period + dates, comparison + dates, freshness, removable chips → one reload)

## Phase 4: User Story 3 — Export (P2)

- [X] T009 [US3] Exportar section (PDF via existing download; CSV of all table/ranking views as one file with a title line per table) + frontend/src/components/report/CardMenu.tsx "Descargar CSV" on DataTable/RankingTable cards

## Phase 5: User Story 4 — Phones (P2)

- [X] T010 [US4] ReportView < lg: "Filtros (n)" button opening a `View` with ParamsForm; back discards draft; apply closes and reloads once

## Phase 6: Polish

- [X] T011 frontend/tests/e2e/report-params.spec.ts (desktop: edit 3 params → apply → one data request, URL, reload keeps; multi-brand; chip removal; Limpiar; CSV download content checks; phone: Filtros view back/apply; axe both themes; no horizontal scroll) and update existing reporting/theme e2e for the new layout
- [X] T012 CHANGELOG.md; run backend report tests + frontend suites; `/speckit-converge`

---

## Phase 7: Convergence

- [X] T013 frontend/src/components/MultiSelect.tsx: never let the combobox reference a missing listbox — always render the listbox (empty/loading/error/"Sin valores en el período"/"Sin coincidencias" as non-option status text outside it) or drop `aria-controls` while it is not rendered; add an axe check of an open, empty/loading MultiSelect in a unit or e2e test, per FR-008 / SC-005 (partial)
- [X] T014 frontend/src/lib/reportQuery.ts `compareChoices`: offer exactly the report's `compare.allowed` (do not add "none" unless allowed); ParamsForm shows the field read-only when one choice remains; unit tests for `[previous_year]`, per spec Edge Cases / US1/AC1 (partial)
- [X] T015 ParamsForm: separate sections "Período" and "Comparar con" (headings in frontend/src/i18n/es.ts), per FR-001 / US1/AC1 (partial)
- [X] T016 ContextBlock: add "Consultado por <nombre>" (signed-in user's full name), per spec Design decision (partial)
- [X] T017 backend/app/reports/pdf.py: meta lines "Período: <nombre> (<fechas>)" and "Comparado con: <fechas> | Sin comparación" matching the context block; test in backend/tests/test_reports_params.py, per US2/AC3 (partial)
- [X] T018 Keep the context-block "Descargar PDF" quick action (phones have no panel) but take its label from frontend/src/i18n/es.ts; record the decision in plan.md, per FR-006 (unrequested → justified)
- [X] T019 frontend/src/api/types.ts `ReportData.filters: Record<string, string[]>`, per plan "Backend" (partial)
