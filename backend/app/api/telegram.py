"""Telegram sign-in API (feature 007): super-user settings; sign-in and link routes below."""

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.auth import _fail, finish_sign_in, refuse_inactive_or_locked
from app.auth.deps import Auth, client_ip, current_auth, recent_reauth, require_superuser
from app.config import get_settings
from app.db import DB
from app.errors import ApiError, not_found
from app.i18n import M, t
from app.models import AppUser, TelegramLink, TelegramRequest, TelegramSettings
from app.security import throttle
from app.services import audit
from app.telegram import service

router = APIRouter()


class TelegramSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bot_username: str = Field(max_length=40)
    token: str | None = Field(default=None, max_length=100)


class TelegramEnabledIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool


@router.get("/api/admin/telegram")
def get_telegram_settings(
    _actor: AppUser = Depends(require_superuser),
    db: Session = DB,
):
    return service.public_state(service.settings_row(db))


@router.put("/api/admin/telegram")
def put_telegram_settings(
    body: TelegramSettingsIn,
    actor: AppUser = Depends(require_superuser),
    _auth: Auth = Depends(recent_reauth),
    ip: str | None = Depends(client_ip),
    db: Session = DB,
):
    row = service.update_settings(
        db, actor, bot_username=body.bot_username, token=body.token, ip=ip
    )
    return service.public_state(row)


@router.post("/api/admin/telegram/check")
def check_telegram(
    actor: AppUser = Depends(require_superuser),
    _auth: Auth = Depends(recent_reauth),
    ip: str | None = Depends(client_ip),
    db: Session = DB,
):
    return service.check(db, actor, ip=ip)


@router.post("/api/admin/telegram/enabled")
def set_telegram_enabled(
    body: TelegramEnabledIn,
    actor: AppUser = Depends(require_superuser),
    _auth: Auth = Depends(recent_reauth),
    ip: str | None = Depends(client_ip),
    db: Session = DB,
):
    row = service.set_enabled(db, actor, body.enabled, ip=ip)
    return service.public_state(row)


# --- sign-in (US3) --------------------------------------------------------------------------

MESSAGES = {
    "not_linked": (
        "Esta cuenta de Telegram no está vinculada. "
        "Ingresa con tu correo y vincúlala desde tu perfil."
    ),
    "wrong_code": "Elegiste un código distinto al de la pantalla. Intenta de nuevo.",
    "cancelled": "Cancelaste la solicitud en Telegram.",
}
TG_COOKIE = "bv_tg"
TG_PATH = "/api/auth/telegram"


def _tg_cookie(response: Response, secret: str) -> None:
    response.set_cookie(TG_COOKIE, secret, max_age=300, httponly=True,
                        secure=get_settings().cookie_secure, samesite="strict", path=TG_PATH)


def _clear_tg_cookie(response: Response) -> None:
    response.delete_cookie(TG_COOKIE, httponly=True, secure=get_settings().cookie_secure,
                           samesite="strict", path=TG_PATH)


@router.post("/api/auth/telegram/start")
def telegram_start(request: Request, response: Response, db: Session = DB):
    ip = client_ip(request)
    throttle.check(db, ip, get_settings())
    row = service.settings_row(db)
    if not service.is_available(row):
        raise not_found()
    service.ensure_reachable(row)

    old_secret = request.cookies.get(TG_COOKIE)
    old = service.find_by_browser(db, old_secret) if old_secret else None
    if old and service.is_live(old):
        old.status, old.reason = "expired", "replaced"

    new = service.new_request(db, "sign_in", ip=ip, user_agent=request.headers.get("user-agent"))
    _tg_cookie(response, new.browser_secret)
    link = service.deep_link(row.bot_username, new.start_token)
    return {
        "match_code": new.request.match_code,
        "deep_link": link,
        "qr_svg": service.qr(link),
        "expires_at": new.request.expires_at,
    }


@router.get("/api/auth/telegram/status")
def telegram_status(request: Request, response: Response, db: Session = DB):
    ip = client_ip(request)
    throttle.check(db, ip, get_settings())
    secret = request.cookies.get(TG_COOKIE)
    req = service.find_by_browser(db, secret) if secret else None

    if req is not None and req.status in ("pending", "started"):
        if service.is_live(req):
            return {"status": "pending"}
        req.status, req.reason = "expired", "expired"

    if req is not None and req.status == "refused":
        reason = req.reason or "unknown"
        # Report and count the failure exactly once (FR-009, SC-002).
        req.status = "expired"
        audit.record(db, "login_failed", target_id=req.user_id, ip=ip,
                     detail={"method": "telegram", "reason": reason})
        _fail(db, ip)
        _clear_tg_cookie(response)
        return {"status": "refused", "reason": reason,
                "message": (
                    t(f"telegram.refused.{reason}")
                    if reason in MESSAGES
                    else t("telegram.refused.other")
                )}

    claim = service.claim_approved(db, req.id) if req is not None and req.status == "approved" \
        else None
    if claim is None:
        _clear_tg_cookie(response)
        return {"status": "expired"}

    user = db.get(AppUser, claim.user_id)
    refuse_inactive_or_locked(db, user, ip, method="telegram")
    result = finish_sign_in(db, user, request, response, ip, method="telegram")
    _clear_tg_cookie(response)
    if result.get("mfa_required"):
        if result.get("mfa_enrollment_required"):
            return {"status": "mfa_required", "enrollment_required": True}
        return {"status": "mfa_required"}
    return {"status": "signed_in", "user": result["user"]}


# --- own link (US2) -------------------------------------------------------------------------

def _live_link_requests(db: Session, user_id: int):
    return db.query(TelegramRequest).filter(
        TelegramRequest.purpose == "link",
        TelegramRequest.user_id == user_id,
        TelegramRequest.status.in_(("pending", "started")),
        TelegramRequest.expires_at > service.now(),
    )


@router.get("/api/me/telegram")
def me_telegram(auth: Auth = Depends(current_auth), db: Session = DB):
    user = auth.user
    link = db.get(TelegramLink, user.id)
    return {
        "available": service.is_available(db.get(TelegramSettings, 1)),
        "linked": link is not None,
        "username": link.username if link else None,
        "display_name": link.display_name if link else None,
        "linked_at": link.linked_at if link else None,
        "pending": _live_link_requests(db, user.id).first() is not None,
    }


@router.post("/api/me/telegram/link")
def link_telegram(request: Request, auth: Auth = Depends(recent_reauth), db: Session = DB):
    user = auth.user
    row = service.settings_row(db)
    if not service.is_available(row):
        raise not_found()
    service.ensure_reachable(row)
    if db.get(TelegramLink, user.id) is not None:
        raise ApiError(409, "telegram_already_linked_self",
                       M("telegram.already_linked_self"))
    _live_link_requests(db, user.id).update({"status": "expired", "reason": "replaced"},
                                            synchronize_session=False)
    new = service.new_request(db, "link", user_id=user.id, ip=client_ip(request),
                              user_agent=request.headers.get("user-agent"))
    link = service.deep_link(row.bot_username, new.start_token)
    return {"deep_link": link, "qr_svg": service.qr(link), "expires_at": new.request.expires_at}


@router.delete("/api/me/telegram", status_code=204)
def unlink_telegram(request: Request, auth: Auth = Depends(recent_reauth), db: Session = DB):
    user = auth.user
    link = db.get(TelegramLink, user.id)
    if link is None:
        raise not_found(M("telegram.none_linked"))
    db.delete(link)
    audit.record(db, "telegram_unlinked", actor_id=user.id, target_id=user.id,
                 ip=client_ip(request))
