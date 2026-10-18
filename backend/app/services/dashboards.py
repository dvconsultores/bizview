"""Dashboard catalogue and access rules (data-model.md: can_see / can_open)."""
from fastapi import Depends
from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.auth.deps import current_user
from app.db import DB
from app.errors import ApiError, forbidden, not_found
from app.i18n import M
from app.models import AppUser, Dashboard, DashboardAccess


def _granted(user_id: int):
    return exists().where(DashboardAccess.user_id == user_id,
                          DashboardAccess.dashboard_id == Dashboard.id)


def visible_for(db: Session, user: AppUser) -> list[Dashboard]:
    stmt = select(Dashboard).where(Dashboard.status != "hidden")
    if user.role != "admin":
        stmt = stmt.where(_granted(user.id))
    return list(db.scalars(stmt.order_by(Dashboard.sort_order, Dashboard.name)))


def can_see(db: Session, user: AppUser, dashboard: Dashboard) -> bool:
    if dashboard.status == "hidden":
        return False
    return user.role == "admin" or bool(db.scalar(select(_granted(user.id))
                                                  .where(Dashboard.id == dashboard.id)))


def get_for_open(db: Session, user: AppUser, code: str) -> Dashboard:
    return check_open(db, user, db.scalar(select(Dashboard).where(Dashboard.code == code)))


def check_open(db: Session, user: AppUser, dashboard: Dashboard | None) -> Dashboard:
    """The access rules of get_for_open on a dashboard row already loaded."""
    if dashboard is None or dashboard.status == "hidden":
        raise not_found(M("dashboards.not_found"))
    if not can_see(db, user, dashboard):
        raise forbidden(M("dashboards.forbidden"))
    if dashboard.status != "available":
        raise ApiError(403, "coming_soon", M("dashboards.coming_soon"))
    return dashboard


def require_dashboard(code: str):
    """Dependency for a dashboard's own API routes, so typed URLs are refused server-side."""
    def _dep(db: Session = DB, user: AppUser = Depends(current_user)) -> Dashboard:
        return get_for_open(db, user, code)
    return _dep


def report_definitions(db: Session) -> dict[str, dict]:
    """Report id -> definition of the active workspace version, for optional English names."""
    from app.workspace import service as workspace_service
    snap = workspace_service.active_for_reads(db)
    if snap is None:
        return {}
    return {rid: entry.get("definition") or {}
            for rid, entry in (snap.artifacts.get("reports") or {}).items()}


def to_json(d: Dashboard, definitions: dict[str, dict] | None = None) -> dict:
    result = {"code": d.code, "name": d.name, "description": d.description,
              "icon": d.icon, "status": d.status,
              "path": f"/r/{d.report_id}" if d.report_id else f"/d/{d.code}"}
    if d.report_id and definitions and d.report_id in definitions:
        definition = definitions[d.report_id]
        title_en = definition.get("title_en")
        description_en = definition.get("description_en")
        if isinstance(title_en, str) and title_en.strip():
            result["name_en"] = title_en
        if isinstance(description_en, str) and description_en.strip():
            result["description_en"] = description_en[:200]
    return result
