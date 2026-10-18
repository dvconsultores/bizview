from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.schemas import ChangePasswordIn, CodeIn, PreferencesIn, user_json
from app.auth import passwords, sessions
from app.auth.deps import (
    Auth,
    auth_allow_temporary,
    client_ip,
    recent_reauth,
    recent_reauth_or_enrollment,
    self_service_auth,
)
from app.config import get_settings
from app.db import DB
from app.errors import ApiError, forbidden
from app.i18n import M
from app.security import crypto, mfa, profile
from app.services import audit, users

router = APIRouter(prefix="/api/me")


@router.get("")
def me(auth: Auth = Depends(self_service_auth), db: Session = DB):
    user = auth.user
    return {**user_json(user),
            "mfa_required": profile.mfa_required_for(user.role, get_settings()),
            "reauth_valid_until": sessions.reauth_valid_until(auth.session),
            "recovery_codes_left": mfa.recovery_codes_left(db, user) if mfa.enabled(user) else 0,
            # Feature 024 FR-006: the image notice is shown once per account, on any device.
            "attachments_notice_at": (user.attachments_notice_at.isoformat()
                                      if user.attachments_notice_at else None)}


@router.post("/attachments-notice", status_code=204)
def accept_attachments_notice(auth: Auth = Depends(auth_allow_temporary),
                              db: Session = DB):
    """The user accepted that an attached image is sent to the AI provider (feature 024)."""
    if auth.user.attachments_notice_at is None:
        auth.user.attachments_notice_at = datetime.now(UTC)
        db.commit()


@router.post("/password", status_code=204)
def change_password(body: ChangePasswordIn, request: Request,
                    auth: Auth = Depends(self_service_auth), db: Session = DB):
    user, ip = auth.user, client_ip(request)
    if users.is_locked(user):
        raise users.locked_error(user)
    if not passwords.verify_password(user.password_hash, body.current_password):
        lock = users.register_failure(db, user, ip)
        if lock:
            sessions.delete_all(db, user.id)
        db.commit()
        raise lock or ApiError(401, "invalid_credentials", M("password.current_incorrect"),
                               fields={"current_password": "invalid"})
    users.check_new_password(body.new_password, user.email, current=body.current_password)
    users.set_password(user, body.new_password, temporary=False)
    user.failed_attempts = 0
    sessions.delete_all(db, user.id, except_hash=auth.session.id_hash)
    audit.record(db, "password_changed", actor_id=user.id, target_id=user.id, ip=ip)


@router.patch("/preferences")
def update_preferences(body: PreferencesIn, auth: Auth = Depends(auth_allow_temporary)):
    """Display preferences (feature 006). Not a security event, so not audited; allowed with a
    temporary password so the password-change screen can switch theme too."""
    fields = body.model_fields_set
    if 'theme' in fields and body.theme is not None:
        auth.user.theme = body.theme
    if 'locale' in fields:
        auth.user.locale = body.locale
    return {"theme": auth.user.theme, "locale": auth.user.locale}


# --- own two-step sign-in (feature 004, FR-018); every change needs step-up ------------------

@router.post("/mfa/setup")
def mfa_setup(auth: Auth = Depends(recent_reauth_or_enrollment), db: Session = DB):
    user = auth.user
    if mfa.enabled(user):
        raise ApiError(409, "conflict", M("mfa.already_active"))
    secret = mfa.new_secret()
    mfa.store_pending_secret(user, secret, crypto.get_keyring())
    crypto.ensure_key_check(db, crypto.get_keyring())
    uri = mfa.provisioning_uri(secret, user.email, get_settings().product_name)
    return {"otpauth_uri": uri, "secret": secret, "qr_svg": mfa.qr_svg_data_uri(uri)}


@router.post("/mfa/enable")
def mfa_enable(body: CodeIn, request: Request,
               auth: Auth = Depends(recent_reauth_or_enrollment), db: Session = DB):
    user = auth.user
    if mfa.enabled(user):
        raise ApiError(409, "conflict", M("mfa.already_active"))
    if user.totp_secret_ct is None:
        raise ApiError(409, "conflict", M("mfa.qr_required"))
    if not mfa.verify_code(user, body.code, crypto.get_keyring()):
        raise ApiError(422, "invalid_code", M("mfa.invalid_code"), fields={"code": "invalid"})
    mfa.enable(user)
    codes = mfa.new_recovery_codes(db, user)
    # Other sessions were opened without the second factor: end them.
    sessions.delete_all(db, user.id, except_hash=auth.session.id_hash)
    if auth.session.mfa_pending:
        # The pending session that may only enrol becomes the session of this sign-in.
        auth.session.mfa_pending = False
        auth.session.reauth_at = sessions.now()
        user.failed_attempts = 0
        user.locked_until = None
        user.last_login_at = users.now()
        audit.record(db, "login_ok", actor_id=user.id, target_id=user.id, ip=client_ip(request),
                     detail={"method": "mfa_enrollment"})
    audit.record(db, "mfa_enabled", actor_id=user.id, target_id=user.id, ip=client_ip(request))
    return {"recovery_codes": codes}


@router.post("/mfa/recovery-codes")
def mfa_new_codes(request: Request, auth: Auth = Depends(recent_reauth), db: Session = DB):
    user = auth.user
    if not mfa.enabled(user):
        raise ApiError(409, "conflict", M("mfa.not_active"))
    codes = mfa.new_recovery_codes(db, user)
    audit.record(db, "recovery_codes_regenerated", actor_id=user.id, target_id=user.id,
                 ip=client_ip(request))
    return {"recovery_codes": codes}


@router.post("/mfa/disable", status_code=204)
def mfa_disable(body: CodeIn, request: Request, auth: Auth = Depends(recent_reauth),
                db: Session = DB):
    user = auth.user
    if not mfa.enabled(user):
        raise ApiError(409, "conflict", M("mfa.not_active"))
    if profile.mfa_required_for(user.role, get_settings()):
        raise forbidden(M("mfa.required_for_admin"))
    if not mfa.verify_code(user, body.code, crypto.get_keyring()):
        raise ApiError(422, "invalid_code", M("mfa.invalid_code"), fields={"code": "invalid"})
    mfa.disable(db, user)
    audit.record(db, "mfa_disabled", actor_id=user.id, target_id=user.id, ip=client_ip(request))
