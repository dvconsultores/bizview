"""The installation's Google sign-in policy (feature 054): domains, provisioning and role rules.

One place decides *who may come in and as what*, so the callback, the admin card and the tests read
the same rules. With no `google_settings` row every answer is the deployment default — the domains
of `GOOGLE_ALLOWED_DOMAINS`, no provisioning, `user` and no dashboards — which is exactly feature
027's behaviour for an installation that never opened the card.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import M, validation
from app.models import (
    GOOGLE_ACCESS_MODES,
    GOOGLE_CONDITIONS,
    ROLES,
    AppUser,
    Dashboard,
    DashboardAccess,
    GoogleRule,
    GoogleSettings,
)
from app.services import audit

MAX_DOMAINS = 20
MAX_RULES = 50
MAX_EMAILS = 50
MAX_DOMAIN_LEN = 253
MAX_EMAIL_LEN = 254

_DOMAIN = re.compile(r"^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def now() -> datetime:
    return datetime.now(UTC)


# --- normalisation --------------------------------------------------------------------------

def normalise_domains(values: list[str] | tuple[str, ...] | None) -> list[str]:
    """Lower case, no leading `@`, trimmed, deduplicated, in the order given."""
    out: list[str] = []
    for raw in values or []:
        value = str(raw).strip().lower().lstrip("@")
        if value and value not in out:
            out.append(value)
    return out


def normalise_emails(values: list[str] | tuple[str, ...] | None) -> list[str]:
    out: list[str] = []
    for raw in values or []:
        value = str(raw).strip().lower()
        if value and value not in out:
            out.append(value)
    return out


def normalise_access(value: dict | None) -> dict:
    """`{mode, codes}` with the codes of `list` deduplicated; the one shape the card and the rules
    share (spec, clarify)."""
    mode = str((value or {}).get("mode") or "none")
    if mode not in GOOGLE_ACCESS_MODES:
        mode = "none"
    codes = [str(c) for c in (value or {}).get("codes") or []]
    codes = list(dict.fromkeys(c for c in codes if c))
    return {"mode": mode, "codes": codes} if mode == "list" else {"mode": mode}


# --- settings -------------------------------------------------------------------------------

@dataclass(frozen=True)
class Policy:
    """What the callback needs, with the deployment defaults already applied."""

    allowed_domains: list[str]
    auto_provision: bool
    default_role: str
    default_access: dict
    apply_rules_to_existing: bool


def row(db: Session) -> GoogleSettings | None:
    return db.get(GoogleSettings, 1)


def policy(db: Session) -> Policy:
    stored = row(db)
    if stored is None:
        return Policy(allowed_domains=normalise_domains(get_settings().google_domains),
                      auto_provision=False, default_role="user",
                      default_access={"mode": "none"}, apply_rules_to_existing=False)
    return Policy(allowed_domains=normalise_domains(stored.allowed_domains),
                  auto_provision=stored.auto_provision, default_role=stored.default_role,
                  default_access=normalise_access(stored.default_access),
                  apply_rules_to_existing=stored.apply_rules_to_existing)


def public_settings(db: Session) -> dict:
    current = policy(db)
    stored = row(db)
    return {
        "allowed_domains": current.allowed_domains,
        # True when the list on screen is the deployment's and the first save turns it into data.
        "domains_from_env": stored is None,
        "auto_provision": current.auto_provision,
        "default_role": current.default_role,
        "default_access": current.default_access,
        "apply_rules_to_existing": current.apply_rules_to_existing,
        "updated_at": stored.updated_at.isoformat() if stored is not None else None,
    }


def validate_settings(body: dict) -> dict:
    domains = normalise_domains(body.get("allowed_domains") or [])
    if len(domains) > MAX_DOMAINS:
        raise validation({"allowed_domains": "too_many"},
                         M("google.too_many_domains", max=MAX_DOMAINS))
    for domain in domains:
        if len(domain) > MAX_DOMAIN_LEN or not _DOMAIN.match(domain):
            raise validation({"allowed_domains": "invalid"},
                             M("google.invalid_domain", domain=domain))
    role = str(body.get("default_role") or "user")
    if role not in ROLES:
        raise validation({"default_role": "invalid"}, M("google.invalid_role"))
    return {
        "allowed_domains": domains,
        "auto_provision": bool(body.get("auto_provision")),
        "default_role": role,
        "default_access": normalise_access(body.get("default_access")),
        "apply_rules_to_existing": bool(body.get("apply_rules_to_existing")),
    }


def update_settings(db: Session, actor: AppUser, body: dict, ip: str | None) -> dict:
    values = validate_settings(body)
    _check_codes(db, values["default_access"])
    stored = db.get(GoogleSettings, 1, with_for_update=True)
    before = public_settings(db)
    if stored is None:
        stored = GoogleSettings(id=1, **values)
        db.add(stored)
    else:
        for key, value in values.items():
            setattr(stored, key, value)
    stored.updated_by = actor.id
    db.flush()
    audit.record(db, "google_settings_updated", actor_id=actor.id, ip=ip, detail={
        "before": {"allowed_domains": before["allowed_domains"],
                   "auto_provision": before["auto_provision"],
                   "default_role": before["default_role"],
                   "default_access": before["default_access"],
                   "apply_rules_to_existing": before["apply_rules_to_existing"]},
        "after": values,
    })
    return public_settings(db)


def _check_codes(db: Session, access: dict) -> None:
    if access["mode"] != "list":
        return
    known = set(db.scalars(select(Dashboard.code)))
    unknown = [code for code in access["codes"] if code not in known]
    if unknown:
        raise validation({"default_access": "unknown"},
                         M("admin.unknown_dashboards", names=", ".join(sorted(unknown))))


# --- rules ----------------------------------------------------------------------------------

def condition_of(kind: str, raw: dict) -> list[str]:
    """The stored value of a condition, or a field error: one domain, or a list of addresses."""
    if kind not in GOOGLE_CONDITIONS:
        raise validation({"condition": "invalid"}, M("google.invalid_condition"))
    if kind == "group":
        # The schema and the card ship the condition; a Workspace service account does not exist
        # here yet, so accepting one would silently never match.
        raise validation({"condition": "unavailable"}, M("google.group_unavailable"))
    if kind == "domain":
        raw_value = raw.get("value")
        entries = raw_value if isinstance(raw_value, list) else [raw_value]
        domain = normalise_domains([str(v or "") for v in entries])
        if len(domain) != 1 or not _DOMAIN.match(domain[0]):
            raise validation({"value": "invalid"}, M("google.invalid_domain",
                                                     domain=str(raw.get("value") or "")))
        return domain
    emails = normalise_emails(raw.get("value") or [])
    if not emails or len(emails) > MAX_EMAILS:
        raise validation({"value": "invalid"}, M("google.too_many_emails", max=MAX_EMAILS))
    for email in emails:
        if len(email) > MAX_EMAIL_LEN or not _EMAIL.match(email):
            raise validation({"value": "invalid"}, M("google.invalid_email", email=email))
    return emails


def validate_rule(db: Session, body: dict) -> dict:
    kind = str(body.get("condition") or "")
    value = condition_of(kind, {"value": body.get("value")})
    role = str(body.get("role") or "user")
    if role not in ROLES:            # `superusuario` and anything else is refused here
        raise validation({"role": "invalid"}, M("google.invalid_role"))
    access = normalise_access(body.get("access"))
    _check_codes(db, access)
    return {"condition": kind, "value": value, "role": role, "access": access,
            "enabled": bool(body.get("enabled", True))}


def list_rules(db: Session) -> list[GoogleRule]:
    return list(db.scalars(select(GoogleRule).order_by(GoogleRule.position, GoogleRule.id)))


def public_rule(rule: GoogleRule) -> dict:
    return {"id": rule.id, "position": rule.position, "condition": rule.condition,
            "value": list(rule.value or []), "role": rule.role,
            "access": normalise_access(rule.access), "enabled": rule.enabled}


def _shift(db: Session, position: int, *, delta: int) -> None:
    """Make room for (or close) a position, keeping the list contiguous."""
    for rule in db.scalars(select(GoogleRule).where(GoogleRule.position >= position)):
        rule.position += delta


def create_rule(db: Session, actor: AppUser, body: dict, ip: str | None) -> dict:
    values = validate_rule(db, body)
    if len(list_rules(db)) >= MAX_RULES:
        raise validation({"rules": "too_many"}, M("google.too_many_rules", max=MAX_RULES))
    _shift(db, 0, delta=1)
    rule = GoogleRule(position=0, updated_by=actor.id, **values)
    db.add(rule)
    db.flush()
    audit.record(db, "google_rule_created", actor_id=actor.id, ip=ip,
                 detail={"rule": rule.id, "condition": rule.condition, "value": rule.value,
                         "role": rule.role, "access": normalise_access(rule.access)})
    return public_rule(rule)


def update_rule(db: Session, actor: AppUser, rule: GoogleRule, body: dict,
                ip: str | None) -> dict:
    values = validate_rule(db, body)
    before = public_rule(rule)
    for key, value in values.items():
        setattr(rule, key, value)
    rule.updated_by = actor.id
    db.flush()
    audit.record(db, "google_rule_updated", actor_id=actor.id, ip=ip,
                 detail={"rule": rule.id, "before": before, "after": public_rule(rule)})
    return public_rule(rule)


def delete_rule(db: Session, actor: AppUser, rule: GoogleRule, ip: str | None) -> None:
    position = rule.position
    db.delete(rule)
    db.flush()
    for other in db.scalars(select(GoogleRule).where(GoogleRule.position > position)):
        other.position -= 1
    audit.record(db, "google_rule_deleted", actor_id=actor.id, ip=ip,
                 detail={"rule": position, "condition": rule.condition})
    db.flush()


def reorder_rules(db: Session, actor: AppUser, ids: list[int], ip: str | None) -> list[dict]:
    rules = {rule.id: rule for rule in list_rules(db)}
    if set(ids) != set(rules) or len(ids) != len(rules):
        raise validation({"ids": "incomplete"}, M("google.reorder_incomplete"))
    for position, rule_id in enumerate(ids):
        rules[rule_id].position = position
    db.flush()
    audit.record(db, "google_rule_updated", actor_id=actor.id, ip=ip,
                 detail={"order": ids})
    return [public_rule(rules[i]) for i in ids]


# --- evaluation and provisioning -------------------------------------------------------------

def matching_rule(db: Session, email: str) -> GoogleRule | None:
    """First enabled rule in position order whose condition the identity satisfies."""
    address = email.strip().lower()
    domain = address.rsplit("@", 1)[-1]
    for rule in list_rules(db):
        if not rule.enabled:
            continue
        values = [str(v).strip().lower() for v in (rule.value or [])]
        if rule.condition == "domain" and domain in values:
            return rule
        if rule.condition == "email" and address in values:
            return rule
    return None


def domain_allowed(policy_: Policy, email: str) -> bool:
    """An empty list admits any verified domain — the meaning `GOOGLE_ALLOWED_DOMAINS` has today."""
    if not policy_.allowed_domains:
        return True
    return email.rsplit("@", 1)[-1].lower() in policy_.allowed_domains


def grant(db: Session, user: AppUser, access: dict, *, actor_id: int | None) -> list[str]:
    """Materialise an access value into `dashboard_access` rows; returns the codes granted."""
    mode = access.get("mode")
    if mode == "none":
        codes: list[str] = []
    elif mode == "all_public":
        codes = list(db.scalars(select(Dashboard.code)
                                .where(Dashboard.status == "available")
                                .order_by(Dashboard.code)))
    else:
        codes = list(access.get("codes") or [])
    if not codes:
        return []
    dashboards = {d.code: d for d in db.scalars(select(Dashboard).where(Dashboard.code.in_(codes)))}
    current = set(db.scalars(select(DashboardAccess.dashboard_id)
                             .where(DashboardAccess.user_id == user.id)))
    added = []
    for code in codes:
        dashboard = dashboards.get(code)
        if dashboard is None or dashboard.id in current:
            continue
        db.add(DashboardAccess(user_id=user.id, dashboard_id=dashboard.id, granted_by=actor_id))
        added.append(code)
    db.flush()
    return added


def provision(db: Session, *, email: str, name: str | None, google_sub: str,
              policy_: Policy, actor_id: int | None = None) -> tuple[AppUser, GoogleRule | None]:
    """Create the account a Google identity is allowed to have, with its grants."""
    from app.models import GoogleLink
    from app.services import users

    address = email.strip().lower()
    full_name = (name or "").strip() or address.split("@", 1)[0]
    rule = matching_rule(db, address)
    role = rule.role if rule is not None else policy_.default_role
    access = normalise_access(rule.access) if rule is not None else policy_.default_access
    user = AppUser(email=address, full_name=full_name[:120], role=role, is_superuser=False,
                   is_active=True, auth_provider="google", password_hash=None,
                   must_change_password=False, failed_attempts=0, created_by=actor_id)
    db.add(user)
    db.flush()
    now_ = users.now()
    db.add(GoogleLink(user_id=user.id, google_sub=google_sub, email=address,
                      created_at=now_, last_login_at=now_))
    db.flush()
    granted = grant(db, user, access, actor_id=actor_id)
    audit.record(db, "google_user_provisioned", target_id=user.id,
                 detail={"email": address, "role": role,
                         "rule": rule.id if rule is not None else None,
                         "dashboards": granted})
    return user, rule


def apply_to_existing(db: Session, user: AppUser, rule: GoogleRule,
                      policy_: Policy) -> bool:
    """Give an existing account the rule's role and access — only when an admin asked for it.

    Returns whether anything changed; a superuser is never touched."""
    if user.is_superuser or not policy_.apply_rules_to_existing:
        return False
    changed: dict = {}
    if user.role != rule.role:
        changed["role"] = {"from": user.role, "to": rule.role}
        user.role = rule.role
    granted = grant(db, user, normalise_access(rule.access), actor_id=user.id)
    if granted:
        changed["dashboards"] = granted
    if not changed:
        return False
    db.flush()
    audit.record(db, "google_rule_applied", target_id=user.id,
                 detail={"rule": rule.id, "condition": rule.condition,
                         "value": list(rule.value or []), **changed})
    return True
