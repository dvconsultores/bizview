"""Workspace and integrations (feature 005, contracts/api.md): super user only; changes need
step-up confirmation (feature 004).  Integration execution controls (pause/resume, schedule
overrides, allowed-hours windows) are exposed and mutated here (feature 013, US1/T004)."""
import io
import tempfile
import zipfile
from datetime import time
from pathlib import Path
from typing import Literal

from bizview_cli import validate as wsv
from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import errors
from app.auth.deps import Auth, client_ip, recent_reauth, require_superuser
from app.config import get_settings
from app.db import DB
from app.engine import runner, schedule
from app.i18n import M, render_stored
from app.models import (
    AppUser,
    DataSource,
    IntegrationControl,
    IntegrationRun,
    IntegrationRunRequest,
    WorkspaceVersion,
)
from app.services import audit
from app.workspace import service

router = APIRouter(prefix="/api")


@router.get("/workspace")
def get_workspace(_: AppUser = Depends(require_superuser), db: Session = DB):
    active = service.active(db)
    return {"mounted": service.mounted_info(), "active": service.version_json(active),
            "previous": service.version_json(service.previous(db)),
            "report_details": service.report_details(db, active)}


@router.get("/workspace/specs")
def get_workspace_spec(key: str = Query(..., min_length=1, max_length=200),
                       _: AppUser = Depends(require_superuser), db: Session = DB):
    return service.spec_document(db, key)


@router.post("/workspace/validate")
def validate_workspace(request: Request, actor: AppUser = Depends(require_superuser),
                       db: Session = DB):
    v = service.validate_mounted(db)
    audit.record(db, "workspace_validated", actor_id=actor.id, ip=client_ip(request),
                 detail={"ok": v.ok, "errors": len(v.errors)})
    return v.to_json()


@router.post("/workspace/apply")
def apply_workspace(request: Request, actor: AppUser = Depends(require_superuser),
                    _: Auth = Depends(recent_reauth), db: Session = DB):
    return {"version": service.version_json(service.apply(db, actor, client_ip(request)))}


@router.post("/workspace/rollback")
def rollback_workspace(request: Request, actor: AppUser = Depends(require_superuser),
                       _: Auth = Depends(recent_reauth), db: Session = DB):
    return {"version": service.version_json(service.rollback(db, actor, client_ip(request)))}


def run_json(r: IntegrationRun) -> dict:
    return {"id": r.id, "kind": r.kind, "status": r.status, "started_at": r.started_at,
            "finished_at": r.finished_at, "window_start": r.window_start,
            "window_end": r.window_end, "rows": r.rows,
            "checks": [{**c, "detail": render_stored(c.get("detail"),
                        c.get("key"), c.get("params"))} for c in (r.checks or [])],
            "message": render_stored(r.message, r.message_key, r.message_params),
            "stop_requested_at": r.stop_requested_at,
            "rollups": r.rollups or {}}


def _time_str(value: time | None) -> str | None:
    return value.strftime("%H:%M") if value is not None else None


def _state(control: IntegrationControl | None) -> dict:
    """Snapshot of a control row (or defaults) for before/after comparison and audits."""
    if control is None:
        return {"paused": False, "schedule": None, "full_rebuild_cron": None,
                "window_start": None, "window_end": None}
    return {"paused": control.paused, "schedule": control.schedule,
            "full_rebuild_cron": control.full_rebuild_cron,
            "window_start": control.window_start, "window_end": control.window_end}


