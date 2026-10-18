"""Subscriptions owned by project distributions (feature 020, research R8)."""
from datetime import UTC, datetime

from sqlalchemy import select

from app.config import get_settings
from app.mail.subscriptions import next_due
from app.models import Dashboard, EmailSend, EmailSubscription, Project
from app.services import audit

SCHEDULE = ("frequency", "hour", "weekday", "monthday")


def _distributions(version) -> dict:
    if version is None or not isinstance(version.artifacts, dict):
        return {}
    return version.artifacts.get("distributions") or {}


def _desired(version) -> dict[tuple[str, str, int], tuple[dict, dict]]:
    """(project slug, distribution id, index) -> (definition, subscription item)."""
    desired = {}
    for dist_id, dist in _distributions(version).items():
        definition = dist.get("definition") or {}
        for index, item in enumerate(definition.get("subscriptions") or []):
            desired[(dist.get("project"), dist_id, index)] = (definition, item)
    return desired


def _previous_paused(previous, dist_id: str, index: int) -> bool | None:
    dist = _distributions(previous).get(dist_id) or {}
    items = (dist.get("definition") or {}).get("subscriptions") or []
    if index >= len(items):
        return None
    return bool(items[index].get("paused", False))


def _fields(dashboard, item: dict) -> dict:
    frequency = item["frequency"]
    return {
        "dashboard_id": dashboard.id,
        "recipients": [{"role": r} for r in item["recipients"]["roles"]],
        "frequency": frequency,
        "hour": item["hour"],
        "weekday": item.get("weekday") if frequency == "weekly" else None,
        "monthday": item.get("monthday") if frequency == "monthly" else None,
        "period": item["period"],
        "attach_pdf": item.get("attach_pdf", True),
        "link_days": item.get("link_days"),
    }


def _forget_link_secrets(db, row) -> None:
    """Same as the 018 delete: past sends keep only the link id, not its secret."""
    for send in db.scalars(select(EmailSend).where(
            EmailSend.subscription_id == row.id,
            EmailSend.selection["link"].has_key("ct"),
            EmailSend.status.in_(("sent", "partial", "failed")))):
        data = send.selection["link"]
        send.selection = {**send.selection, "link": {"id": data.get("id"), "sub": row.id}}


def sync(db, version, actor, *, previous=None) -> dict[str, int]:
    """Make the owned subscriptions match the distributions of `version`.

    Hand-made subscriptions (`project_id IS NULL`) are never read. `previous` is the version
    the distributions come from (to tell whether the YAML changed `paused`)."""
    actor_id = actor.id if actor is not None else None
    tz = get_settings().timezone
    now = datetime.now(UTC)
    desired = _desired(version)
    projects = {p.slug: p for p in db.scalars(select(Project).where(Project.deleted_at.is_(None)))}
    slugs = {p.id: p.slug for p in projects.values()}
    dashboards = {d.report_id: d for d in db.scalars(
        select(Dashboard).where(Dashboard.report_id.is_not(None)))}
    owned = db.scalars(select(EmailSubscription).where(
        EmailSubscription.project_id.is_not(None))).all()
    rows = {(slugs.get(r.project_id), r.distribution_id, r.distribution_index): r
            for r in owned if r.project_id in slugs}

    counts = {"created": 0, "updated": 0, "deleted": 0}
    kept: set[int] = set()
    for (slug, dist_id, index), (definition, item) in desired.items():
        project = projects.get(slug)
        dashboard = dashboards.get(definition.get("report"))
        if project is None or dashboard is None:
            continue
        fields = _fields(dashboard, item)
        yaml_paused = bool(item.get("paused", False))
        detail = {"dashboard": dashboard.code, "project": slug, "distribution": dist_id}
        row = rows.get((slug, dist_id, index))
        if row is None:
            if actor_id is None:
                continue
            row = EmailSubscription(
                **fields, created_by=actor_id, paused=yaml_paused,
                next_due_at=next_due(fields["frequency"], fields["hour"], fields["weekday"],
                                     fields["monthday"], now, tz),
                project_id=project.id, distribution_id=dist_id, distribution_index=index)
            db.add(row)
            db.flush()
            kept.add(row.id)
            counts["created"] += 1
            audit.record(db, "email_subscription_created", actor_id=actor_id, ip=None,
                         detail={"subscription_id": row.id, **detail,
                                 "recipients": len(fields["recipients"])})
            continue

        kept.add(row.id)
        changed = [name for name, value in fields.items() if getattr(row, name) != value]
        for name in changed:
            setattr(row, name, fields[name])
        before = _previous_paused(previous, dist_id, index)
        if (before is None or before != yaml_paused) and row.paused != yaml_paused:
            row.paused = yaml_paused
            changed.append("paused")
        if any(name in changed for name in SCHEDULE) or (
                "paused" in changed and not row.paused):
            row.next_due_at = next_due(row.frequency, row.hour, row.weekday, row.monthday,
                                       now, tz)
        if changed:
            if actor_id is not None:
                row.created_by = actor_id
            counts["updated"] += 1
            audit.record(db, "email_subscription_updated", actor_id=actor_id, ip=None,
                         detail={"subscription_id": row.id, **detail,
                                 "fields": sorted(changed)})

    codes = {d.id: d.code for d in dashboards.values()}
    for row in owned:
        if row.id in kept:
            continue
        _forget_link_secrets(db, row)
        db.delete(row)
        counts["deleted"] += 1
        audit.record(db, "email_subscription_deleted", actor_id=actor_id, ip=None,
                     detail={"subscription_id": row.id, "dashboard": codes.get(row.dashboard_id),
                             "project": slugs.get(row.project_id),
                             "distribution": row.distribution_id})
    db.flush()
    return counts


def share_policy(db, report_id: str) -> dict | None:
    """Share rule of the active version's distributions of a report (None: no rule)."""
    from app.workspace.service import active

    shares = [(dist.get("definition") or {}).get("share") or {}
              for dist in _distributions(active(db)).values()
              if (dist.get("definition") or {}).get("report") == report_id]
    if not shares:
        return None
    limits = [s["max_days"] for s in shares if s.get("max_days") is not None]
    return {"allowed": all(s.get("allowed", True) for s in shares),
            "max_days": min(limits) if limits else None}
