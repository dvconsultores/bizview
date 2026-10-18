from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.schemas import LoginIn, MfaIn, ReauthIn, user_json
from app.auth import passwords, sessions
from app.auth.deps import Auth, auth_allow_temporary, client_ip, pending_mfa_auth
from app.config import get_settings
from app.db import DB
from app.errors import ApiError
from app.i18n import M
from app.security import crypto, mfa, profile, throttle
from app.services import audit, users

router = APIRouter(prefix="/api/auth")

INVALID = ApiError(401, "invalid_credentials", M("auth.invalid_credentials"))
INVALID_CODE = ApiError(401, "invalid_code", M("mfa.invalid_code"))


def _fail(db: Session, ip: str | None) -> None:
    """Count a failure for the address and keep it even though an error response follows."""
    throttle.register_failure(db, ip, get_settings())
    db.commit()


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = DB):
    ip = client_ip(request)
    throttle.check(db, ip, get_settings())
    user = users.by_email(db, body.email)
    if user is None:
        passwords.verify_password(passwords.DUMMY_HASH, body.password)
        audit.record(db, "login_failed", ip=ip,
                     detail={"email": passwords.normalise_email(body.email)[:254]})
        _fail(db, ip)
        raise INVALID
    if users.is_locked(user):
        audit.record(db, "login_failed", target_id=user.id, ip=ip, detail={"locked": True})
        _fail(db, ip)
        raise users.locked_error(user)
    ok = passwords.verify_password(user.password_hash, body.password)
    if not ok or not user.is_active:
        if not user.is_active:
            audit.record(db, "login_failed", target_id=user.id, ip=ip, detail={"inactive": True})
            _fail(db, ip)
            raise INVALID
        lock = users.register_failure(db, user, ip)
        _fail(db, ip)
        raise lock or INVALID

    if passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash_password(body.password)
    return finish_sign_in(db, user, request, response, ip)


def refuse_inactive_or_locked(db: Session, user, ip: str | None, *, method: str) -> None:
    """Same refusals as password sign-in, for credentials proven another way (feature 007)."""
    if users.is_locked(user):
        audit.record(db, "login_failed", target_id=user.id, ip=ip,
                     detail={"locked": True, "method": method})
        _fail(db, ip)
        raise users.locked_error(user)
    if not user.is_active:
        audit.record(db, "login_failed", target_id=user.id, ip=ip,
                     detail={"inactive": True, "method": method})
        _fail(db, ip)
        raise ApiError(401, "invalid_credentials", M("auth.account_disabled"))


def finish_sign_in(db: Session, user, request: Request, response: Response, ip: str | None,
                   *, method: str = "password") -> dict:
    """Shared by every sign-in method once the credential is proven: two-step or session."""
    if mfa.enabled(user):
        # Credential accepted; the session only allows the second-factor step for 5 minutes.
        raw = sessions.create(db, user, request.headers.get("user-agent"), ip, mfa_pending=True)
        sessions.set_cookie(response, raw)
        return {"mfa_required": True}
    if profile.mfa_required_for(user.role, get_settings()):
        # The profile demands a second factor this account has not enrolled yet (a superuser
        # `reset_mfa`, or a never-enrolled admin). The session may only enrol it, never act.
        raw = sessions.create(db, user, request.headers.get("user-agent"), ip, mfa_pending=True)
        sessions.set_cookie(response, raw)
        return {"mfa_required": True, "mfa_enrollment_required": True}
    return _complete_login(db, user, request, response, ip, method=method)


def _complete_login(db: Session, user, request: Request, response: Response,
                    ip: str | None, *, method: str = "password") -> dict:
    user.failed_attempts = 0
    user.locked_until = None
    user.last_login_at = users.now()
    raw = sessions.create(db, user, request.headers.get("user-agent"), ip)
    audit.record(db, "login_ok", actor_id=user.id, target_id=user.id, ip=ip,
                 detail={"method": method} if method != "password" else None)
    sessions.set_cookie(response, raw)
    return {"user": user_json(user)}


@router.post("/mfa")
def second_factor(body: MfaIn, request: Request, response: Response,
                  auth: Auth = Depends(pending_mfa_auth), db: Session = DB):
    ip, user = client_ip(request), auth.user
    throttle.check(db, ip, get_settings())
    if users.is_locked(user):
        raise users.locked_error(user)
    if body.recovery_code:
        ok = mfa.use_recovery_code(db, user, body.recovery_code)
        if ok:
            audit.record(db, "recovery_code_used", actor_id=user.id, target_id=user.id, ip=ip,
                         detail={"left": mfa.recovery_codes_left(db, user)})
    else:
        ok = bool(body.code) and mfa.verify_code(user, body.code or "", crypto.get_keyring())
    if not ok:
        lock = users.register_failure(db, user, ip)
        if lock:
            sessions.delete_all(db, user.id)
        _fail(db, ip)
        raise lock or INVALID_CODE
    # Replace the pending session with a fresh one (no session fixation across the two steps).
    db.delete(auth.session)
    return _complete_login(db, user, request, response, ip)


@router.post("/reauth", status_code=204)
def reauth(body: ReauthIn, request: Request, auth: Auth = Depends(auth_allow_temporary),
           db: Session = DB):
    ip, user = client_ip(request), auth.user
    throttle.check(db, ip, get_settings())
    if users.is_locked(user):
        raise users.locked_error(user)
    if not passwords.verify_password(user.password_hash, body.password):
        audit.record(db, "reauth_failed", actor_id=user.id, target_id=user.id, ip=ip)
        lock = users.register_failure(db, user, ip)
        if lock:
            sessions.delete_all(db, user.id)
        _fail(db, ip)
        raise lock or ApiError(401, "invalid_credentials", M("auth.password_incorrect"),
                               fields={"password": "invalid"})
    user.failed_attempts = 0
    auth.session.reauth_at = sessions.now()
    audit.record(db, "reauth_ok", actor_id=user.id, target_id=user.id, ip=ip)


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = DB):
    raw = request.cookies.get(sessions.COOKIE_NAME)
    found = sessions.lookup(db, raw)
    if found and not found[0].mfa_pending:
        audit.record(db, "logout", actor_id=found[1].id, target_id=found[1].id,
                     ip=client_ip(request))
    sessions.delete_one(db, raw)
    response = Response(status_code=204)
    sessions.clear_cookie(response)
    return response
