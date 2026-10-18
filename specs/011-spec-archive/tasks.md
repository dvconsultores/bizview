---
description: "Task list for feature 011 — Spec archive in the installation"
---

# Tasks: Spec archive in the installation

**Roles**: DeepSeek writes code; Claude audits/converges. Run after feature 010 (both touch Workspace.tsx).

## Phase 1: User Story 1 — Read the spec behind what is running (P1)

- [X] T001 [US1] backend/app/workspace/service.py `_artifacts`: store `documents` = text of `spec.md`, `plan.md`, `tasks.md` (UTF-8) per entry in `specs[entry.key]`; texts must correspond to the hashed bytes in the lock
- [X] T002 [US1] backend/app/api/workspace.py: `GET /api/workspace` strips `documents` from the specs it returns; new `GET /api/workspace/specs?key=` (same super-user dependency as the other workspace routes) returning `{key, folder, title, status, sha256, documents | null}` from the active version, 404 `not_found` for unknown keys
- [X] T003 [P] [US1] Backend tests (follow the existing workspace tests' fixtures): apply stores documents whose SHA-256 equals the lock entry; GET /api/workspace has no documents; GET specs returns texts; unknown key 404; admin (non-super) 403; a version row without documents returns `documents: null`; rollback serves the previous version's texts
- [X] T004 [US1] frontend/src/api/types.ts + frontend/src/i18n/es.ts (`workspace.specs` strings: "Especificaciones", "Ver", "Especificación", "Plan", "Tareas", "Texto no disponible para esta versión") + frontend/src/pages/admin/Workspace.tsx: specs card and View per plan.md (no modal, tokens only, wraps at 375 px)
- [X] T005 [US1] E2E step in the spec that applies a workspace: open Espacio de trabajo → "Ver" on a report → view shows text containing "**Spec type**: report"; back closes it

## Phase 2: Polish

- [X] T006 CHANGELOG.md Unreleased entry; run backend tests for workspace + the touched e2e; `/speckit-converge`
