"""Mailing lists (feature 058): reusable, owned groups of addresses.

A list is how a sender reaches 140 people without typing them, and how an authored project names its
recipients without carrying personal data (constitution II: a `distributions/<id>.yaml` names a list,
never an address). Two kinds share one row shape: `members` holds addresses in `mail_list_member`,
`role` resolves at send time to the installation's users of that role.

Nothing here talks to SMTP: this module owns the lists and the addresses, `app.mail.sends` owns the
deliveries.
"""
from __future__ import annotations

import csv
import io
from datetime import UTC, datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.errors import ApiError, not_found
from app.i18n import M
from app.mail import addresses as mail_addresses
from app.models import (
    MAIL_LIST_MAX_MEMBERS as MAX_MEMBERS,
    MAIL_LIST_ROLES,
    AppUser,
    EmailSubscription,
    MailList,
    MailListMember,
)
from app.services import audit

NAME_MAX = 80
DESCRIPTION_MAX = 200
NAME_MIN = 1
#: Roles that may own a shared list (everybody may own a personal one).
SHARING_ROLES = ("admin", "superuser")


def _refuse(status: int, code: str, message, fields: dict | None = None):
    raise ApiError(status, code, message, extra={"fields": fields} if fields else None)


def clean_name(value: str | None) -> str:
    name = " ".join((value or "").split())
    if not (NAME_MIN <= len(name) <= NAME_MAX):
        _refuse(422, "validation", M("mail.list_name_invalid", max=NAME_MAX),
                {"name": "length"})
    return name


