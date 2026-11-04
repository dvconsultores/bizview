"""The installation's Google sign-in policy (feature 054): domains, provisioning and role rules.

Superuser only, step-up protected on every write, audited per change. The card in Administración →
Seguridad reads and writes these endpoints; the callback (`app/api/oauth.py`) reads the same policy
through `app/services/google_policy.py`, so what the card saves is what the next sign-in obeys
without a restart.
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.deps import client_ip, recent_reauth, require_superuser
from app.db import DB
from app.errors import not_found
from app.models import AppUser, Dashboard, GoogleRule
from app.services import google_policy as policy

router = APIRouter(prefix="/api/admin/google")


class AccessIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: str = Field(default="none", max_length=16)
    codes: list[str] = Field(default_factory=list, max_length=policy.MAX_DOMAINS * 10)


class SettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_domains: list[str] = Field(default_factory=list, max_length=policy.MAX_DOMAINS)
    auto_provision: bool = False
    default_role: str = Field(default="user", max_length=16)
    default_access: AccessIn = Field(default_factory=AccessIn)
    apply_rules_to_existing: bool = False


class RuleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    condition: str = Field(max_length=16)
    # One domain, or the addresses of an email rule: one shape for both (spec, clarify).
    value: list[str] = Field(default_factory=list, max_length=policy.MAX_EMAILS)
    role: str = Field(default="user", max_length=16)
    access: AccessIn = Field(default_factory=AccessIn)
    enabled: bool = True


class ReorderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[int] = Field(default_factory=list)


def _catalogue(db: Session) -> list[dict]:
    """The dashboards the access picker offers: the same catalogue the admin screen lists."""
    rows = db.scalars(select(Dashboard).order_by(Dashboard.sort_order, Dashboard.name))
    return [{"code": d.code, "name": d.name, "status": d.status} for d in rows]


def _rule(db: Session, rule_id: int) -> GoogleRule:
    rule = db.get(GoogleRule, rule_id)
    if rule is None:
        raise not_found()
    return rule


def _body(model: BaseModel) -> dict:
    return model.model_dump()


@router.get("")
def get_settings(_actor: AppUser = Depends(require_superuser), db: Session = DB):
    return {"settings": policy.public_settings(db), "dashboards": _catalogue(db)}


@router.put("")
def put_settings(body: SettingsIn, request: Request,
                 actor: AppUser = Depends(require_superuser),
                 _auth=Depends(recent_reauth),
                 db: Session = DB):
    saved = policy.update_settings(db, actor, _body(body), client_ip(request))
    return {"settings": saved, "dashboards": _catalogue(db)}


@router.get("/rules")
def list_rules(_actor: AppUser = Depends(require_superuser), db: Session = DB):
    return {"items": [policy.public_rule(rule) for rule in policy.list_rules(db)]}


@router.post("/rules", status_code=201)
def create_rule(body: RuleIn, request: Request,
                actor: AppUser = Depends(require_superuser),
                _auth=Depends(recent_reauth),
                db: Session = DB):
    return policy.create_rule(db, actor, _body(body), client_ip(request))


@router.put("/rules/reorder")
def reorder_rules(body: ReorderIn, request: Request,
                  actor: AppUser = Depends(require_superuser),
                  _auth=Depends(recent_reauth),
                  db: Session = DB):
    return {"items": policy.reorder_rules(db, actor, list(body.ids), client_ip(request))}


@router.put("/rules/{rule_id}")
def update_rule(rule_id: int, body: RuleIn, request: Request,
                actor: AppUser = Depends(require_superuser),
                _auth=Depends(recent_reauth),
                db: Session = DB):
    return policy.update_rule(db, actor, _rule(db, rule_id), _body(body), client_ip(request))


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, request: Request,
                actor: AppUser = Depends(require_superuser),
                _auth=Depends(recent_reauth),
                db: Session = DB):
    policy.delete_rule(db, actor, _rule(db, rule_id), client_ip(request))
