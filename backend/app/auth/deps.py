"""Request guards: session, pending second factor, temporary password, roles, step-up."""
import ipaddress
from dataclasses import dataclass

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.auth import sessions
from app.config import get_settings
from app.db import DB
from app.errors import ApiError, forbidden, unauthenticated
from app.models import AppUser, UserSession
from app.security import mfa, profile


@dataclass
class Auth:
    user: AppUser
    session: UserSession


def client_ip(request: Request) -> str | None:
    """Client address for audit and limits. Uvicorn runs with --proxy-headers behind Caddy, which
    only trusts TRUSTED_PROXIES, so request.client is the real client; non-IP values → None."""
    host = request.client.host if request.client else None
    try:
        return str(ipaddress.ip_address(host)) if host else None
    except ValueError:
        return None


from app.i18n import M, set_locale  # noqa: E402


def _lookup(request: Request, db: Session) -> Auth:
    found = sessions.lookup(db, request.cookies.get(sessions.COOKIE_NAME))
    if found is None:
        raise unauthenticated()
    sess, user = found
    if user.locale:
        set_locale(user.locale)
    return Auth(user=user, session=sess)


def pending_mfa_auth(request: Request, db: Session = DB) -> Auth:
    """Only for the second-factor step: a session whose password was accepted."""
    auth = _lookup(request, db)
    if not auth.session.mfa_pending:
        raise unauthenticated()
    return auth


def auth_allow_temporary(request: Request, db: Session = DB) -> Auth:
    auth = _lookup(request, db)
    if auth.session.mfa_pending:
        raise unauthenticated()  # second factor not given yet
    return auth


def enrollment_pending(user: AppUser) -> bool:
    """The password was accepted but the profile requires a second factor the account has not
    enrolled yet: the pending session may only enrol it (feature 004, FR-017)."""
    return profile.mfa_required_for(user.role, get_settings()) and not mfa.enabled(user)


def self_service_auth(request: Request, db: Session = DB) -> Auth:
    """Own profile only: a normal session, or the pending session of an unenrolled admin, which
    must be able to see /api/me and change a temporary password before enrolling."""
    auth = _lookup(request, db)
    if auth.session.mfa_pending and not enrollment_pending(auth.user):
        raise unauthenticated()
    return auth


def recent_reauth_or_enrollment(auth: Auth = Depends(self_service_auth)) -> Auth:
    """Step-up, or (only for an unenrolled admin) the pending session that may enrol."""
    if not auth.session.mfa_pending:
        ensure_recent_reauth(auth.session)
    return auth


def current_auth(auth: Auth = Depends(auth_allow_temporary)) -> Auth:
    if auth.user.must_change_password:
        raise ApiError(403, "password_change_required",
                       M("auth.password_change_required"))
    return auth


def current_user(auth: Auth = Depends(current_auth)) -> AppUser:
    return auth.user


def _mfa_gate(user: AppUser) -> None:
    if profile.mfa_required_for(user.role, get_settings()) and not mfa.enabled(user):
        raise ApiError(403, "mfa_enrollment_required",
                       M("mfa.enrollment_required"))


def require_admin(user: AppUser = Depends(current_user)) -> AppUser:
    if user.role != "admin":
        raise forbidden()
    _mfa_gate(user)
    return user


def require_superuser(user: AppUser = Depends(current_user)) -> AppUser:
    if not user.is_superuser:
        raise forbidden()
    _mfa_gate(user)
    return user


def ensure_recent_reauth(session: UserSession) -> None:
    until = sessions.reauth_valid_until(session)
    if until is None or until < sessions.now():
        raise ApiError(403, "reauth_required", M("auth.reauth_required"))


def recent_reauth(auth: Auth = Depends(current_auth)) -> Auth:
    """Step-up (feature 004, FR-021): password confirmed within the last 5 minutes."""
    ensure_recent_reauth(auth.session)
    return auth
