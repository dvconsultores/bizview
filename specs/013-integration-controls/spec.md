# Feature Specification: Integration controls (start, stop, frequency)

**Feature Branch**: `013-integration-controls`

**Created**: 2026-10-01

**Status**: Implemented (closed 2026-10-08, full suites green)

**Input**: Owner, 2026-10-01: "ETL table stored, define stop, start, frequency." The super user
controls each integration's execution from BizView, stored in the database: pause/resume it,
stop a run in progress, change how often it runs and when it may run — without editing the
workspace spec.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pause and resume an integration (Priority: P1)

The super user opens Administración → Integraciones and pauses an integration (e.g. during a
maintenance window at the source). It stops being scheduled; its data stays as it is and reports
keep showing it with its last update time. Later they resume it and the schedule continues.

**Why this priority**: the most frequent operational need; today the only way is to change the spec.

**Independent Test**: pause an integration, wait past its next scheduled time, confirm no run
happened and the data is unchanged; resume, confirm the next run happens on schedule.

**Acceptance Scenarios**:

1. **Given** an active integration, **When** the super user presses "Pausar", **Then** its state shows
   "Pausada", no scheduled run starts while paused, and "Próxima ejecución" shows "—".
2. **Given** a paused integration, **When** they press "Reanudar", **Then** its state shows "Activa"
   and "Próxima ejecución" shows the next time per its frequency.
3. **Given** a paused integration, **When** they press "Ejecutar ahora", **Then** one manual run
   happens (manual runs are allowed while paused) and the integration stays paused.
4. **Given** the worker is running, **When** an integration is paused or resumed, **Then** the change
   takes effect within 1 minute without restarting anything.

---

### User Story 2 - Stop a run in progress (Priority: P1)

A run is taking too long or was started by mistake. The super user presses "Detener"; the run
stops, is recorded as "Detenida" with who stopped it, and the published data is unchanged.

**Why this priority**: a long run blocks the next ones and loads the source; stopping it safely is
essential operational control.

**Independent Test**: start a long manual run, press "Detener", check the run ends as "Detenida"
within a short time and the dataset is unchanged.

**Acceptance Scenarios**:

1. **Given** a running run, **When** the super user presses "Detener", **Then** the run ends within
   30 seconds with status "Detenida", the reason "detenida por <nombre>", and no data of that run is
   published.
2. **Given** no run in progress, **When** the integration is shown, **Then** "Detener" is not offered.

---

### User Story 3 - Change frequency and allowed hours (Priority: P2)

The super user changes how often an integration runs ("Cada 15 minutos", "Cada 30 minutos",
"Cada hora", "Diaria a las 03:00", or a custom expression) and optionally restricts the hours in
which scheduled runs may start (e.g. 06:00–22:00). The spec's own schedule remains visible and
can be restored with one action.

**Why this priority**: tuning freshness against load on the source; depends on the stored control
of US1.

**Independent Test**: set "Cada 15 minutos" with window 06:00–22:00, check next execution times;
restore the spec's schedule.

**Acceptance Scenarios**:

1. **Given** an integration, **When** the super user selects a frequency preset, **Then** "Próxima
   ejecución" updates and scheduled runs follow it within 1 minute.
2. **Given** a custom expression, **When** it is invalid or more frequent than every 5 minutes,
   **Then** it is refused with a clear message and nothing changes.
3. **Given** an allowed-hours window, **When** a scheduled time falls outside it, **Then** no run starts
   at that time (manual runs are not restricted).
4. **Given** a changed frequency, **When** they choose "Usar la programación del spec", **Then** the
   override is removed and the spec's schedule applies again.
5. **Given** the daily full rebuild declared by the spec, **When** the frequency is overridden, **Then**
   the full rebuild keeps its own schedule unless it is also overridden ("Recarga completa").

---

### Edge Cases

- A new workspace version is applied: controls of integrations that still exist are kept; controls of
  removed integrations are kept but inactive (shown nowhere) and reapply if the integration returns.
- Stop requested exactly when the run finishes: the run keeps its real final status.
- Pausing while a run is in progress does not stop it (Detener does).
- Time zone: frequencies and windows use the installation time zone (as schedules do today).
- Overnight windows (22:00–06:00) are allowed.
- Every change (pause, resume, stop, frequency, window, restore) is recorded in the audit log with the
  user and the before/after values.

## Requirements *(mandatory)*

- **FR-001**: The system MUST store per integration: paused (yes/no), optional frequency override,
  optional full-rebuild override, optional allowed-hours window, who changed it last and when.
- **FR-002**: Only the super user MAY change controls or stop runs; changes MUST be audited.
- **FR-003**: Scheduled runs MUST honour paused state, frequency override and window; manual runs MUST
  ignore pause and window.
- **FR-004**: The worker MUST apply control changes within 1 minute without restart.
- **FR-005**: "Detener" MUST end a running run within 30 seconds, record it as stopped with who stopped
  it, and publish nothing from it.
- **FR-006**: Frequencies MUST be validated (valid expression, at most once every 5 minutes) and shown
  in Spanish words when they match a preset.
- **FR-007**: The Integraciones screen MUST show per integration: state (Activa, Pausada, Ejecutando),
  effective frequency (and whether it comes from the spec or an override), allowed hours, next
  execution, last run result, and the actions Pausar/Reanudar, Ejecutar ahora, Detener, Cambiar
  frecuencia.
- **FR-008**: Spanish UI, feature-010 look, no modals (feature 009 views for editing frequency),
  mobile-first, WCAG AA.

## Success Criteria *(mandatory)*

- **SC-001**: 0 scheduled runs start while an integration is paused (over a test with a 1-minute
  schedule paused for 5 minutes).
- **SC-002**: A stop request ends the run within 30 seconds in 100% of tests, with data unchanged.
- **SC-003**: Control changes take effect within 1 minute in 100% of tests, without restart.
- **SC-004**: 100% of control changes appear in the audit log.

## Assumptions

- Controls are operational settings of the installation, not part of the spec; the spec stays the
  default and the documented intent.
- "Stop" is cooperative: the run checks for a stop request between blocks/batches (as it checks its
  time limit today).
