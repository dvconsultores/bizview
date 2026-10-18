"""Administration routes: users, dashboard grants, audit (contracts/api.md)."""
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, aliased

from app.api.schemas import CreateUserIn, GrantsIn, ResetPasswordIn, UpdateUserIn, user_json
from app.auth import sessions
from app.auth.deps import (
    Auth,
    client_ip,
    current_auth,
    ensure_recent_reauth,
    recent_reauth,
    require_admin,
    require_superuser,
)
from app.db import DB
from app.errors import not_found, validation
from app.i18n import M, t
from app.models import (
    AUDIT_KINDS,
    AppUser,
    AuditEvent,
    Dashboard,
    DashboardAccess,
    DataSource,
    IntegrationRun,
    TelegramLink,
)
from app.security import mfa
from app.services import audit, dashboards, users
from app.workspace import service as workspace_service

router = APIRouter(prefix="/api/admin")


def _target(db: Session, user_id: int) -> AppUser:
    target = users.get(db, user_id)
    if target is None:
        raise not_found(M("users.not_found"))
    return target


def _dashboards_for(db: Session, target: AppUser) -> list[dict]:
    granted = set(db.scalars(select(DashboardAccess.dashboard_id)
                             .where(DashboardAccess.user_id == target.id)))
    rows = db.scalars(select(Dashboard).where(Dashboard.status != "hidden")
                      .order_by(Dashboard.sort_order, Dashboard.name))
    out = []
    for d in rows:
        item = {"code": d.code, "name": d.name, "status": d.status}
        if target.role == "user":
            item["granted"] = d.id in granted
        out.append(item)
    return out


@router.get("/overview")
def overview(actor: AppUser = Depends(require_admin), db: Session = DB):
    """Home page counters in one request and one query (each request to a remote database costs
    a round trip): users for administrators; data sources and integrations for the super user."""
    count = lambda *where: (  # noqa: E731
        select(func.count()).select_from(where[0]).where(*where[1:]).scalar_subquery())
    parts = {"users": count(AppUser),
             "active_users": count(AppUser, AppUser.is_active.is_(True))}
    ids: list[str] = []
    if actor.is_superuser:
        version = workspace_service.active_for_reads(db)
        ids = sorted((version.artifacts.get("integrations") or {}) if version else {})
        latest = (select(IntegrationRun.status)
                  .distinct(IntegrationRun.integration_id)
                  .where(IntegrationRun.integration_id.in_(ids))
                  .order_by(IntegrationRun.integration_id, IntegrationRun.id.desc())
                  .subquery())
        parts |= {"sources": count(DataSource),
                  "connected_sources": count(DataSource, DataSource.enabled.is_(True),
                                             DataSource.last_test_ok.is_(True)),
                  "failed_integrations": count(latest, latest.c.status == "failed")}
    row = db.execute(select(*(v.label(k) for k, v in parts.items()))).one()._asdict()
    if actor.is_superuser:
        row["integrations"] = len(ids)
    return row


@router.get("/users")
def list_users(q: str | None = Query(None, max_length=100),
               role: Literal["admin", "user"] | None = None,
               status: Literal["active", "inactive", "locked"] | None = None,
               limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
               _: AppUser = Depends(require_admin), db: Session = DB):
    items, total = users.list_users(db, q, role, status, limit, offset)
    return {"items": [user_json(u) for u in items], "total": total}


@router.post("/users", status_code=201)
def create_user(body: CreateUserIn, request: Request, actor: AppUser = Depends(require_admin),
                db: Session = DB):
    user = users.create(db, actor, email=body.email, full_name=body.full_name, role=body.role,
                        temporary_password=body.temporary_password, ip=client_ip(request))
    db.refresh(user)
    return user_json(user)


@router.get("/users/{user_id}")
def get_user(user_id: int, _: AppUser = Depends(require_admin), db: Session = DB):
    target = _target(db, user_id)
    return {"user": user_json(target), "dashboards": _dashboards_for(db, target),
            "telegram_linked": db.get(TelegramLink, target.id) is not None}


@router.patch("/users/{user_id}")
def update_user(user_id: int, body: UpdateUserIn, request: Request,
                actor: AppUser = Depends(require_admin), auth: Auth = Depends(current_auth),
                db: Session = DB):
    target = _target(db, user_id)
    if body.role is not None and body.role != target.role:
        ensure_recent_reauth(auth.session)  # role changes are sensitive (feature 004, FR-021)
    users.update(db, actor, target, full_name=body.full_name, role=body.role,
                 is_active=body.is_active, ip=client_ip(request))
    db.refresh(target)
    return user_json(target)


@router.post("/users/{user_id}/password", status_code=204)
def reset_password(user_id: int, body: ResetPasswordIn, request: Request,
                   actor: AppUser = Depends(require_admin), db: Session = DB):
    users.reset_password(db, actor, _target(db, user_id), body.temporary_password,
                         client_ip(request))


