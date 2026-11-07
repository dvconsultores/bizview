"""Mailing lists (feature 058): the API of `app.mail.lists`.

Only signed-in users reach any of this, and a list is visible to its owner and — when shared — to
everybody who can send. There is no public surface and no endpoint that returns an address to
somebody who cannot edit the list's use of it: the dialog gets names and counts, the editor gets the
members it may edit.
"""
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth.deps import client_ip, current_user
from app.db import DB
from app.errors import not_found, validation
from app.i18n import M
from app.mail import addresses as mail_addresses
from app.mail import lists as mail_lists
from app.models import AppUser

router = APIRouter(prefix="/api/mail/lists")

Address = Annotated[str, Field(max_length=254)]
MemberName = Annotated[str, Field(max_length=120)]


class ListIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=mail_lists.NAME_MAX)
    description: str | None = Field(default=None, max_length=mail_lists.DESCRIPTION_MAX)
    visibility: Literal["personal", "compartida"] = "personal"
    kind: Literal["members", "role"] = "members"
    role: Literal["user", "admin"] | None = None


class ListPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=mail_lists.NAME_MAX)
    description: str | None = Field(default=None, max_length=mail_lists.DESCRIPTION_MAX)
    visibility: Literal["personal", "compartida"] | None = None


class MemberIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    address: Address
    name: MemberName | None = None
    paused: bool = False


class MembersIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    members: list[MemberIn] = Field(default_factory=list)
    #: Free text pasted instead of (or beside) the rows: parsed with the same grammar as a send.
    text: str | None = Field(default=None, max_length=200_000)


class PauseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    paused: bool = True


def _json(db: Session, user: AppUser, row, *, with_members: bool = False) -> dict:
    return mail_lists.to_json(db, row, user=user, with_members=with_members)


@router.get("")
def get_lists(
    scope: Literal["mine", "shared", "all"] = "all",
    q: str | None = Query(None, max_length=100),
    user: AppUser = Depends(current_user),
    db: Session = DB,
):
    rows = mail_lists.visible_to(db, user)
    if scope == "mine":
        rows = [row for row in rows if row.owner_id == user.id]
    elif scope == "shared":
        rows = [row for row in rows if row.visibility == "compartida"]
    if q:
        needle = q.strip().lower()
        rows = [row for row in rows if needle in row.name.lower()]
    return {
        "items": [_json(db, user, row) for row in rows],
        "can_share": mail_lists.can_share(user),
        "max_members": mail_lists.MAX_MEMBERS,
    }


@router.post("", status_code=201)
def post_list(body: ListIn, request: Request, user: AppUser = Depends(current_user),
              db: Session = DB):
    row = mail_lists.create(db, user, name=body.name, description=body.description,
                            visibility=body.visibility, kind=body.kind, role=body.role,
                            ip=client_ip(request))
    db.flush()
    return _json(db, user, row, with_members=True)


@router.get("/{list_id}")
def get_list(list_id: int, user: AppUser = Depends(current_user), db: Session = DB):
    return _json(db, user, mail_lists.get(db, user, list_id), with_members=True)


@router.patch("/{list_id}")
def patch_list(list_id: int, body: ListPatch, request: Request,
               user: AppUser = Depends(current_user), db: Session = DB):
    row = mail_lists.get(db, user, list_id)
    updated = mail_lists.update(
        db, user, row, name=body.name, description=body.description,
        visibility=body.visibility, description_set="description" in body.model_fields_set,
        ip=client_ip(request))
    db.flush()
    return _json(db, user, updated, with_members=True)


@router.delete("/{list_id}", status_code=204)
def delete_list(list_id: int, request: Request, user: AppUser = Depends(current_user),
                db: Session = DB):
    row = mail_lists.get(db, user, list_id)
    mail_lists.delete(db, user, row, ip=client_ip(request))
    return Response(status_code=204)


@router.put("/{list_id}/members")
def put_members(list_id: int, body: MembersIn, user: AppUser = Depends(current_user),
                db: Session = DB):
    row = mail_lists.get(db, user, list_id)
    entries = [member.model_dump() for member in body.members]
    if body.text:
        parsed, invalid = mail_addresses.parse_recipients(body.text)
        if invalid:
            raise validation({"members": "invalid", "values": invalid[:20]},
                             M("mail.invalid_emails"))
        entries.extend({"address": address, "name": name, "paused": False}
                       for address, name in parsed)
    mail_lists.replace_members(db, user, row, entries)
    db.flush()
    return _json(db, user, row, with_members=True)


@router.post("/{list_id}/members/import")
def import_members(list_id: int, request: Request, body: dict | None = None,
                   user: AppUser = Depends(current_user), db: Session = DB):
    row = mail_lists.get(db, user, list_id)
    text = ""
    if isinstance(body, dict):
        text = str(body.get("text") or "")
    if not text:
        text = request.headers.get("x-csv-text") or ""
    result = mail_lists.import_csv(db, user, row, text)
    db.flush()
    return {**result, "list": _json(db, user, row)}


@router.get("/{list_id}/export")
def export_members(list_id: int, user: AppUser = Depends(current_user), db: Session = DB):
    row = mail_lists.get(db, user, list_id)
    if not mail_lists.editable(user, row):
        raise not_found(M("mail.list_not_found"))
    name = "".join(c if c.isalnum() or c in " -_" else "-" for c in row.name).strip() or "lista"
    return Response(
        mail_lists.export_csv(db, row),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="lista-{name}.csv"'},
    )


@router.post("/{list_id}/members/{member_id}/pause")
def pause_member(list_id: int, member_id: int, body: PauseIn, request: Request,
                 user: AppUser = Depends(current_user), db: Session = DB):
    row = mail_lists.get(db, user, list_id)
    mail_lists.set_paused(db, user, row, member_id, body.paused, ip=client_ip(request))
    db.flush()
    return _json(db, user, row, with_members=True)