def control_json(definition: dict, control: IntegrationControl | None, tz: str) -> dict:
    """Single control object shape shared by GET /integrations and PUT .../control."""
    effective_cron, effective_source = schedule.effective_schedule(definition, control)
    full_crons, full_source = schedule.effective_full_crons(definition, control)
    window = None
    window_pair = None
    if control is not None and control.window_start is not None:
        window = {"start": _time_str(control.window_start), "end": _time_str(control.window_end)}
        window_pair = (control.window_start, control.window_end)
    paused = control.paused if control is not None else False
    next_fire = schedule.next_fire(effective_cron, tz, paused=paused, window=window_pair)
    return {
        "paused": paused,
        "schedule": effective_cron,
        "schedule_source": effective_source,
        "schedule_words": schedule.describe(effective_cron),
        "spec_schedule": definition["schedule"],
        "full_rebuild_cron": control.full_rebuild_cron
        if control is not None else None,
        "full_rebuild_crons": full_crons,
        "full_rebuild_source": full_source,
        "spec_full_rebuild_crons": schedule.spec_full_crons(definition),
        "window": window,
        "next_run": next_fire,
        "updated_at": control.updated_at if control is not None else None,
    }


@router.get("/integrations")
def list_integrations(_: AppUser = Depends(require_superuser), db: Session = DB):
    version = service.active_for_reads(db)
    items = []
    tz = get_settings().timezone
    integrations = version.artifacts.get("integrations", {}) if version else {}
    ids = sorted(integrations)
    sources = {s.name.lower(): s for s in db.scalars(select(DataSource))}
    controls = {c.integration_id: c for c in db.scalars(select(IntegrationControl))}
    running = dict(db.execute(select(IntegrationRun.integration_id, IntegrationRun.id)
                              .where(IntegrationRun.status == "running")
                              .order_by(IntegrationRun.id)).all())
    # Latest run and latest success of every integration in two queries, not two per row.
    last_runs = {r.integration_id: r for r in db.scalars(
        select(IntegrationRun).distinct(IntegrationRun.integration_id)
        .where(IntegrationRun.integration_id.in_(ids))
        .order_by(IntegrationRun.integration_id, IntegrationRun.id.desc()))} if ids else {}
    last_oks = dict(db.execute(
        select(IntegrationRun.integration_id, func.max(IntegrationRun.finished_at))
        .where(IntegrationRun.integration_id.in_(ids), IntegrationRun.status == "succeeded")
        .group_by(IntegrationRun.integration_id)).all()) if ids else {}
    for iid in ids:
        d = integrations[iid]["definition"]
        last = last_runs.get(iid)
        last_ok = last_oks.get(iid)
        src = sources.get(d["source"].strip().lower())
        ctl = control_json(d, controls.get(iid), tz)
        items.append({
            "id": iid, "source": d["source"], "schedule": d["schedule"],
            "datasets": sorted(d["datasets"]), "spec": d.get("spec"),
            "paused": src is None or not src.enabled,
            "last_run": run_json(last) if last else None, "last_success_at": last_ok,
            "next_run": ctl["next_run"],
            "control": ctl,
            "running_run_id": running.get(iid),
        })
    return {"items": items}


@router.get("/integrations/{integration_id}/runs")
def list_runs(integration_id: str, limit: int = Query(20, ge=1, le=200),
              _: AppUser = Depends(require_superuser), db: Session = DB):
    runs = db.scalars(select(IntegrationRun).where(IntegrationRun.integration_id == integration_id)
                      .order_by(IntegrationRun.id.desc()).limit(limit))
    return {"items": [run_json(r) for r in runs]}


class RunIn(BaseModel):
    kind: Literal["incremental", "full"] = "incremental"


@router.post("/integrations/{integration_id}/run", status_code=202)
def request_run(integration_id: str, body: RunIn, request: Request,
                actor: AppUser = Depends(require_superuser), _: Auth = Depends(recent_reauth),
                db: Session = DB):
    service.integration(db, integration_id)          # 404 unless in the active version
    req = IntegrationRunRequest(integration_id=integration_id, kind=body.kind,
                                requested_by=actor.id)
    db.add(req)
    db.flush()
    audit.record(db, "integration_run_requested", actor_id=actor.id, ip=client_ip(request),
                 detail={"integration": integration_id, "kind": body.kind})
    return {"request_id": req.id}