@router.put("/users/{user_id}/dashboards")
def set_grants(user_id: int, body: GrantsIn, request: Request,
               actor: AppUser = Depends(require_admin), db: Session = DB):
    target = _target(db, user_id)
    users.ensure_can_manage(actor, target, "grant")
    if target.role != "user":
        raise validation({"codes": "admin_sees_all"},
                         t("admin.admins_have_all_dashboards"))
    wanted_codes = set(body.codes)
    catalogue = {d.code: d for d in db.scalars(select(Dashboard))}
    unknown = wanted_codes - catalogue.keys()
    if unknown:
        names = ", ".join(sorted(unknown))
        raise validation({"codes": "unknown"}, M("admin.unknown_dashboards", names=names))
    current = set(db.scalars(select(DashboardAccess.dashboard_id)
                             .where(DashboardAccess.user_id == target.id)))
    wanted = {catalogue[c].id for c in wanted_codes}
    by_id = {d.id: d.code for d in catalogue.values()}
    ip = client_ip(request)
    for dashboard_id in sorted(wanted - current):
        db.add(DashboardAccess(user_id=target.id, dashboard_id=dashboard_id, granted_by=actor.id))
        audit.record(db, "dashboard_granted", actor_id=actor.id, target_id=target.id, ip=ip,
                     detail={"dashboard": by_id[dashboard_id]})
    removed = current - wanted
    if removed:
        db.execute(delete(DashboardAccess).where(DashboardAccess.user_id == target.id,
                                                 DashboardAccess.dashboard_id.in_(removed)))
        for dashboard_id in sorted(removed):
            audit.record(db, "dashboard_revoked", actor_id=actor.id, target_id=target.id, ip=ip,
                         detail={"dashboard": by_id[dashboard_id]})
    db.flush()
    return {"dashboards": _dashboards_for(db, target)}


@router.get("/dashboards")
def catalogue(_: AppUser = Depends(require_admin), db: Session = DB):
    rows = db.scalars(select(Dashboard).order_by(Dashboard.sort_order, Dashboard.name))
    definitions = dashboards.report_definitions(db)
    return {"items": [dashboards.to_json(d, definitions) for d in rows]}


@router.get("/audit")
def audit_log(target_id: int | None = None, actor_id: int | None = None,
              kind: str | None = Query(None, max_length=40), before: int | None = None,
              limit: int = Query(50, ge=1, le=100),
              _: AppUser = Depends(require_superuser), db: Session = DB):
    if kind is not None and kind not in AUDIT_KINDS:
        raise validation({"kind": "unknown"})
    actor, target = aliased(AppUser), aliased(AppUser)
    stmt = (select(AuditEvent, actor.email, target.email)
            .outerjoin(actor, actor.id == AuditEvent.actor_id)
            .outerjoin(target, target.id == AuditEvent.target_id))
    if target_id is not None:
        stmt = stmt.where(AuditEvent.target_id == target_id)
    if actor_id is not None:
        stmt = stmt.where(AuditEvent.actor_id == actor_id)
    if kind:
        stmt = stmt.where(AuditEvent.kind == kind)
    if before is not None:
        stmt = stmt.where(AuditEvent.id < before)
    rows = db.execute(stmt.order_by(AuditEvent.id.desc()).limit(limit + 1)).all()
    items = [{
        "id": e.id, "occurred_at": e.occurred_at, "kind": e.kind,
        "actor": {"id": e.actor_id, "email": a_email} if e.actor_id else None,
        "target": {"id": e.target_id, "email": t_email} if e.target_id else None,
        "ip": str(e.ip) if e.ip else None, "detail": e.detail,
    } for e, a_email, t_email in rows[:limit]]
    return {"items": items, "next_before": items[-1]["id"] if len(rows) > limit else None}


@router.post("/users/{user_id}/mfa/reset", status_code=204)
def reset_mfa(user_id: int, request: Request, actor: AppUser = Depends(require_superuser),
              _: Auth = Depends(recent_reauth), db: Session = DB):
    """Super user resets another user's two-step sign-in (lost device and recovery codes)."""
    target = _target(db, user_id)
    if target.id == actor.id:
        raise validation({"user_id": "self"}, M("admin.use_own_profile"))
    mfa.disable(db, target)
    sessions.delete_all(db, target.id)
    audit.record(db, "mfa_reset", actor_id=actor.id, target_id=target.id, ip=client_ip(request))


@router.delete("/users/{user_id}/telegram", status_code=204)
def unlink_user_telegram(user_id: int, request: Request, actor: AppUser = Depends(require_admin),
                         auth: Auth = Depends(current_auth), db: Session = DB):
    """Remove a managed user's Telegram link, e.g. a lost phone (feature 007, FR-007)."""
    target = _target(db, user_id)
    users.ensure_can_manage(actor, target, "edit")
    ensure_recent_reauth(auth.session)
    link = db.get(TelegramLink, target.id)
    if link is None:
        raise not_found(t("admin.user_no_telegram"))
    db.delete(link)
    audit.record(db, "telegram_unlinked", actor_id=actor.id, target_id=target.id,
                 ip=client_ip(request))
