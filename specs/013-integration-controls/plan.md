# Implementation Plan: Integration controls

**Branch**: `013-integration-controls` | **Date**: 2026-10-01 | **Spec**: [spec.md](./spec.md)

## Summary

New table `integration_control` (migration `0008_integration_control`) + `integration_run.stop_*`
columns and status `stopped`; worker reloads its jobs when the active version OR the controls
fingerprint change (checked every loop, ≤ 1 min); scheduled jobs check pause/window at fire time;
runner checks a stop flag between blocks/batches; super-user API + Integraciones UI.

## Technical Context

Python 3.12 / FastAPI / SQLAlchemy / Alembic / APScheduler (backend, worker); React 19 / Tailwind
(frontend). Storage: BI database `public`. Tests: pytest (`app_test_*`), Vitest, Playwright.

## Constitution Check

PASS: product schema via Alembic (0008); super-user only + audit; spec remains default intent
(principle IX) — controls are operational overrides recorded and visible; no modals; tokens only.

## Design

### Data
- `integration_control(integration_id text PK, paused bool NOT NULL default false,
  schedule text NULL, full_rebuild_cron text NULL, window_start time NULL, window_end time NULL,
  updated_by bigint FK app_user NULL, updated_at timestamptz NOT NULL default now())`;
  CHECK (window_start IS NULL) = (window_end IS NULL).
- `integration_run`: add `stop_requested_at timestamptz NULL`, `stop_requested_by bigint NULL`;
  `RUN_STATUSES` += `stopped`; audit event types += `integration_paused`, `integration_resumed`,
  `integration_schedule_changed`, `integration_run_stopped` (follow the audit type list pattern in
  migrations 0004/0006).

### Worker
- `schedules(version, controls)` uses override `schedule` / `full_rebuild_cron` when set.
- `reload()` compares `(version_id, controls_fingerprint)`; fingerprint = sorted
  (integration_id, updated_at) of controls; called each loop iteration (existing loop cadence).
- `run_scheduled` re-reads the control at fire time: skip if paused or outside the window
  (window in installation TZ, overnight supported); manual requests ignore both.

### Runner
- Stop flag check alongside the deadline check (bulk COPY blocks and row batches): reads
  `integration_run.stop_requested_at` at most every 2 s; when set → raise a `RunStopped`
  → transaction rolled back, run status `stopped`, error "detenida por <nombre>".

### API (super user, CSRF as other routes)
- `GET /api/integrations` adds `control` {paused, schedule, schedule_source: spec|override,
  full_rebuild_cron, window, next_run} and `running_run_id`.
- `PUT /api/integrations/{id}/control` body {paused?, schedule? (null = spec), full_rebuild_cron?,
  window_start?, window_end?}; validation: cron parses, min interval ≥ 5 min (two consecutive fire
  times), window both-or-none → 422 with field codes; audited with before/after.
- `POST /api/integrations/{id}/runs/{run_id}/stop` → 202; 409 if not running.

### UI (`pages/admin/Integrations.tsx`)
- Card per integration: state pill (Activa / Pausada / Ejecutando), frequency in words (preset
  mapping: */15, */30, 0 *, daily HH:MM) + "(spec)" / "(personalizada)", allowed hours, next run,
  last run; actions Pausar/Reanudar, Ejecutar ahora, Detener (when running), "Cambiar frecuencia"
  → `View` with a form: preset radio + custom cron input, optional window (Desde/Hasta time
  inputs), full-rebuild override, "Usar la programación del spec", Guardar.