@router.post("/integrations/{integration_id}/runs/{run_id}/stop", status_code=202)
def stop_run(integration_id: str, run_id: int, request: Request,
             actor: AppUser = Depends(require_superuser), _: Auth = Depends(recent_reauth),
             db: Session = DB):
    """Ask a running run to stop cooperatively; finishes orphaned runs at once."""
    run = db.scalar(select(IntegrationRun).where(
        IntegrationRun.id == run_id,
        IntegrationRun.integration_id == integration_id).with_for_update())
    if run is None:
        raise errors.not_found(M("workspace.run_not_found"))
    if run.status != "running":
        raise errors.ApiError(409, "conflict", M("workspace.run_finished"))
    already_requested = run.stop_requested_at is not None
    acquired = db.scalar(
        text("SELECT pg_try_advisory_xact_lock(hashtextextended(:k, 0))"),
        {"k": runner._lock_key(integration_id)})
    if acquired:
        if run.stop_requested_at is None:
            run.stop_requested_at = func.now()
            run.stop_requested_by = actor.id
        run.status = "stopped"
        run.finished_at = func.now()
        runner.set_message(run, runner._stopped_message(actor.full_name))
        db.flush()
        audit.record(db, "integration_run_stopped", actor_id=actor.id, ip=client_ip(request),
                     detail={"integration": integration_id, "run_id": run.id,
                             "before": {"status": "running",
                                        "stop_requested": already_requested},
                             "after": {"status": "stopped", "stop_requested": True}})
        return {"run_id": run.id, "stop_requested": True, "status": "stopped"}
    if run.stop_requested_at is None:
        run.stop_requested_at = func.now()
        run.stop_requested_by = actor.id
        db.flush()
        audit.record(db, "integration_run_stopped", actor_id=actor.id, ip=client_ip(request),
                     detail={"integration": integration_id, "run_id": run.id,
                             "before": {"status": "running", "stop_requested": False},
                             "after": {"status": "running", "stop_requested": True}})
    return {"run_id": run.id, "stop_requested": True, "status": "running"}


class ControlIn(BaseModel):
    paused: bool | None = None
    schedule: str | None = None
    full_rebuild_cron: str | None = None
    window_start: time | None = None
    window_end: time | None = None