def clean_description(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if len(text) > DESCRIPTION_MAX:
        _refuse(422, "validation", M("mail.list_description_too_long", max=DESCRIPTION_MAX),
                {"description": "length"})
    return text


def can_share(user: AppUser) -> bool:
    return user.role in SHARING_ROLES


def visible_to(db: Session, user: AppUser) -> list[MailList]:
    """The lists this user may use: their own, plus every shared one."""
    return list(db.scalars(
        select(MailList)
        .where(MailList.deleted_at.is_(None),
               (MailList.owner_id == user.id) | (MailList.visibility == "compartida"))
        .order_by(func.lower(MailList.name))).all())


def get(db: Session, user: AppUser, list_id: int) -> MailList:
    row = db.get(MailList, list_id)
    if row is None or row.deleted_at is not None:
        raise not_found(M("mail.list_not_found"))
    if row.owner_id != user.id and row.visibility != "compartida":
        # A personal list of somebody else does not exist for this user.
        raise not_found(M("mail.list_not_found"))
    return row


def editable(user: AppUser, row: MailList) -> bool:
    """Who may change a list: its owner, and an administrator for the shared ones."""
    return row.owner_id == user.id or (can_share(user) and row.visibility == "compartida")


def require_editable(user: AppUser, row: MailList) -> None:
    if not editable(user, row):
        _refuse(403, "list_not_editable", M("mail.list_not_editable"))


def _name_taken(db: Session, owner_id: int, name: str, *, ignore: int | None = None) -> bool:
    query = select(func.count()).select_from(MailList).where(
        MailList.owner_id == owner_id, MailList.deleted_at.is_(None),
        func.lower(MailList.name) == name.lower())
    if ignore is not None:
        query = query.where(MailList.id != ignore)
    return bool(db.scalar(query))


def create(
    db: Session,
    user: AppUser,
    *,
    name: str | None,
    description: str | None = None,
    visibility: str = "personal",
    kind: str = "members",
    role: str | None = None,
    ip: str | None = None,
) -> MailList:
    clean = clean_name(name)
    if visibility not in ("personal", "compartida"):
        _refuse(422, "validation", M("common.validation"), {"visibility": "invalid"})
    if visibility == "compartida" and not can_share(user):
        _refuse(403, "list_not_shared", M("mail.list_shared_admins_only"))
    if kind not in ("members", "role"):
        _refuse(422, "validation", M("common.validation"), {"kind": "invalid"})
    if kind == "role":
        if role not in MAIL_LIST_ROLES:
            _refuse(422, "validation", M("mail.list_role_invalid"), {"role": "invalid"})
        if not can_share(user):
            _refuse(403, "list_not_shared", M("mail.list_role_admins_only"))
    else:
        role = None
    if _name_taken(db, user.id, clean):
        _refuse(422, "name_taken", M("mail.list_name_taken", name=clean), {"name": "taken"})
    row = MailList(owner_id=user.id, name=clean, description=clean_description(description),
                   visibility=visibility, kind=kind, role=role)
    db.add(row)
    db.flush()
    audit.record(db, "mail_list_created", actor_id=user.id, ip=ip,
                 detail={"list": row.id, "name": row.name, "visibility": row.visibility,
                         "kind": row.kind, "role": row.role})
    return row


def update(
    db: Session,
    user: AppUser,
    row: MailList,
    *,
    name: str | None = None,
    description: str | None = None,
    visibility: str | None = None,
    ip: str | None = None,
    description_set: bool = False,
) -> MailList:
    require_editable(user, row)
    changes: dict[str, object] = {}
    if name is not None:
        clean = clean_name(name)
        if clean != row.name and _name_taken(db, row.owner_id, clean, ignore=row.id):
            _refuse(422, "name_taken", M("mail.list_name_taken", name=clean), {"name": "taken"})
        if clean != row.name:
            changes["name"] = clean
            row.name = clean
    if description_set or description is not None:
        value = clean_description(description)
        if value != row.description:
            changes["description"] = value
            row.description = value
    if visibility is not None and visibility != row.visibility:
        if visibility not in ("personal", "compartida"):
            _refuse(422, "validation", M("common.validation"), {"visibility": "invalid"})
        if visibility == "compartida" and not can_share(user):
            _refuse(403, "list_not_shared", M("mail.list_shared_admins_only"))
        changes["visibility"] = visibility
        row.visibility = visibility
    if changes:
        row.updated_at = datetime.now(UTC)
        audit.record(db, "mail_list_updated", actor_id=user.id, ip=ip,
                     detail={"list": row.id, "fields": sorted(changes)})
    return row


def delete(db: Session, user: AppUser, row: MailList, *, ip: str | None = None) -> int:
    """Soft delete; every delivery that named the list is paused with the reason, never deleted."""
    require_editable(user, row)
    now = datetime.now(UTC)
    row.deleted_at = now
    paused = 0
    for sub in db.scalars(
            select(EmailSubscription).where(EmailSubscription.paused.is_(False))).all():
        if any(isinstance(e, dict) and e.get("list") == row.id for e in sub.recipients or []):
            sub.paused = True
            sub.paused_reason = "list_deleted"
            paused += 1
    audit.record(db, "mail_list_deleted", actor_id=user.id, ip=ip,
                 detail={"list": row.id, "name": row.name, "paused_subscriptions": paused})
    db.flush()
    return paused


# --- Members ----------------------------------------------------------------------------------


def members(db: Session, row: MailList) -> list[MailListMember]:
    return list(db.scalars(
        select(MailListMember).where(MailListMember.list_id == row.id)
        .order_by(func.lower(MailListMember.address))).all())


def replace_members(db: Session, user: AppUser, row: MailList, entries: list[dict]) -> int:
    """The whole member list at once: what the editor saves after a paste or a CSV import."""
    require_editable(user, row)
    if row.kind != "members":
        _refuse(422, "validation", M("mail.list_role_no_members"), {"kind": "role"})
    cleaned: list[tuple[str, str | None, bool]] = []
    seen: set[str] = set()
    invalid: list[str] = []
    for entry in entries or []:
        raw = str(entry.get("address") or "")
        parsed, bad = mail_addresses.parse_recipients(raw)
        invalid.extend(bad)
        name = (entry.get("name") or "").strip() or None
        paused = bool(entry.get("paused"))
        for address, parsed_name in parsed:
            if address in seen:
                continue
            seen.add(address)
            cleaned.append((address, (name or parsed_name) or None, paused))
    if invalid:
        _refuse(422, "validation", M("mail.invalid_emails"),
                {"members": "invalid", "values": invalid[:20]})
    if len(cleaned) > MAX_MEMBERS:
        _refuse(422, "list_too_large", M("mail.list_too_large", n=MAX_MEMBERS),
                {"members": "too_many"})
    db.execute(MailListMember.__table__.delete().where(MailListMember.list_id == row.id))
    for address, name, paused in cleaned:
        db.add(MailListMember(list_id=row.id, address=address, name=name, paused=paused))
    row.updated_at = datetime.now(UTC)
    audit.record(db, "mail_list_updated", actor_id=user.id,
                 detail={"list": row.id, "fields": ["members"], "count": len(cleaned)})
    db.flush()
    return len(cleaned)


def import_csv(db: Session, user: AppUser, row: MailList, text: str) -> dict:
    """`correo,nombre[,pausado]` per line. Bad lines are reported, they never abort the import."""
    require_editable(user, row)
    if row.kind != "members":
        _refuse(422, "validation", M("mail.list_role_no_members"), {"kind": "role"})
    existing = {m.address: m for m in members(db, row)}
    added = updated = skipped = 0
    errors: list[dict] = []
    rows = list(csv.reader(io.StringIO(text or "")))
    for number, cells in enumerate(rows, start=1):
        cells = [c.strip() for c in cells if c is not None]
        if not cells or not "".join(cells):
            continue
        if number == 1 and cells[0].lower() in ("correo", "email", "e-mail", "mail"):
            continue
        raw = cells[0]
        name = cells[1] if len(cells) > 1 and cells[1] else None
        paused = len(cells) > 2 and cells[2].lower() in ("1", "si", "sí", "true", "yes")
        parsed, bad = mail_addresses.parse_recipients(raw)
        if bad or not parsed:
            errors.append({"line": number, "value": raw[:200], "code": "invalid"})
            skipped += 1
            continue
        address = parsed[0][0]
        if len(existing) >= MAX_MEMBERS and address not in existing:
            errors.append({"line": number, "value": raw[:200], "code": "too_many"})
            skipped += 1
            continue
        row_member = existing.get(address)
        if row_member is None:
            row_member = MailListMember(list_id=row.id, address=address, name=name,
                                        paused=paused)
            db.add(row_member)
            existing[address] = row_member
            added += 1
        else:
            if name:
                row_member.name = name
            row_member.paused = paused
            updated += 1
    row.updated_at = datetime.now(UTC)
    audit.record(db, "mail_list_updated", actor_id=user.id,
                 detail={"list": row.id, "fields": ["members"], "imported": added + updated})
    db.flush()
    return {"added": added, "updated": updated, "skipped": skipped, "errors": errors}


def export_csv(db: Session, row: MailList) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["correo", "nombre", "pausado"])
    for member in members(db, row):
        writer.writerow([member.address, member.name or "", "si" if member.paused else "no"])
    return buffer.getvalue()


