# Implementation Plan: Spec archive in the installation

**Branch**: `011-spec-archive` | **Date**: 2026-10-01 | **Spec**: [spec.md](./spec.md)

## Summary

On apply, put the text of each entry's `spec.md`/`plan.md`/`tasks.md` into the existing
`workspace_version.specs` JSONB (`specs[key].documents`), served by a new super-user endpoint and
shown in Espacio de trabajo through a feature-009 view. No table change (JSONB), no new library.

## Technical Context

Python 3.12 / FastAPI / SQLAlchemy (backend), TypeScript / React 19 (frontend). Storage: existing
`public.workspace_version.specs` (JSONB). Testing: pytest on DATABASE_URL_BI (`app_test_*`),
Vitest, Playwright (one step in an existing workspace e2e).

## Constitution Check

All PASS: product schema unchanged (JSONB content only, documented here); JSON API; super-user
only (same guard as the other workspace routes); no secrets in specs (workspace rule); views not
modals (feature 009).

## Design

- `app/workspace/service.py::_artifacts`: `specs[entry.key]["documents"] = {name: text}` for
  `SPEC_FILES` read from the validated spec folder (UTF-8; the bytes are the ones hashed into the
  lock — reuse what validation read when available, otherwise read the same paths once).
- `GET /api/workspace` keeps returning spec metadata only (documents stripped).
- New `GET /api/workspace/specs?key=<entry key>` (super user): `{key, folder, title, status,
  sha256, documents: {"spec.md": str, "plan.md": str, "tasks.md": str} | null}` from the active
  version; unknown key → 404 `not_found`.
- Frontend `pages/admin/Workspace.tsx`: "Especificaciones" card listing entries (type, title,
  status pill); "Ver" opens a `View` with tabs/segmented control spec/plan/tareas and the text in a
  `whitespace-pre-wrap break-words` block; message "Texto no disponible para esta versión" when
  `documents` is null.

## Structure

backend/app/workspace/service.py, backend/app/api/workspace.py, backend/tests/test_workspace*.py;
frontend/src/api/types.ts, frontend/src/pages/admin/Workspace.tsx, frontend/src/i18n/es.ts,
frontend/tests/e2e/reporting.spec.ts (or the spec that applies a workspace).