@router.put("/integrations/{integration_id}/control")
def update_control(integration_id: str, body: ControlIn, request: Request,
                   actor: AppUser = Depends(require_superuser),
                   _: Auth = Depends(recent_reauth), db: Session = DB):
    _, item = service.integration(db, integration_id)
    definition = item["definition"]
    current = db.get(IntegrationControl, integration_id)
    fields = body.model_fields_set

    before = _state(current)
    after = before.copy()

    if "paused" in fields and body.paused is not None:
        after["paused"] = body.paused
    if "schedule" in fields:
        after["schedule"] = body.schedule or None
    if "full_rebuild_cron" in fields:
        after["full_rebuild_cron"] = body.full_rebuild_cron or None
    if "window_start" in fields:
        after["window_start"] = body.window_start
    if "window_end" in fields:
        after["window_end"] = body.window_end

    schedule_errors: dict[str, str] = {}
    tz = get_settings().timezone
    for field in ("window_start", "window_end"):
        value = after.get(field)
        if value is not None and value.tzinfo is not None:
            schedule_errors[field] = "window_timezone"
    if not any(code == "window_timezone" for code in schedule_errors.values()):
        if after["schedule"]:
            try:
                after["schedule"] = schedule.validate_cron(after["schedule"], tz)
            except schedule.ScheduleError as e:
                schedule_errors["schedule"] = e.code
        if after["full_rebuild_cron"]:
            try:
                after["full_rebuild_cron"] = schedule.validate_cron(
                    after["full_rebuild_cron"], tz)
            except schedule.ScheduleError as e:
                schedule_errors["full_rebuild_cron"] = e.code
        try:
            window_pair = schedule.validate_window(after["window_start"], after["window_end"])
        except schedule.ScheduleError as e:
            schedule_errors["window_start"] = schedule_errors["window_end"] = e.code
        else:
            after["window_start"], after["window_end"] = (
                window_pair if window_pair else (None, None))

    if schedule_errors:
        first_field = next(iter(schedule_errors))
        first_code = schedule_errors[first_field]
        if first_code == "invalid_cron":
            raise errors.validation(schedule_errors, M("workspace.schedule_invalid"))
        if first_code == "too_frequent":
            raise errors.validation(schedule_errors, M("workspace.schedule_min_frequency"))
        if first_code == "too_long":
            raise errors.validation(schedule_errors, M("schedule.too_long"))
        if first_code == "window_timezone":
            raise errors.validation(
                schedule_errors,
                M("workspace.schedule_no_timezone"))
        if first_code in ("window_incomplete", "window_empty"):
            raise errors.validation(schedule_errors, M("workspace.window_invalid"))
        raise errors.validation(schedule_errors)

    if before == after:
        ctl_row = current
        return {"control": control_json(definition, ctl_row, tz)}

    control = current
    if control is None:
        control = IntegrationControl(integration_id=integration_id)
        db.add(control)
    control.paused = after["paused"]
    control.schedule = after["schedule"]
    control.full_rebuild_cron = after["full_rebuild_cron"]
    control.window_start = after["window_start"]
    control.window_end = after["window_end"]
    control.updated_by = actor.id
    control.updated_at = func.now()
    db.flush()

    ip = client_ip(request)
    if before["paused"] is False and after["paused"] is True:
        audit.record(db, "integration_paused", actor_id=actor.id, ip=ip,
                     detail={"integration": integration_id,
                             "before": {"paused": False}, "after": {"paused": True}})
    elif before["paused"] is True and after["paused"] is False:
        audit.record(db, "integration_resumed", actor_id=actor.id, ip=ip,
                     detail={"integration": integration_id,
                             "before": {"paused": True}, "after": {"paused": False}})

    sched_before = {k: _time_str(v) if k in ("window_start", "window_end") else v
                    for k, v in (("schedule", before["schedule"]),
                                 ("full_rebuild_cron", before["full_rebuild_cron"]),
                                 ("window_start", before["window_start"]),
                                 ("window_end", before["window_end"]))}
    sched_after = {k: _time_str(v) if k in ("window_start", "window_end") else v
                   for k, v in (("schedule", after["schedule"]),
                                ("full_rebuild_cron", after["full_rebuild_cron"]),
                                ("window_start", after["window_start"]),
                                ("window_end", after["window_end"]))}
    if sched_before != sched_after:
        audit.record(db, "integration_schedule_changed", actor_id=actor.id, ip=ip,
                     detail={"integration": integration_id, "before": sched_before,
                             "after": sched_after})

    return {"control": control_json(definition, control, tz)}


@router.get("/workspace/versions/{version_id}/export.zip")
def export_version(version_id: int, _: AppUser = Depends(require_superuser), db: Session = DB):
    """A version as a v2 workspace folder (features 014 and 020): root `bizview.yaml`,
    `projects/<slug>/…` per owning project and the lock of that tree, e.g. to commit it."""
    from app.projects import compose

    version = db.get(WorkspaceVersion, version_id)
    if version is None:
        raise errors.not_found(M("workspace.version_not_found"))
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "bizview.yaml").write_text(compose.manifest_text(version), encoding="utf-8")
        for slug, tree in compose.version_projects(version).items():
            compose.write_tree(tree, root / "projects" / slug)
        result = wsv.validate(root)
        wsv.write_lock(root, result.lock if result.lock is not None else version.lock)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                zf.write(path, path.relative_to(root).as_posix())
    return Response(content=buffer.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition":
                             f'attachment; filename="bizview-workspace-v{version.id}.zip"'})
