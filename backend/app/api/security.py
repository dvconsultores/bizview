"""Security overview for the super user (feature 004, FR-025)."""
from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth.deps import require_superuser
from app.config import get_settings
from app.db import DB
from app.i18n import t
from app.models import AppUser, AssistantAttachment, DirectReadLog, SecurityState
from app.security import crypto

router = APIRouter(prefix="/api/security")


def _direct_reads(db: Session) -> list[dict]:
    """Direct reads per source over the last 24 h (FR-015); stale-served rows are extra
    log lines of an already counted failure, so they are not counted again."""
    rows = db.execute(
        select(DirectReadLog.source,
               func.count().label("total"),
               func.count().filter(DirectReadLog.outcome != "ok").label("failed"))
        .where(DirectReadLog.stale_served.is_(False),
               DirectReadLog.occurred_at >= func.now() - timedelta(hours=24))
        .group_by(DirectReadLog.source)
        .order_by(DirectReadLog.source)
    ).all()
    return [{"source": source, "total": total, "failed": failed}
            for source, total, failed in rows]


def _attachments(db) -> dict:
    """What the chat has sent to the provider (feature 024, FR-014): counts and sizes only."""
    s = get_settings()
    total, size = db.execute(select(func.count(AssistantAttachment.id),
                                    func.coalesce(func.sum(AssistantAttachment.byte_size),
                                                  0))).one()
    return {"total": total, "bytes": int(size),
            "conversations": db.scalar(select(func.count(
                func.distinct(AssistantAttachment.session_id)))) or 0,
            "provider": s.ai_provider, "model": s.ai_model_effective}


@router.get("")
def overview(_: AppUser = Depends(require_superuser), db: Session = DB):
    s = get_settings()
    state = db.get(SecurityState, 1)
    admins = db.scalar(select(func.count()).where(AppUser.role == "admin",
                                                  AppUser.is_active.is_(True))) or 0
    admins_mfa = db.scalar(select(func.count()).where(
        AppUser.role == "admin", AppUser.is_active.is_(True),
        AppUser.totp_enabled_at.is_not(None))) or 0
    key_ok = crypto.get_keyring().current is not None
    networks = [str(n) for n in s.admin_networks]
    checks = [
        {"id": "https", "ok": s.site_is_domain if s.profile == "internet" else None,
         "detail": s.site_address},
        {"id": "secure_cookies", "ok": s.cookie_secure if s.profile == "internet" else None},
        {"id": "secret_key", "ok": key_ok},
        {"id": "admin_mfa", "ok": (admins_mfa == admins) if s.profile == "internet" else None,
         "detail": t("security.check.mfa_detail", mfa=admins_mfa, total=admins)},
        {"id": "admin_networks", "ok": None,
         "detail": ", ".join(networks) if networks else t("security.check.no_restriction")},
        {"id": "private_networks", "ok": None,
         "detail": (
             t("security.check.private_networks_allowed")
             if s.sources_allow_private_networks
             else t("security.check.private_networks_blocked")
         )},
        {"id": "login_rate_limit", "ok": None,
         "detail": t(
             "security.check.login_rate_limit",
             attempts=s.login_rate_limit,
             minutes=s.login_rate_window_minutes,
         )},
        {"id": "key_rotation", "ok": None,
         "detail": state.key_rotated_at.isoformat() if state and state.key_rotated_at
         else t("security.check.secret_never_rotated")},
    ]
    return {"profile": s.profile, "profile_source": s.security_profile,
            "http_allowed": s.http_allowed, "checks": checks,
            "legacy_origin_notice": bool(state and state.legacy_origin_notice),
            "legacy_origin_variable_present": bool(s.database_url_origin),
            "direct_reads": _direct_reads(db), "attachments": _attachments(db)}