def set_paused(db: Session, user: AppUser, row: MailList, member_id: int, paused: bool,
               *, ip: str | None = None) -> MailListMember:
    require_editable(user, row)
    member = db.get(MailListMember, member_id)
    if member is None or member.list_id != row.id:
        raise not_found(M("mail.list_member_not_found"))
    member.paused = bool(paused)
    row.updated_at = datetime.now(UTC)
    db.flush()
    return member


# --- Resolution -------------------------------------------------------------------------------


def role_addresses(db: Session, role: str, *, exclude: str | None = None) -> list[tuple[str, str]]:
    """Active users of a role, resolved at send time (a new administrator is included at once)."""
    rows = db.scalars(select(AppUser).where(AppUser.role == role, AppUser.is_active.is_(True))
                      .order_by(AppUser.full_name)).all()
    return [(u.email, u.full_name) for u in rows if u.email != exclude]


def resolve(db: Session, list_ids: list[int], *, exclude: str | None = None) -> list[dict]:
    """Addresses of these lists, as `{address, name, list_id, user}`.

    Paused members are skipped, role lists resolve to live users, the sender's own address is left
    out (it is the sender), and an address that appears in two lists appears once — the first list
    that named it owns it, which is what the history shows."""
    out: list[dict] = []
    seen: set[str] = set()
    if not list_ids:
        return out
    rows = db.scalars(select(MailList).where(MailList.id.in_(set(list_ids)),
                                             MailList.deleted_at.is_(None))).all()
    for row in sorted(rows, key=lambda r: r.id):
        if row.kind == "role":
            entries = [(address, name, None) for address, name in
                       role_addresses(db, row.role or "user", exclude=exclude)]
        else:
            entries = [(m.address, m.name, m.id) for m in members(db, row) if not m.paused]
        for address, name, member_id in entries:
            if address == exclude or address in seen:
                continue
            seen.add(address)
            out.append({"address": address, "name": name, "list_id": row.id,
                        "list_name": row.name})
    return out


def summary(db: Session, row: MailList, *, user: AppUser | None = None) -> dict:
    """The dialog's chip: a name and how many people it reaches, never the addresses."""
    if row.kind == "role":
        count = len(role_addresses(db, row.role or "user"))
        paused = 0
    else:
        count = db.scalar(select(func.count()).select_from(MailListMember)
                          .where(MailListMember.list_id == row.id,
                                 MailListMember.paused.is_(False))) or 0
        paused = db.scalar(select(func.count()).select_from(MailListMember)
                           .where(MailListMember.list_id == row.id,
                                  MailListMember.paused.is_(True))) or 0
    owner = db.get(AppUser, row.owner_id)
    return {
        "id": row.id,
        "name": row.name,
        "description": row.description,
        "visibility": row.visibility,
        "kind": row.kind,
        "role": row.role,
        "owner": {"id": row.owner_id, "name": owner.full_name if owner else ""},
        "mine": bool(user and row.owner_id == user.id),
        "editable": bool(user and editable(user, row)),
        "count": int(count),
        "paused": int(paused),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def to_json(db: Session, row: MailList, *, user: AppUser | None = None,
            with_members: bool = False) -> dict:
    payload = summary(db, row, user=user)
    if with_members:
        payload["members"] = [
            {"id": m.id, "address": m.address, "name": m.name, "paused": m.paused}
            for m in members(db, row)
        ] if row.kind == "members" else []
    return payload


def usable(db: Session, user: AppUser) -> list[dict]:
    """Every list this user may put in a recipient box."""
    return [{"id": row.id, "name": row.name, "count": summary(db, row, user=user)["count"],
             "visibility": row.visibility, "kind": row.kind, "role": row.role}
            for row in visible_to(db, user)]


def by_name(db: Session, name: str) -> MailList | None:
    """A project names a list; the name it names is resolved here (case-insensitive).

    Shared lists win over personal ones of the same name, so an authored project keeps working when
    somebody else creates a personal list with the same words."""
    shared_first = case((MailList.visibility == "compartida", 0), else_=1)
    rows = db.scalars(select(MailList).where(MailList.deleted_at.is_(None),
                                             func.lower(MailList.name) == name.strip().lower())
                      .order_by(shared_first, MailList.id)).all()
    return rows[0] if rows else None
